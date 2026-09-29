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

## De donde sale cada tecnica de vision

Todo el procesamiento de `cerebro.py` usa unicamente tecnicas de los notebooks 3 y 4
del curso y de `extra.py` / `extra2.py`. No se usa ninguna funcion de deteccion de
contornos: los centroides, los perimetros y la separacion de regiones se calculan
con proyecciones y aritmetica sobre las mascaras.

| Etapa | Tecnica | Funcion | Origen |
| ----- | ------- | ------- | ------ |
| Preparar la imagen | Suavizado con kernel impar | `GaussianBlur` | extra.py |
| Preparar la imagen | Escala de grises | `cvtColor(COLOR_BGR2GRAY)` | notebook 3, extra.py |
| Umbral de la linea | Agrupar piso y linea con K = 2 | `KMeans` | notebook 4 |
| Mascara de la linea | Umbralizacion | `threshold(THRESH_BINARY)` | notebook 3 |
| Mascara de la linea | Resta para invertir la mascara | `subtract` | notebook 3 |
| Mascara de la linea | Apertura (erosion entonces dilatacion) | `erode`, `dilate` | extra.py |
| Direccion | Centroide por franja | proyeccion de columnas (NumPy) | aritmetica, notebook 3 |
| Mascara de color | Dominancia de canal (resta) | `subtract` | notebook 3 |
| Mascara de color | Descartar sombras oscuras | `threshold` + `bitwise_and` | notebook 3 |
| Mascara de color | Cierre (dilatacion entonces erosion) | `dilate`, `erode` | extra.py |
| Señales | Separar regiones | proyecciones (NumPy) | aritmetica, notebook 3 |
| Señales | Perimetro (anillo del borde) | `dilate` - `erode` | extra.py + notebook 3 |
| Señales | Compacidad radial | radios centroide-borde (NumPy) | aritmetica, notebook 3 |
| Señales | Nitidez del borde | `Canny` + `bitwise_and` | extra.py + notebook 3 |
| Dibujo | Recuadros, lineas y textos | `rectangle`, `line`, `circle`, `putText` | notebook 3, extra.py |

Nota sobre el simulador: `simulador.py` usa `getPerspectiveTransform` y
`warpPerspective` para generar la imagen sintetica de la camara. Eso **reemplaza a
la camara**, no analiza nada: no forma parte del algoritmo de vision.

### Por que no se cuentan los 8 vertices del octagono

La camara mira el piso en diagonal, asi que el octagono pintado en la pista **no
llega a la imagen como un octagono**: la perspectiva lo estira y lo inclina. Se
midio la compacidad radial (radio minimo entre radio maximo desde el centroide, que
es invariante a la rotacion) contra figuras de geometria conocida:

| figura | compacidad radial |
| ------ | ----------------- |
| octagono regular | 0.92 |
| circulo | 0.97 |
| cuadrado (y el mismo girado 45 grados) | 0.72 |
| triangulo | 0.52 |
| barra fina | 0.16 |
| **señal real vista por la camara** | **0.71** |

La señal real mide 0.71, el valor de un cuadrado. Contar vertices seria afirmar algo
que la imagen no sostiene. Lo que si se puede medir con seguridad es que la region
es **compacta, del color correcto y del tamaño correcto**, y eso basta porque en la
pista los unicos objetos rojos y verdes son las señales. Si en la competencia
aparecen distractores rojos o verdes (ropa, cables, reflejos), el filtro que los
rechaza es la compacidad: una barra da 0.16 contra 0.71 de una señal.

Tampoco se usa la circularidad 4·pi·A/P². Se midio que con un perimetro discreto
depende mas de la inclinacion de la figura que de su forma: un cuadrado da 0.40 y el
mismo cuadrado girado 45 grados da 0.79. Rechazaria señales validas y aceptaria rombos.

### Envolvente de operacion (medida en el simulador)

Se vario la iluminacion del mapa y se midio cuando deja de funcionar:

| Condicion | Rango que aguanta | Que pasa al salirse |
| --------- | ----------------- | ------------------- |
| Ganancia de luz | 0.30x a 1.0x+ | pierde la linea, entra en BUSCANDO y gira |
| Contraste | 0.40x a 1.0x | igual: falla de forma segura, sin descarrilarse |

Con umbrales fijos el sistema se rompia en ganancia 0.44x, y lo hacia de la peor
manera: el piso entero entraba en la mascara, el robot creia que seguia una linea
(0 % de cuadros "sin linea") y recorria la pista **al reves y fuera del carril**,
con 5 descarrilamientos y 312 px de desvio. Ahora en esa misma condicion da 0
descarrilamientos y 22 px.

**La leccion, y va en el poster:** cada umbral absoluto del pipeline era un punto de
falla ante cambios de luz. Aparecieron tres, todos con el mismo sintoma (funciona a
luz nominal, se cae al variarla) y todos con la misma solucion: derivar el umbral de
una medicion de la propia imagen en vez de clavarlo.

1. Umbral de la linea -> lo fija K-Means (notebook 4).
2. Dominancia de color -> relativa al brillo del pixel, no absoluta. Ademas el brillo
   se mide como `max(R,G,B)` y no como escala de grises, donde el rojo pesa solo
   0.299 y un rojo saturado se pierde en cuanto baja la luz.
3. Umbrales de Canny -> atados a la separacion piso/linea que K-Means ya calculo.

### Limitaciones conocidas

* **Un circulo rojo pasa el filtro de forma** (compacidad 0.97 contra 0.92 del
  octagono). Es la unica figura mas compacta que un octagono, y el cierre
  morfologico que tapa las letras redondea las esquinas. Sin contar vertices no hay
  forma limpia de separarlos. En la pista no deberia haber tapas ni puntos rojos
  redondos, pero conviene saberlo.
* **El estado BUSCANDO no sabe cual es "hacia adelante".** Si pierde la linea y gira
  demasiado, puede recuperarla mirando al otro lado y recorrer la pista en sentido
  contrario. Se observo con la luz al 30 %.
* **Los umbrales de color no se han calibrado contra imagenes reales**, solo contra
  el simulador. Los videos de ensayo del reto son la siguiente prueba pendiente.

### Por que K-Means y no un umbral fijo

Con un umbral clavado en un numero, basta una sombra para que el piso entero entre
en la mascara de la linea. El robot no se entera (sigue "viendo" una linea) y
recorre la pista fuera del carril. K-Means mira los niveles de gris de la ROI, los
separa en dos grupos (piso y linea) y pone el umbral en la mitad, asi que se mueve
solo cuando cambia la luz. Ademas, si los dos grupos quedan muy juntos
(`SEPARACION_MINIMA`) se concluye que no hay linea, en vez de umbralizar ruido.

## Configuracion del robot real

Escriba la MAC Bluetooth real del mBot en la pestana Camara antes de pulsar Conectar.
El valor por defecto se cambia en `MAC_POR_DEFECTO` dentro de camara.py.

## Regla para estudiantes

Trabajar solo en esta carpeta.
No modificar actuadores_arduino.
