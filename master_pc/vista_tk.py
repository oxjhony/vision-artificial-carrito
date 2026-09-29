# Utilidades para mostrar imágenes de OpenCV dentro de una ventana de tkinter.

import tkinter as tk

import cv2


def imagen_a_ppm(imagen_bgr):
    # tkinter.PhotoImage entiende el formato PPM sin librerías extra
    rgb = cv2.cvtColor(imagen_bgr, cv2.COLOR_BGR2RGB)
    alto, ancho = rgb.shape[:2]
    return b"P6 %d %d 255 " % (ancho, alto) + rgb.tobytes()


def mostrar(etiqueta, imagen_bgr):
    # Pone una imagen de OpenCV (BGR) en un tk.Label, reutilizando la misma PhotoImage
    datos = imagen_a_ppm(imagen_bgr)

    if getattr(etiqueta, "foto", None) is None:
        etiqueta.foto = tk.PhotoImage(data=datos, format="PPM")
        etiqueta.configure(image=etiqueta.foto)
    else:
        etiqueta.foto.configure(data=datos, format="PPM")
