
#include <Arduino.h>
#include <AccelStepper.h>
#include <math.h>
#include <stdlib.h>

// =====================================
// PINOS - MANTIDOS DO SEU PROJETO
// =====================================

#define STEP_FL 26
#define DIR_FL  27

#define STEP_FR 12
#define DIR_FR  14

#define STEP_RL 18
#define DIR_RL  19

#define STEP_RR 16
#define DIR_RR  17

#define EN_PIN 25

// =====================================
// MOTORES
// =====================================

AccelStepper FL(AccelStepper::DRIVER, STEP_FL, DIR_FL);
AccelStepper FR(AccelStepper::DRIVER, STEP_FR, DIR_FR);
AccelStepper RL(AccelStepper::DRIVER, STEP_RL, DIR_RL);
AccelStepper RR(AccelStepper::DRIVER, STEP_RR, DIR_RR);

AccelStepper* motores[4] = {
    &FL, &FR, &RL, &RR
};

// =====================================
// CONFIGURACOES
// =====================================

const float MAX_SPEED = 1000.0f;
const float ACCELERATION = 1500.0f;

const unsigned long TIMEOUT = 500;

const int DIRECAO[4] = {
     1,  1, -1, -1
};

float velocidadeAlvo[4] = {0};
float velocidadeAtual[4] = {0};

unsigned long ultimoComando = 0;
unsigned long ultimaAtualizacao = 0;

// Buffer serial
char buffer[80];
size_t indice = 0;

// =====================================
// DEFINIR VELOCIDADES
// =====================================

void definirVelocidades(
    float fl,
    float fr,
    float rl,
    float rr
) {
    float valores[4] = {fl, fr, rl, rr};

    for (int i = 0; i < 4; i++) {
        velocidadeAlvo[i] = constrain(
            valores[i],
            -MAX_SPEED,
            MAX_SPEED
        ) * DIRECAO[i];
    }
}

// =====================================
// PARADA COM DESACELERACAO
// =====================================

void parar() {
    definirVelocidades(0, 0, 0, 0);
}

// =====================================
// ATUALIZACAO DA ACELERACAO
// =====================================

void atualizarAceleracao() {

    unsigned long agora = micros();

    float dt =
        (agora - ultimaAtualizacao) / 1000000.0f;

    ultimaAtualizacao = agora;

    dt = min(dt, 0.05f);

    float incremento = ACCELERATION * dt;

    for (int i = 0; i < 4; i++) {

        float diferenca =
            velocidadeAlvo[i] - velocidadeAtual[i];

        diferenca = constrain(
            diferenca,
            -incremento,
            incremento
        );

        velocidadeAtual[i] += diferenca;

        motores[i]->setSpeed(velocidadeAtual[i]);
    }
}

// =====================================
// PROCESSAR COMANDO
// Formato: M=FL,FR,RL,RR
// =====================================

void processarComando(char* comando) {

    if (strcmp(comando, "STOP") == 0) {
        parar();
        ultimoComando = millis();
        return;
    }

    if (strncmp(comando, "M=", 2) != 0) {
        return;
    }

    float valores[4];
    char* p = comando + 2;

    for (int i = 0; i < 4; i++) {

        char* fim;
        valores[i] = strtof(p, &fim);

        if (fim == p || !isfinite(valores[i])) {
            return;
        }

        if (i < 3) {
            if (*fim != ',') return;
            p = fim + 1;
        } else {
            if (*fim != '\0') return;
        }
    }

    definirVelocidades(
        valores[0],
        valores[1],
        valores[2],
        valores[3]
    );

    ultimoComando = millis();
}

// =====================================
// SERIAL NAO BLOQUEANTE
// =====================================

void lerSerial() {

    // Limita o processamento por ciclo
    // para preservar a geracao de passos.
    int processados = 0;

    while (Serial.available() && processados < 64) {

        char c = Serial.read();
        processados++;

        if (c == '\n') {

            buffer[indice] = '\0';

            processarComando(buffer);

            indice = 0;

        } else if (c != '\r') {

            if (indice < sizeof(buffer) - 1) {
                buffer[indice++] = c;
            } else {
                indice = 0;
            }
        }
    }
}

// =====================================
// SETUP
// =====================================

void setup() {

    Serial.begin(115200);

    pinMode(EN_PIN, OUTPUT);

    // A4988: ENABLE ativo em LOW
    digitalWrite(EN_PIN, LOW);

    for (int i = 0; i < 4; i++) {

        motores[i]->setMaxSpeed(MAX_SPEED);
        motores[i]->setMinPulseWidth(3);
        motores[i]->setSpeed(0);
    }

    ultimoComando = millis();
    ultimaAtualizacao = micros();

    Serial.println("MECANUM_READY");
}

// =====================================
// LOOP PRINCIPAL
// =====================================

void loop() {

    lerSerial();

    // Failsafe
    if (millis() - ultimoComando > TIMEOUT) {
        parar();
    }

    // Atualiza as velocidades
    atualizarAceleracao();

    // Executa os quatro motores
    FL.runSpeed();
    FR.runSpeed();
    RL.runSpeed();
    RR.runSpeed();
}
