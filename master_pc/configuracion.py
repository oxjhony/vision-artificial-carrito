# Todos los valores ajustables del cerebro y del simulador.

# ================= CEREBRO (visión) =================

# Línea
ROI_INICIO = 0.45       # la zona de análisis empieza en el 45 % de la altura de la imagen
N_FRANJAS = 3           # la ROI se divide en franjas horizontales
PESOS_FRANJAS = [0.2, 0.3, 0.5]  # peso de cada franja en el error (de arriba hacia abajo)
V_MAX_LINEA = 90        # brillo máximo (V) de un píxel de la línea negra
S_MAX_LINEA = 90        # saturación máxima (S): la línea es negra, no de color
AREA_MIN_LINEA = 150    # área mínima (px) de un trozo de línea en una franja

# Señales
ROJO_1 = ((0, 100, 70), (10, 255, 255))      # el rojo está en los dos extremos del tono H
ROJO_2 = ((170, 100, 70), (179, 255, 255))
VERDE = ((40, 80, 50), (85, 255, 255))
AREA_MIN_SENAL = 0.004  # fracción de la imagen para considerar un objeto como posible señal
SENAL_Y_CERCA = 0.5     # la señal está "cerca" cuando su centro pasa de la mitad de la imagen hacia abajo
CUADROS_CONFIRMAR = 3   # cuadros seguidos viendo la señal antes de reaccionar

# Comportamiento
TIEMPO_PARE = 3.0       # segundos detenido ante PARE (lo define el docente)

# Control de las llantas (escala -100 a 100)
VEL_BASE = 60
VEL_MAX = 100
KP = 55                 # cuánto gira según el error
KD = 25                 # amortigua el giro según el cambio del error
VEL_BUSQUEDA = 35       # velocidad de giro cuando se pierde la línea


# ================= SIMULADOR =================

MAPA_ANCHO, MAPA_ALTO = 1400, 1000
GROSOR_LINEA = 28       # px en el mapa
RADIO_SENAL = 26        # px en el mapa

DT = 1 / 30             # segundos por paso de simulación (30 cuadros por segundo)
ESCALA_VEL = 2.0        # velocidad 100 = 200 px/s en el mapa
DIST_LLANTAS = 50       # distancia entre las llantas (px)

# Cuadro de vista de la cámara (en px del mapa, delante del robot)
CAM_CERCA, CAM_LEJOS = 40, 260          # distancia al borde cercano y al lejano
CAM_ANCHO_CERCA, CAM_ANCHO_LEJOS = 180, 340
CAM_W, CAM_H = 640, 480                 # tamaño de la imagen que recibe el cerebro

LIMITE_DESCARRILA = 45  # px: si el robot se aleja más que esto de la línea, se cuenta un descarrilamiento
