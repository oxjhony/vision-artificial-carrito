import cv2
import numpy as np


VENTANA = "Vision Artificial"
modo_morfologico = 0  # 0: dilatación → erosión | 1: erosión → dilatación


def nada(valor):
    pass


def mouse_callback(event, x, y, flags, param):
    global modo_morfologico

    if event != cv2.EVENT_LBUTTONDOWN:
        return

    if 20 <= x <= 40 and 20 <= y <= 40:
        modo_morfologico = 0
    elif 20 <= x <= 40 and 60 <= y <= 80:
        modo_morfologico = 1


def poner_titulo(imagen, texto, x, y, escala=0.7):
    cv2.putText(
        imagen,
        texto,
        (x, y),
        cv2.FONT_HERSHEY_SIMPLEX,
        escala,
        (0, 255, 0),
        2,
        cv2.LINE_AA
    )


def dibujar_panel(imagen):
    ancho_panel = min(450, imagen.shape[1])

    cv2.rectangle(
        imagen,
        (0, 0),
        (ancho_panel, 100),
        (40, 40, 40),
        -1
    )

    # Opción 1
    cv2.rectangle(imagen, (20, 20), (40, 40), (255, 255, 255), 2)

    if modo_morfologico == 0:
        cv2.line(imagen, (22, 22), (38, 38), (0, 255, 0), 2)
        cv2.line(imagen, (38, 22), (22, 38), (0, 255, 0), 2)

    cv2.putText(
        imagen,
        "Dilatacion -> Erosion",
        (50, 37),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (255, 255, 255),
        2,
        cv2.LINE_AA
    )

    # Opción 2
    cv2.rectangle(imagen, (20, 60), (40, 80), (255, 255, 255), 2)

    if modo_morfologico == 1:
        cv2.line(imagen, (22, 62), (38, 78), (0, 255, 0), 2)
        cv2.line(imagen, (38, 62), (22, 78), (0, 255, 0), 2)

    cv2.putText(
        imagen,
        "Erosion -> Dilatacion",
        (50, 77),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (255, 255, 255),
        2,
        cv2.LINE_AA
    )


# =========================
# Inicializar cámara
# =========================

cap = cv2.VideoCapture(0)

if not cap.isOpened():
    raise RuntimeError("No se pudo abrir la camara.")

# Resolución solicitada
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

cv2.namedWindow(VENTANA, cv2.WINDOW_NORMAL)
cv2.setMouseCallback(VENTANA, mouse_callback)

# =========================
# Trackbars
# =========================

cv2.createTrackbar("Umbral Bajo", VENTANA, 100, 255, nada)
cv2.createTrackbar("Umbral Alto", VENTANA, 200, 255, nada)
cv2.createTrackbar("Kernel Gauss", VENTANA, 5, 31, nada)
cv2.createTrackbar("Dilatar", VENTANA, 1, 20, nada)
cv2.createTrackbar("Erosionar", VENTANA, 1, 20, nada)

try:
    while True:
        ret, frame = cap.read()

        if not ret:
            print("No se pudo leer un fotograma de la camara.")
            break

        alto_frame, ancho_frame = frame.shape[:2]

        # =========================
        # Leer controles
        # =========================

        umbral_1 = cv2.getTrackbarPos("Umbral Bajo", VENTANA)
        umbral_2 = cv2.getTrackbarPos("Umbral Alto", VENTANA)

        # Garantiza que bajo siempre sea menor o igual que alto
        umbral_bajo = min(umbral_1, umbral_2)
        umbral_alto = max(umbral_1, umbral_2)

        kernel_gauss = cv2.getTrackbarPos("Kernel Gauss", VENTANA)
        dilatacion_iter = cv2.getTrackbarPos("Dilatar", VENTANA)
        erosion_iter = cv2.getTrackbarPos("Erosionar", VENTANA)

        # GaussianBlur necesita un kernel impar y mayor que cero
        kernel_gauss = max(1, kernel_gauss)

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
            umbral_bajo,
            umbral_alto
        )

        kernel_morfologico = np.ones((3, 3), dtype=np.uint8)

        if modo_morfologico == 0:
            procesada = cv2.dilate(
                canny,
                kernel_morfologico,
                iterations=dilatacion_iter
            )

            procesada = cv2.erode(
                procesada,
                kernel_morfologico,
                iterations=erosion_iter
            )

            texto_modo = "Dilatacion -> Erosion"
        else:
            procesada = cv2.erode(
                canny,
                kernel_morfologico,
                iterations=erosion_iter
            )

            procesada = cv2.dilate(
                procesada,
                kernel_morfologico,
                iterations=dilatacion_iter
            )

            texto_modo = "Erosion -> Dilatacion"

        # =========================
        # Crear mosaico
        # =========================

        gris_bgr = cv2.cvtColor(gris, cv2.COLOR_GRAY2BGR)
        gaussian_bgr = cv2.cvtColor(gaussian, cv2.COLOR_GRAY2BGR)
        procesada_bgr = cv2.cvtColor(procesada, cv2.COLOR_GRAY2BGR)

        fila_superior = np.hstack((frame, gris_bgr))
        fila_inferior = np.hstack((gaussian_bgr, procesada_bgr))
        salida = np.vstack((fila_superior, fila_inferior))

        # =========================
        # Panel y títulos
        # =========================

        dibujar_panel(salida)

        margen_y = 130

        poner_titulo(salida, "Original", 20, margen_y)
        poner_titulo(salida, "Escala de grises", ancho_frame + 20, margen_y)

        poner_titulo(
            salida,
            "Filtro gaussiano",
            20,
            alto_frame + 40
        )

        poner_titulo(
            salida,
            texto_modo,
            ancho_frame + 20,
            alto_frame + 40,
            escala=0.65
        )

        # Información adicional
        informacion = (
            f"Canny: {umbral_bajo}-{umbral_alto} | "
            f"Gauss: {kernel_gauss} | "
            f"D: {dilatacion_iter} | E: {erosion_iter}"
        )

        cv2.putText(
            salida,
            informacion,
            (20, salida.shape[0] - 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (0, 255, 255),
            2,
            cv2.LINE_AA
        )

        cv2.imshow(VENTANA, salida)

        tecla = cv2.waitKey(1) & 0xFF

        if tecla == ord("q") or tecla == 27:
            break

finally:
    cap.release()
    cv2.destroyAllWindows()