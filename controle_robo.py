
import serial
import time
import threading
from pynput import keyboard

# =====================================
# CONFIGURACOES
# =====================================

PORTA = "COM3"
BAUDRATE = 115200

VELOCIDADE_MAX = 900
VELOCIDADE_MIN = 100
VELOCIDADE_INICIAL = 500

PASSO_VELOCIDADE = 10
INTERVALO_VELOCIDADE = 0.1

# Enviar 20 comandos por segundo
INTERVALO_ENVIO = 0.05

# =====================================
# ESTADO
# =====================================

teclas = set()

velocidade = VELOCIDADE_INICIAL

shift_pressionado = False
ctrl_pressionado = False

programa_rodando = True

lock = threading.Lock()

# =====================================
# CINEMATICA MECANUM
# =====================================

def calcular_mecanum(x, y, rot, vel):

    fl = y + x + rot
    fr = y - x - rot
    rl = y - x + rot
    rr = y + x - rot

    valores = [fl, fr, rl, rr]

    # Normalizacao
    maior = max(1.0, *(abs(v) for v in valores))

    return [
        int(v / maior * vel)
        for v in valores
    ]

# =====================================
# ENVIO SERIAL
# =====================================

def enviar_motores(esp32, velocidades):

    comando = (
        "M=" +
        ",".join(str(v) for v in velocidades) +
        "\n"
    )

    esp32.write(comando.encode("ascii"))

# =====================================
# THREAD DE COMUNICACAO
# =====================================

def controle_serial(esp32):

    global velocidade

    ultimo_ajuste = time.monotonic()

    while programa_rodando:

        inicio = time.monotonic()

        with lock:

            agora = time.monotonic()

            if agora - ultimo_ajuste >= INTERVALO_VELOCIDADE:

                velocidade_anterior = velocidade

                if shift_pressionado:
                    velocidade = min(
                        velocidade + PASSO_VELOCIDADE,
                        VELOCIDADE_MAX
                    )

                elif ctrl_pressionado:
                    velocidade = max(
                        velocidade - PASSO_VELOCIDADE,
                        VELOCIDADE_MIN
                    )

                # Imprime apenas quando a velocidade mudar
                if velocidade != velocidade_anterior:
                    print(f"Velocidade: {velocidade}")

                ultimo_ajuste = agora

            estado = teclas.copy()
            vel = velocidade

        # Eixos de translacao
        x = int("a" in estado) - int("d" in estado)
        y = int("w" in estado) - int("s" in estado)

        # Rotacao
        rot = int("j" in estado) - int("l" in estado)

        velocidades = calcular_mecanum(
            x, y, rot, vel
        )

        enviar_motores(esp32, velocidades)

        restante = INTERVALO_ENVIO - (
            time.monotonic() - inicio
        )

        if restante > 0:
            time.sleep(restante)

# =====================================
# FUNCOES DO TECLADO
# =====================================

def executar_controle(esp32):

    global shift_pressionado
    global ctrl_pressionado
    global programa_rodando

    teclas_validas = set("wasdjl")

    def tecla_pressionada(key):

        global shift_pressionado
        global ctrl_pressionado
        global programa_rodando

        if key in (
            keyboard.Key.shift,
            keyboard.Key.shift_l,
            keyboard.Key.shift_r
        ):
            with lock:
                shift_pressionado = True
            return

        if key in (
            keyboard.Key.ctrl,
            keyboard.Key.ctrl_l,
            keyboard.Key.ctrl_r
        ):
            with lock:
                ctrl_pressionado = True
            return

        try:
            tecla = key.char.lower()
        except (AttributeError, TypeError):
            return

        if tecla in teclas_validas:
            with lock:
                teclas.add(tecla)

        elif tecla == "x":
            with lock:
                teclas.clear()
            print("PARADO")

        elif tecla == "q":
            programa_rodando = False
            with lock:
                teclas.clear()
            return False

    def tecla_solta(key):

        global shift_pressionado
        global ctrl_pressionado

        if key in (
            keyboard.Key.shift,
            keyboard.Key.shift_l,
            keyboard.Key.shift_r
        ):
            with lock:
                shift_pressionado = False
            return

        if key in (
            keyboard.Key.ctrl,
            keyboard.Key.ctrl_l,
            keyboard.Key.ctrl_r
        ):
            with lock:
                ctrl_pressionado = False
            return

        try:
            tecla = key.char.lower()
        except (AttributeError, TypeError):
            return

        if tecla in teclas_validas:
            with lock:
                teclas.discard(tecla)

    with keyboard.Listener(
        on_press=tecla_pressionada,
        on_release=tecla_solta
    ) as listener:

        listener.join()

# =====================================
# PROGRAMA PRINCIPAL
# =====================================

def main():

    global programa_rodando

    print("Conectando ao ESP32...")

    with serial.Serial(
        PORTA,
        BAUDRATE,
        timeout=0.1,
        write_timeout=0.2
    ) as esp32:

        # Aguarda reinicializacao do ESP32
        time.sleep(2)

        esp32.reset_input_buffer()

        print("ESP32 conectado!")
        print()
        print("=== CONTROLE MECANUM ===")
        print("W/S = Frente / Tras")
        print("A/D = Movimento lateral")
        print("J/L = Girar")
        print("W+A, W+D = Diagonais")
        print("SHIFT = Aumentar velocidade")
        print("CTRL = Diminuir velocidade")
        print("X = Parar")
        print("Q = Sair")
        print()

        thread = threading.Thread(
            target=controle_serial,
            args=(esp32,),
            daemon=True
        )

        try:
            thread.start()
            executar_controle(esp32)

        except KeyboardInterrupt:
            print("\nInterrompido.")

        finally:
            programa_rodando = False
            thread.join(timeout=1.0)

            # Envia parada final
            try:
                enviar_motores(esp32, [0, 0, 0, 0])
                esp32.flush()
            except serial.SerialException:
                pass

            print("Programa encerrado.")


if __name__ == "__main__":
    main()
