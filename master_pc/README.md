# master_pc

Esta carpeta contiene el codigo Python que los estudiantes SI deben modificar para resolver el reto.

## Ejecucion

```bash
python main.py
```

Se abre una ventana con dos pestanas (al inicio el contenido esta vacio):

- **Simulacion**: pista virtual con un robot que usa el cerebro de vision. Botones o teclas: `P` pausa, `R` reinicia, `+`/`-` velocidad. Al cambiar de pestana la simulacion se detiene y al volver continua.
- **Camara**: a la izquierda se conecta el robot (MAC Bluetooth) y la camara, cada uno con su estado en colores
  (verde conectado, rojo fallo, naranja desconectado). En la camara se puede escribir `Camara0`, `Camara1`, ...
  para usar una camara del computador, o una URL (por ejemplo `http://192.168.1.50:8080/video` del celular).
  Debajo se ven las llantas girando segun la decision y una flecha verde (anda) o roja (para).
  A la derecha se ve la camara con lo que detecta el cerebro. El robot recibe `w`, `a`, `d` o `x`.

## Archivos principales

- main.py: ventana principal con las pestanas Simulacion / Camara.
- configuracion.py: todos los valores ajustables (umbrales, control, simulador).
- cerebro.py: vision artificial y decision (linea, senales PARE/SIGA, control PD, maquina de estados).
- simulador.py: pista, robot virtual y pestana del simulador.
- camara.py: pestana de la camara (conexion Bluetooth, camara, llantas y envio de comandos).
- vista_tk.py: muestra imagenes de OpenCV dentro de la ventana.
- Robot.py: conexion Bluetooth y envio de comandos al mBot.

## Configuracion del robot real

Escriba la MAC Bluetooth real del mBot en la pestana Camara antes de pulsar Conectar.
El valor por defecto se cambia en `MAC_POR_DEFECTO` dentro de camara.py.

## Regla para estudiantes

Trabajar solo en esta carpeta.
No modificar actuadores_arduino.
