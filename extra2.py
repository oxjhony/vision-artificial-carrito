import ctypes

import cv2
import numpy as np

def nada(x):
    pass

def obtener_resolucion_pantalla():
    try:
        user32 = ctypes.windll.user32
        user32.SetProcessDPIAware()
        return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
    except Exception:
        return 1280, 720

# =========================
# Variables globales
# =========================

modo_morfologico = 0  # 0 = Dilatacion primero | 1 = Erosion primero

# =========================
# Callback Mouse
# =========================

def mouse_callback(event, x, y, flags, param):
    global modo_morfologico

    if event == cv2.EVENT_LBUTTONDOWN:

        # Checkbox 1
        if 20 <= x <= 40 and 20 <= y <= 40:
            modo_morfologico = 0

        # Checkbox 2
        if 20 <= x <= 40 and 60 <= y <= 80:
            modo_morfologico = 1

# =========================
# Camara
# =========================

cap = cv2.VideoCapture(0)

frame_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
frame_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
mosaico_w = frame_w * 2
mosaico_h = frame_h * 2

pantalla_w, pantalla_h = obtener_resolucion_pantalla()
max_w = pantalla_w - 60
max_h = pantalla_h - 120

escala = min(max_w / mosaico_w, max_h / mosaico_h, 1.0)
ventana_w = int(mosaico_w * escala)
ventana_h = int(mosaico_h * escala)

cv2.namedWindow("Vision Artificial", cv2.WINDOW_NORMAL)
cv2.resizeWindow("Vision Artificial", ventana_w, ventana_h)
cv2.setMouseCallback("Vision Artificial", mouse_callback)

# =========================
# Trackbars
# =========================

cv2.createTrackbar("Umbral Bajo", "Vision Artificial", 100, 255, nada)
cv2.createTrackbar("Umbral Alto", "Vision Artificial", 200, 255, nada)

cv2.createTrackbar("Kernel Gauss", "Vision Artificial", 5, 31, nada)

cv2.createTrackbar("Dilatar", "Vision Artificial", 1, 20, nada)
cv2.createTrackbar("Erosionar", "Vision Artificial", 1, 20, nada)

while True:

    ret, frame = cap.read()

    if not ret:
        break

    # =========================
    # Leer Trackbars
    # =========================

    bajo = cv2.getTrackbarPos("Umbral Bajo", "Vision Artificial")
    alto = cv2.getTrackbarPos("Umbral Alto", "Vision Artificial")

    kernel_gauss = cv2.getTrackbarPos("Kernel Gauss", "Vision Artificial")

    dilatacion_iter = cv2.getTrackbarPos("Dilatar", "Vision Artificial")
    erosion_iter = cv2.getTrackbarPos("Erosionar", "Vision Artificial")

    # Kernel impar
    if kernel_gauss < 1:
        kernel_gauss = 1

    if kernel_gauss % 2 == 0:
        kernel_gauss += 1

    # =========================
    # Procesamiento
    # =========================

    gris = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    gaussian = cv2.GaussianBlur(
        gris,
        (kernel_gauss, kernel_gauss),
        0
    )

    canny = cv2.Canny(
        gaussian,
        bajo,
        alto
    )

    kernel = np.ones((3,3), np.uint8)

    # =========================
    # Operaciones Morfologicas
    # =========================

    if modo_morfologico == 0:

        # Dilatacion -> Erosion
        procesada = cv2.dilate(
            canny,
            kernel,
            iterations=dilatacion_iter
        )

        procesada = cv2.erode(
            procesada,
            kernel,
            iterations=erosion_iter
        )

        texto_modo = "Modo: Dilatacion -> Erosion"

    else:

        # Erosion -> Dilatacion
        procesada = cv2.erode(
            canny,
            kernel,
            iterations=erosion_iter
        )

        procesada = cv2.dilate(
            procesada,
            kernel,
            iterations=dilatacion_iter
        )

        texto_modo = "Modo: Erosion -> Dilatacion"

    # =========================
    # Convertir a BGR
    # =========================

    gris_bgr = cv2.cvtColor(gris, cv2.COLOR_GRAY2BGR)
    gaussian_bgr = cv2.cvtColor(gaussian, cv2.COLOR_GRAY2BGR)
    canny_bgr = cv2.cvtColor(canny, cv2.COLOR_GRAY2BGR)
    procesada_bgr = cv2.cvtColor(procesada, cv2.COLOR_GRAY2BGR)

    # =========================
    # Crear Mosaico
    # =========================

    fila1 = np.hstack((
        frame,
        gris_bgr
    ))

    fila2 = np.hstack((
        gaussian_bgr,
        procesada_bgr
    ))

    salida = np.vstack((fila1, fila2))

    # =========================
    # Dibujar Checkboxes
    # =========================

    # Fondo panel
    cv2.rectangle(salida, (0,0), (450,100), (40,40,40), -1)

    # Checkbox 1
    cv2.rectangle(salida, (20,20), (40,40), (255,255,255), 2)

    if modo_morfologico == 0:
        cv2.line(salida, (20,20), (40,40), (0,255,0), 2)
        cv2.line(salida, (40,20), (20,40), (0,255,0), 2)

    cv2.putText(
        salida,
        "Dilatacion -> Erosion",
        (50,35),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (255,255,255),
        2
    )

    # Checkbox 2
    cv2.rectangle(salida, (20,60), (40,80), (255,255,255), 2)

    if modo_morfologico == 1:
        cv2.line(salida, (20,60), (40,80), (0,255,0), 2)
        cv2.line(salida, (40,60), (20,80), (0,255,0), 2)

    cv2.putText(
        salida,
        "Erosion -> Dilatacion",
        (50,75),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (255,255,255),
        2
    )

    # =========================
    # Titulos
    # =========================

    cv2.putText(
        salida,
        "Original",
        (20,130),
        cv2.FONT_HERSHEY_SIMPLEX,
        1,
        (0,255,0),
        2
    )

    cv2.putText(
        salida,
        "Grises",
        (660,130),
        cv2.FONT_HERSHEY_SIMPLEX,
        1,
        (0,255,0),
        2
    )

    cv2.putText(
        salida,
        "Gaussiano",
        (20,520),
        cv2.FONT_HERSHEY_SIMPLEX,
        1,
        (0,255,0),
        2
    )

    cv2.putText(
        salida,
        texto_modo,
        (660,520),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (0,255,0),
        2
    )

    # =========================
    # Mostrar
    # =========================

    cv2.imshow("Vision Artificial", salida)

    # Salir
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
