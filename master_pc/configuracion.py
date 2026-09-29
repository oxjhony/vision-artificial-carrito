# Todos los valores ajustables del cerebro y del simulador.
#
# Las técnicas de visión salen únicamente de:
#   - notebook 3 (operaciones matemáticas): grises, resta, umbralización y AND lógico
#   - notebook 4 (K-Means): separación automática de piso y línea
#   - extra.py / extra2.py: GaussianBlur, Canny, erosión y dilatación con iteraciones

# ================= CEREBRO (visión) =================

# --- Preparación de la imagen (extra.py) ---
GAUSS_KERNEL = 5        # lado del kernel del filtro gaussiano (debe ser impar)

# --- Línea ---
ROI_INICIO = 0.45       # la zona de análisis empieza en el 45 % de la altura de la imagen
N_FRANJAS = 3           # la ROI se divide en franjas horizontales
PESOS_FRANJAS = [0.2, 0.3, 0.5]  # peso de cada franja en el error (de arriba hacia abajo)
MIN_PIXELES_FRANJA = 150         # píxeles de línea mínimos para aceptar una franja
FRACCION_MAX_FRANJA = 0.45       # si la máscara llena más que esto, no es una línea sino el piso
VENTANA_SEGUIMIENTO = 0.35       # fracción del ancho donde se busca la línea alrededor de la anterior
EROSION_LINEA = 1       # iteraciones de erosión  (apertura: quita puntos sueltos)
DILATACION_LINEA = 2    # iteraciones de dilatación (recompone el trazo)

# --- Calibración automática del umbral con K-Means (notebook 4) ---
KMEANS_K = 2            # dos grupos: piso y línea
KMEANS_MUESTRAS = 3000  # píxeles que se le pasan a K-Means (submuestreo, para que sea rápido)
KMEANS_CADA = 15        # recalibrar cada N cuadros
KMEANS_N_INIT = 10      # igual que en el notebook 4
KMEANS_SEMILLA = 42     # igual que en el notebook 4
UMBRAL_INICIAL = 110    # valor de arranque, antes de la primera calibración
SUAVIZADO_UMBRAL = 0.35         # 0 = no cambia nunca, 1 = salta al valor nuevo de una vez
SEPARACION_MINIMA = 25  # si los dos grupos quedan más juntos que esto, no hay línea que seguir

# --- Señales ---
DOMINANCIA_COLOR = 60   # ventaja del canal sobre los otros dos, RELATIVA al brillo (0..255)
BRILLO_MIN_SENAL = 35   # piso de brillo medido como max(R,G,B), no como gris
CIERRE_SENAL = 3        # iteraciones de dilatación→erosión para tapar las letras blancas
AREA_MIN_SENAL = 0.004  # fracción de la imagen para considerar un objeto como posible señal
# La cámara mira el piso en diagonal: la perspectiva estira el octágono y la firma
# de 8 lados no llega a la imagen. Estos umbrales verifican "mancha compacta del
# color correcto y del tamaño correcto", que es lo que la imagen sí sostiene.
# Medido contra figuras conocidas: octágono 0.92, cuadrado 0.72, triángulo 0.52,
# barra fina 0.16. La señal real del simulador da 0.71.
# Los pisos van holgados a proposito. El filtro de color ya es muy selectivo (solo
# las señales son rojas o verdes en la pista), asi que perder una señal cuesta mas
# que aceptar un candidato de mas. Medido en el simulador: compacidad 0.52..0.77,
# aspecto 0.92..1.70, llenado 0.67..0.81, nitidez 0.16..0.88.
COMPACIDAD_MIN = 0.55   # radio mínimo ÷ máximo desde el centroide (invariante a la rotación)
ASPECTO_MIN, ASPECTO_MAX = 0.45, 2.20   # ancho/alto: descarta lo claramente alargado
LLENADO_MIN, LLENADO_MAX = 0.50, 0.98   # área ÷ caja envolvente
NITIDEZ_MIN = 0.10      # fracción del borde que Canny confirma: descarta manchas difusas
# Los umbrales de Canny NO son fijos: salen del contraste que K-Means ya midio
# (separacion entre piso y linea). Con umbrales fijos, al bajar la luz los gradientes
# se encogen, Canny deja de ver el borde de la señal y la señal se pierde.
CANNY_MINIMO = 30       # piso del umbral alto, para no disparar Canny con ruido
SENAL_Y_CERCA = 0.5     # la señal está "cerca" cuando su centro pasa de la mitad de la imagen hacia abajo
CUADROS_CONFIRMAR = 3   # cuadros seguidos viendo la señal antes de reaccionar

# --- Comportamiento ---
TIEMPO_PARE = 3.0       # segundos detenido ante PARE (lo define el docente)

# --- Control de las llantas (escala -100 a 100) ---
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
