#include <MeMCore.h>

// Definir motores del mBot
MeDCMotor motorLeft(M1);  // Motor izquierdo
MeDCMotor motorRight(M2); // Motor derecho

// Velocidad base de los motores
int speed = 150;

// Funciones para controlar el movimiento del mBot
void moveForward() {
  motorLeft.run(-speed);
  motorRight.run(speed);
}

void moveBackward() {
  motorLeft.run(speed);
  motorRight.run(-speed);
}

void turnLeft() {
  motorLeft.run(speed);
  motorRight.run(speed);
}

void turnRight() {
  motorLeft.run(-speed);
  motorRight.run(-speed);
}

void stopMotors() {
  motorLeft.run(0);
  motorRight.run(0);
}

// Función para procesar comandos recibidos por Bluetooth
void executeCommand(char command) {
  switch (command) {
    case 'w': // Adelante
      moveForward();
      delay(100);  // Girar durante 1 segundo
      stopMotors(); // Detener motores
      Serial.println("Comando: Adelante");
      break;
    case 's': // Atrás
      moveBackward();
      delay(100);  // Girar durante 1 segundo
      stopMotors(); // Detener motores
      Serial.println("Comando: Atrás");
      break;
    case 'a': // Girar izquierda
      turnLeft();
      delay(30);  // Girar durante 1 segundo
      stopMotors(); // Detener motores
      Serial.println("Comando: Izquierda");
      break;
    case 'd': // Girar derecha
      turnRight();
      delay(30);  // Girar durante 1 segundo
      stopMotors(); // Detener motores
      Serial.println("Comando: Derecha");
      break;
    case 'x': // Detener motores
      stopMotors();
      Serial.println("Comando: Detener");
      break;
    default:
      Serial.println("Comando no reconocido");
      break;
  }
}

void setup() {
  Serial.begin(115200); // Inicializar la comunicación serial
  stopMotors();       // Asegurarse de que los motores estén detenidos al iniciar
  Serial.println("mBot listo para recibir comandos por Bluetooth");
}

void loop() {
  // Leer datos enviados por Bluetooth
  if (Serial.available() > 0) {
    char command = Serial.read(); // Leer un carácter desde el puerto serial
    executeCommand(command);      // Ejecutar el comando recibido
  }
}
