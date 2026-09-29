# Simulador: una pista vista desde arriba y un robot virtual que usa el mismo Cerebro que el robot real.

import time
import tkinter as tk

import cv2
import numpy as np

from cerebro import Cerebro, dibujar_cerebro
from configuracion import (
    CAM_ANCHO_CERCA, CAM_ANCHO_LEJOS, CAM_CERCA, CAM_H, CAM_LEJOS, CAM_W, DIST_LLANTAS, DT,
    ESCALA_VEL, GROSOR_LINEA, LIMITE_DESCARRILA, MAPA_ALTO, MAPA_ANCHO, RADIO_SENAL,
)
from vista_tk import mostrar


# ================= La pista =================

def recorrido_pista(n=600):
    t = np.linspace(0, 2 * np.pi, n, endpoint=False)

    # Óvalo con dos entradas hacia adentro (abajo y arriba): así hay curvas a ambos lados
    entrada_abajo = 230 * np.exp(-((t - np.pi / 2) / 0.45) ** 2)
    entrada_arriba = 170 * np.exp(-((t - 3 * np.pi / 2) / 0.5) ** 2)

    x = MAPA_ANCHO / 2 + 540 * np.cos(t)
    y = MAPA_ALTO / 2 + 360 * np.sin(t) - entrada_abajo + entrada_arriba

    return np.stack([x, y], axis=1)


def octagono(centro, radio, angulo=0.0):
    t = angulo + np.deg2rad(22.5) + 2 * np.pi * np.arange(8) / 8
    puntos = np.stack([centro[0] + radio * np.cos(t), centro[1] + radio * np.sin(t)], axis=1)
    return puntos.astype(np.int32)


def generar_pista(semilla=0):
    generador = np.random.default_rng(semilla)

    mapa = np.full((MAPA_ALTO, MAPA_ANCHO, 3), 205, np.int16)
    mapa += generador.integers(-7, 8, size=mapa.shape, dtype=np.int16)
    mapa = np.clip(mapa, 0, 255).astype(np.uint8)

    puntos = recorrido_pista()
    curva = puntos.astype(np.int32).reshape(-1, 1, 2)

    cv2.polylines(mapa, [curva], True, (25, 25, 25), GROSOR_LINEA, cv2.LINE_AA)

    # Señales al lado derecho de la línea (según el sentido de avance)
    senales = [(0.36, (35, 35, 210), "PARE"), (0.86, (40, 160, 40), "SIGA")]

    for fraccion, color, texto in senales:
        i = int(fraccion * len(puntos))
        p = puntos[i]
        tangente = puntos[(i + 1) % len(puntos)] - puntos[i - 1]
        tangente /= np.linalg.norm(tangente)
        derecha = np.array([-tangente[1], tangente[0]])

        centro = p + derecha * (GROSOR_LINEA / 2 + RADIO_SENAL + 16)
        cv2.fillPoly(mapa, [octagono(centro, RADIO_SENAL)], color, cv2.LINE_AA)

        (tw, th), _ = cv2.getTextSize(texto, cv2.FONT_HERSHEY_SIMPLEX, 0.4, 1)
        cv2.putText(mapa, texto, (int(centro[0] - tw / 2), int(centro[1] + th / 2)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1, cv2.LINE_AA)

    # Posición inicial: sobre la línea, mirando en el sentido de avance
    inicio = puntos[0]
    direccion = puntos[1] - puntos[0]
    angulo_inicio = np.arctan2(direccion[1], direccion[0])

    return mapa, puntos, (inicio[0], inicio[1], angulo_inicio)


# ================= El robot y su cámara =================

class RobotSimulado:
    def __init__(self, x, y, angulo):
        self.x, self.y, self.angulo = float(x), float(y), float(angulo)

    def vectores(self):
        adelante = np.array([np.cos(self.angulo), np.sin(self.angulo)])
        derecha = np.array([-np.sin(self.angulo), np.cos(self.angulo)])
        return np.array([self.x, self.y]), adelante, derecha

    def mover(self, izq, der, dt):
        # Tracción diferencial
        v = (izq + der) / 2 * ESCALA_VEL
        w = (izq - der) * ESCALA_VEL / DIST_LLANTAS

        self.angulo += w * dt
        self.x += v * np.cos(self.angulo) * dt
        self.y += v * np.sin(self.angulo) * dt

    def cuadro_de_vista(self):
        # Las 4 esquinas del trapecio en el mapa: lejos-izq, lejos-der, cerca-der, cerca-izq
        p, adelante, derecha = self.vectores()

        return np.float32([
            p + adelante * CAM_LEJOS - derecha * CAM_ANCHO_LEJOS / 2,
            p + adelante * CAM_LEJOS + derecha * CAM_ANCHO_LEJOS / 2,
            p + adelante * CAM_CERCA + derecha * CAM_ANCHO_CERCA / 2,
            p + adelante * CAM_CERCA - derecha * CAM_ANCHO_CERCA / 2,
        ])

    def camara(self, mapa, generador):
        esquinas_imagen = np.float32([[0, 0], [CAM_W, 0], [CAM_W, CAM_H], [0, CAM_H]])
        M = cv2.getPerspectiveTransform(self.cuadro_de_vista(), esquinas_imagen)

        imagen = cv2.warpPerspective(mapa, M, (CAM_W, CAM_H), borderValue=(205, 205, 205))

        # Ruido de cámara
        ruido = generador.normal(0, 4, imagen.shape)
        return np.clip(imagen + ruido, 0, 255).astype(np.uint8)

    def dibujar(self, img):
        p, adelante, derecha = self.vectores()

        cv2.polylines(img, [self.cuadro_de_vista().astype(np.int32)], True, (255, 200, 0), 2)

        cuerpo = cv2.boxPoints(((self.x, self.y), (60, 44), np.degrees(self.angulo)))
        cv2.fillPoly(img, [cuerpo.astype(np.int32)], (200, 120, 30))

        for lado in (-1, 1):
            centro = p + derecha * lado * DIST_LLANTAS / 2
            a = (centro - adelante * 13).astype(int)
            b = (centro + adelante * 13).astype(int)
            cv2.line(img, tuple(a), tuple(b), (20, 20, 20), 8)

        punta = (p + adelante * 35).astype(int)
        cv2.arrowedLine(img, tuple(p.astype(int)), tuple(punta), (255, 255, 255), 3, tipLength=0.4)


# ================= Simulación =================

class Simulacion:
    def __init__(self, semilla=0):
        self.mapa, self.puntos, self.pose_inicio = generar_pista(semilla)
        self.reiniciar()

    def reiniciar(self):
        self.robot = RobotSimulado(*self.pose_inicio)
        self.cerebro = Cerebro()
        self.generador = np.random.default_rng(1)
        self.t = 0.0
        self.rastro = []
        self.historial = []
        self.paradas = 0
        self.sigas = 0
        self.descarrilamientos = 0
        self.fuera = False
        self.estado_anterior = None
        self.indice_anterior = 0
        self.avance = 0          # puntos de la pista recorridos (para contar vueltas)
        self.ultimo = None

    @property
    def vueltas(self):
        return self.avance / len(self.puntos)

    def paso(self):
        # 1. Foto  2. Pensar  3. Mover
        imagen = self.robot.camara(self.mapa, self.generador)
        r = self.cerebro.pensar(imagen, self.t)
        c = r["comando"]

        self.robot.mover(c["izq"], c["der"], DT)
        self.t += DT

        # Métricas (solo el simulador conoce la pista)
        posicion = np.array([self.robot.x, self.robot.y])
        distancias = np.linalg.norm(self.puntos - posicion, axis=1)
        indice = int(distancias.argmin())
        distancia = float(distancias[indice])

        delta = (indice - self.indice_anterior + len(self.puntos) // 2) % len(self.puntos) - len(self.puntos) // 2
        self.avance += delta
        self.indice_anterior = indice

        fuera = distancia > LIMITE_DESCARRILA
        if fuera and not self.fuera:
            self.descarrilamientos += 1
        self.fuera = fuera

        if c["estado"] != self.estado_anterior:
            if c["estado"] == "PARE":
                self.paradas += 1
            if c["estado"] == "SIGA":
                self.sigas += 1
            print(f"t = {self.t:6.2f} s  ->  {c['estado']} ({c['accion']})")
            self.estado_anterior = c["estado"]

        self.rastro.append((self.robot.x, self.robot.y))
        self.historial.append({"t": self.t, "error": r["linea"]["error"], "distancia": distancia, **c})
        self.ultimo = r

        return r

    def dibujar_mapa(self):
        img = self.mapa.copy()

        if len(self.rastro) > 1:
            cv2.polylines(img, [np.array(self.rastro, np.int32)], False, (255, 120, 0), 2)

        self.robot.dibujar(img)

        textos = [
            f"tiempo {self.t:5.1f} s   vueltas {self.vueltas:4.2f}",
            f"PARE {self.paradas}   SIGA {self.sigas}   descarrilamientos {self.descarrilamientos}",
        ]
        for k, texto in enumerate(textos):
            cv2.putText(img, texto, (20, 40 + 38 * k), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 2)

        return img

    def panel(self):
        # Izquierda: pista con el robot y su cuadro de vista. Derecha: lo que ve y piensa el robot.
        mapa = self.dibujar_mapa()
        alto = CAM_H
        ancho = int(MAPA_ANCHO * alto / MAPA_ALTO)
        mapa = cv2.resize(mapa, (ancho, alto), interpolation=cv2.INTER_AREA)

        vista = dibujar_cerebro(self.ultimo) if self.ultimo else np.zeros((CAM_H, CAM_W, 3), np.uint8)

        return cv2.hconcat([mapa, vista])

    def resumen(self):
        print()
        print(f"Tiempo: {self.t:.1f} s   Vueltas: {self.vueltas:.2f}")
        print(f"Paradas en PARE: {self.paradas}   SIGA: {self.sigas}   Descarrilamientos: {self.descarrilamientos}")
        if self.historial:
            print(f"Distancia máxima a la línea: {max(h['distancia'] for h in self.historial):.1f} px")


# ================= Pestaña del simulador (dentro de la ventana principal) =================

class PanelSimulador(tk.Frame):
    """
    Muestra la simulación dentro de la ventana. Teclas (con la pestaña abierta):
      P -> pausar / continuar
      R -> reiniciar
      + / - -> más rápido / más lento
    """

    def __init__(self, padre):
        super().__init__(padre)

        self.sim = Simulacion()
        self.pausa = False
        self.velocidad = 1.0
        self.corriendo = False
        self._tarea = None

        barra = tk.Frame(self)
        barra.pack(fill="x", padx=8, pady=(8, 4))

        self.boton_pausa = tk.Button(barra, text="Pausar (P)", width=14, command=self.alternar_pausa)
        self.boton_pausa.pack(side="left", padx=(0, 4))
        tk.Button(barra, text="Reiniciar (R)", width=14, command=self.reiniciar).pack(side="left", padx=4)
        tk.Button(barra, text="Más lento (-)", width=14, command=lambda: self.cambiar_velocidad(0.5)).pack(side="left", padx=4)
        tk.Button(barra, text="Más rápido (+)", width=14, command=lambda: self.cambiar_velocidad(2)).pack(side="left", padx=4)

        self.texto_velocidad = tk.Label(barra, text="velocidad x1")
        self.texto_velocidad.pack(side="left", padx=12)

        self.pantalla = tk.Label(self, bg="black")
        self.pantalla.pack(padx=8, pady=(4, 8))

        self.winfo_toplevel().bind("<Key>", self._tecla, add="+")

    # --- Controles ---

    def alternar_pausa(self):
        self.pausa = not self.pausa
        self.boton_pausa.configure(text="Continuar (P)" if self.pausa else "Pausar (P)")

    def reiniciar(self):
        self.sim.reiniciar()

    def cambiar_velocidad(self, factor):
        self.velocidad = min(max(self.velocidad * factor, 0.25), 8)
        self.texto_velocidad.configure(text=f"velocidad x{self.velocidad:g}")

    def _tecla(self, evento):
        if not self.corriendo:
            return

        tecla = evento.char.lower()
        if tecla == "p":
            self.alternar_pausa()
        elif tecla == "r":
            self.reiniciar()
        elif tecla in ("+", "="):
            self.cambiar_velocidad(2)
        elif tecla == "-":
            self.cambiar_velocidad(0.5)

    # --- Ciclo de simulación ---

    def iniciar(self):
        if not self.corriendo:
            self.corriendo = True
            self._ciclo()

    def detener(self):
        self.corriendo = False
        if self._tarea is not None:
            self.after_cancel(self._tarea)
            self._tarea = None

    def _ciclo(self):
        if not self.corriendo:
            return

        inicio = time.monotonic()

        if not self.pausa:
            self.sim.paso()

        mostrar(self.pantalla, self.sim.panel())

        # Esperar lo necesario para ir a tiempo real (DT por paso) / velocidad
        transcurrido = time.monotonic() - inicio
        espera = max(1, int((DT / self.velocidad - transcurrido) * 1000))
        self._tarea = self.after(espera, self._ciclo)


if __name__ == "__main__":
    ventana = tk.Tk()
    ventana.title("Simulador")
    panel = PanelSimulador(ventana)
    panel.pack()
    panel.iniciar()
    ventana.mainloop()
