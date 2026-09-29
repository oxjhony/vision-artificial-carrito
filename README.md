# Robot Seguidor (mBot + Vision Artificial)

Repositorio base para controlar un robot mBot desde un computador "Master PC" usando algoritmos de vision artificial.

## Objetivo

Este proyecto permite que un computador procese imagenes/camara y, a partir de ese analisis, envie comandos de movimiento al robot.

## Estructura del repositorio

- `master_pc/`
  - Contiene el codigo que **SI** deben modificar los estudiantes.
  - Aqui se implementan los algoritmos del reto (vision artificial, logica de control, toma de decisiones).
- `actuadores_arduino/`
  - Contiene el firmware del robot (`arduinoFinal.ino`).
  - Este script ya define como interpretar comandos de movimiento en el mBot.
  - **NO debe ser modificado por estudiantes.**

## Regla principal para estudiantes

Trabajar **exclusivamente** en la carpeta `master_pc/`.

No se debe editar, alterar ni reemplazar nada en `actuadores_arduino/` durante los retos.

## Flujo de funcionamiento

1. El Master PC captura imagen (camara).
2. El algoritmo de vision artificial analiza la escena.
3. Se decide una accion (adelante, atras, izquierda, derecha, parar).
4. El Master PC envia un comando por Bluetooth al mBot.
5. El firmware en Arduino ejecuta el movimiento.

## Comandos de control (Master PC -> Robot)

- `w`: adelante
- `s`: atras
- `a`: izquierda
- `d`: derecha
- `x`: parar

## Componentes actuales

### Master PC

- `main.py`: punto de entrada, lectura de camara y envio de comandos.
- `Robot.py`: clase para conexion Bluetooth y envio de comandos.

### Arduino (robot)

- `arduinoFinal.ino`: recepcion de comandos y accion sobre motores.

## Alcance academico

En cada reto, los estudiantes deben:

- Implementar o ajustar el procesamiento de vision en `master_pc/`.
- Definir la estrategia de navegacion/control en `master_pc/`.
- Mantener intacto el firmware de Arduino.

## Requisitos sugeridos (Master PC)

- Python 3.10+
- OpenCV (`opencv-python`)
- Conexion Bluetooth funcional con el mBot
- Camara disponible en el equipo

## Ejecucion base

Desde la carpeta `master_pc/`:

```bash
python main.py
```

## Nota para docentes

Este repositorio separa explicitamente:

- Capa de actuacion (Arduino, fija y protegida).
- Capa de inteligencia (Master PC, editable por estudiantes).

Esta separacion asegura evaluaciones centradas en algoritmos de vision y toma de decisiones, sin depender de cambios de bajo nivel en el robot.
