# Genera la pista del simulador como una imagen PNG grande, para imprimirla y probar con la cámara real.
#
#   python generar_tablero.py            -> tablero_simulacion.png (escala 4: 5600 x 4000 px)
#   python generar_tablero.py 6          -> escala 6: 8400 x 6000 px

import sys

import cv2
import numpy as np

from configuracion import GROSOR_LINEA, MAPA_ALTO, MAPA_ANCHO, RADIO_SENAL
from simulador import octagono, recorrido_pista


def generar_tablero(escala=4):
    # Mismo dibujo que generar_pista(), pero a mayor resolución y sin ruido (piso blanco para imprimir)
    alto, ancho = MAPA_ALTO * escala, MAPA_ANCHO * escala
    tablero = np.full((alto, ancho, 3), 255, np.uint8)

    puntos = recorrido_pista(n=600 * escala)
    curva = (puntos * escala).astype(np.int32).reshape(-1, 1, 2)
    cv2.polylines(tablero, [curva], True, (25, 25, 25), GROSOR_LINEA * escala, cv2.LINE_AA)

    # Señales al lado derecho de la línea (según el sentido de avance)
    senales = [(0.36, (35, 35, 210), "PARE"), (0.86, (40, 160, 40), "SIGA")]

    for fraccion, color, texto in senales:
        i = int(fraccion * len(puntos))
        p = puntos[i]
        tangente = puntos[(i + 1) % len(puntos)] - puntos[i - 1]
        tangente /= np.linalg.norm(tangente)
        derecha = np.array([-tangente[1], tangente[0]])

        centro = (p + derecha * (GROSOR_LINEA / 2 + RADIO_SENAL + 16)) * escala
        cv2.fillPoly(tablero, [octagono(centro, RADIO_SENAL * escala)], color, cv2.LINE_AA)

        tamano, grosor = 0.4 * escala, max(1, escala)
        (tw, th), _ = cv2.getTextSize(texto, cv2.FONT_HERSHEY_SIMPLEX, tamano, grosor)
        cv2.putText(tablero, texto, (int(centro[0] - tw / 2), int(centro[1] + th / 2)),
                    cv2.FONT_HERSHEY_SIMPLEX, tamano, (255, 255, 255), grosor, cv2.LINE_AA)

    # Marca de salida y sentido de avance
    inicio = puntos[0] * escala
    direccion = puntos[1] - puntos[0]
    direccion /= np.linalg.norm(direccion)
    lateral = np.array([-direccion[1], direccion[0]])
    medio = GROSOR_LINEA * escala

    cv2.line(tablero, tuple((inicio - lateral * medio).astype(int)), tuple((inicio + lateral * medio).astype(int)),
             (200, 120, 30), 3 * escala, cv2.LINE_AA)
    base = inicio + lateral * (medio + 20 * escala)
    cv2.arrowedLine(tablero, tuple(base.astype(int)), tuple((base + direccion * 60 * escala).astype(int)),
                    (200, 120, 30), 3 * escala, cv2.LINE_AA, tipLength=0.35)

    return tablero


if __name__ == "__main__":
    escala = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    tablero = generar_tablero(escala)
    cv2.imwrite("tablero_simulacion.png", tablero)
    print(f"Guardado tablero_simulacion.png ({tablero.shape[1]} x {tablero.shape[0]} px)")
