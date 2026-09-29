# Cerebro del robot: recibe una imagen de la cámara y devuelve la velocidad de las dos llantas.
# Es el mismo para el simulador y para el robot real.

import cv2
import numpy as np

from configuracion import (
    AREA_MIN_LINEA, AREA_MIN_SENAL, CUADROS_CONFIRMAR, KD, KP, N_FRANJAS, PESOS_FRANJAS,
    ROI_INICIO, ROJO_1, ROJO_2, S_MAX_LINEA, SENAL_Y_CERCA, TIEMPO_PARE, V_MAX_LINEA,
    VEL_BASE, VEL_BUSQUEDA, VEL_MAX, VERDE,
)


# ================= 1. Encontrar la línea =================

def mascara_linea(cuadro):
    suave = cv2.GaussianBlur(cuadro, (5, 5), 0)
    hsv = cv2.cvtColor(suave, cv2.COLOR_BGR2HSV)

    # Línea negra: saturación baja Y brillo bajo
    mascara = cv2.inRange(hsv, (0, 0, 0), (179, S_MAX_LINEA, V_MAX_LINEA))

    kernel = np.ones((5, 5), np.uint8)
    mascara = cv2.morphologyEx(mascara, cv2.MORPH_OPEN, kernel)
    mascara = cv2.morphologyEx(mascara, cv2.MORPH_CLOSE, kernel)

    return mascara


# ================= 2. Dirección del movimiento =================

def detectar_linea(cuadro, x_anterior=None):
    alto, ancho = cuadro.shape[:2]
    centro = ancho / 2

    mascara = mascara_linea(cuadro)

    y_inicio = int(alto * ROI_INICIO)
    alto_franja = (alto - y_inicio) // N_FRANJAS

    # De abajo hacia arriba: cada franja sigue a la de abajo
    x_referencia = centro if x_anterior is None else x_anterior
    puntos = [None] * N_FRANJAS

    for i in reversed(range(N_FRANJAS)):
        y_a = y_inicio + i * alto_franja
        franja = mascara[y_a:y_a + alto_franja]

        contornos, _ = cv2.findContours(franja, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        candidatos = []

        for contorno in contornos:
            if cv2.contourArea(contorno) < AREA_MIN_LINEA:
                continue

            m = cv2.moments(contorno)
            candidatos.append((m["m10"] / m["m00"], m["m01"] / m["m00"] + y_a))

        if candidatos:
            punto = min(candidatos, key=lambda p: abs(p[0] - x_referencia))
            puntos[i] = punto
            x_referencia = punto[0]

    resultado = {
        "encontrada": False, "error": 0.0, "x_abajo": None,
        "puntos": puntos, "mascara": mascara, "y_inicio": y_inicio, "alto_franja": alto_franja,
    }

    encontrados = [(p, w) for p, w in zip(puntos, PESOS_FRANJAS) if p is not None]

    if encontrados:
        suma_pesos = sum(w for _, w in encontrados)
        error = sum((p[0] - centro) / centro * w for p, w in encontrados) / suma_pesos

        resultado["encontrada"] = True
        resultado["error"] = float(np.clip(error, -1, 1))
        resultado["x_abajo"] = next(p[0] for p in reversed(puntos) if p is not None)

    return resultado


# ================= 3. Reconocer las señales =================

def mascaras_senales(cuadro):
    suave = cv2.GaussianBlur(cuadro, (5, 5), 0)
    hsv = cv2.cvtColor(suave, cv2.COLOR_BGR2HSV)

    rojo = cv2.bitwise_or(cv2.inRange(hsv, *ROJO_1), cv2.inRange(hsv, *ROJO_2))
    verde = cv2.inRange(hsv, *VERDE)

    kernel = np.ones((5, 5), np.uint8)
    mascaras = {}

    for nombre, mascara in (("rojo", rojo), ("verde", verde)):
        mascara = cv2.morphologyEx(mascara, cv2.MORPH_OPEN, kernel)
        mascara = cv2.morphologyEx(mascara, cv2.MORPH_CLOSE, kernel, iterations=3)
        mascaras[nombre] = mascara

    return mascaras


def es_octagono(contorno):
    envolvente = cv2.convexHull(contorno)

    area = cv2.contourArea(contorno)
    area_envolvente = cv2.contourArea(envolvente)
    perimetro = cv2.arcLength(envolvente, True)

    if area_envolvente == 0:
        return False, envolvente

    aproximado = cv2.approxPolyDP(envolvente, 0.02 * perimetro, True)

    solidez = area / area_envolvente
    circularidad = 4 * np.pi * area_envolvente / perimetro ** 2

    es = 7 <= len(aproximado) <= 9 and solidez > 0.9 and circularidad > 0.65

    return es, aproximado


def detectar_senales(cuadro):
    alto, ancho = cuadro.shape[:2]
    mascaras = mascaras_senales(cuadro)
    senales = []

    for color, mascara in mascaras.items():
        contornos, _ = cv2.findContours(mascara, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for contorno in contornos:
            if cv2.contourArea(contorno) / (alto * ancho) < AREA_MIN_SENAL:
                continue

            es, aproximado = es_octagono(contorno)

            if not es:
                continue

            m = cv2.moments(contorno)
            cy = m["m01"] / m["m00"]

            senales.append({
                "color": color,
                "aproximado": aproximado,
                "cerca": cy >= SENAL_Y_CERCA * alto,
            })

    return senales, mascaras


# ================= 4. Decisión: mover las llantas =================

class Controlador:
    def __init__(self):
        self.estado = "SIGUIENDO"
        self.error_anterior = 0.0
        self.ultimo_lado = 1            # 1 = derecha, -1 = izquierda
        self.fin_pare = 0.0
        self.ignorar_rojo = False       # True después de un PARE, hasta que el rojo salga de la vista
        self.cuadros_sin_rojo = 0
        self.siga_hasta = -1.0
        self.cuenta = {"rojo": 0, "verde": 0}

    def _comando(self, izq, der, accion):
        izq = float(np.clip(izq, -VEL_MAX, VEL_MAX))
        der = float(np.clip(der, -VEL_MAX, VEL_MAX))
        return {"izq": izq, "der": der, "accion": accion, "estado": self.estado}

    def actualizar(self, linea, senales, t):
        # 1. Señales: cuántos cuadros seguidos se ven cerca
        cerca = {s["color"] for s in senales if s["cerca"]}
        visibles = {s["color"] for s in senales}

        for color in self.cuenta:
            self.cuenta[color] = self.cuenta[color] + 1 if color in cerca else 0

        self.cuadros_sin_rojo = 0 if "rojo" in visibles else self.cuadros_sin_rojo + 1

        if self.ignorar_rojo and self.cuadros_sin_rojo >= CUADROS_CONFIRMAR:
            self.ignorar_rojo = False

        ver_pare = self.cuenta["rojo"] >= CUADROS_CONFIRMAR and not self.ignorar_rojo
        ver_siga = self.cuenta["verde"] >= CUADROS_CONFIRMAR

        # 2. PARE: quieto hasta que pase el tiempo
        if self.estado == "PARE":
            if t < self.fin_pare:
                return self._comando(0, 0, f"{self.fin_pare - t:.1f} s")

            self.estado = "SIGUIENDO"
            self.ignorar_rojo = True
            ver_pare = False

        if ver_pare:
            self.estado = "PARE"
            self.fin_pare = t + TIEMPO_PARE
            return self._comando(0, 0, f"{TIEMPO_PARE:.1f} s")

        if ver_siga:
            self.siga_hasta = t + 1.0

        # 3. Sin línea: buscarla girando hacia donde se vio por última vez
        if not linea["encontrada"]:
            self.estado = "BUSCANDO"
            giro = VEL_BUSQUEDA * self.ultimo_lado
            return self._comando(giro, -giro, "DERECHA" if self.ultimo_lado > 0 else "IZQUIERDA")

        # 4. Seguir la línea con control PD
        self.estado = "SIGA" if t < self.siga_hasta else "SIGUIENDO"

        error = linea["error"]
        cambio = error - self.error_anterior
        self.error_anterior = error

        if abs(error) > 0.05:
            self.ultimo_lado = 1 if error > 0 else -1

        giro = KP * error + KD * cambio
        base = VEL_BASE * (1 - 0.5 * abs(error))

        if abs(error) < 0.15:
            accion = "ADELANTE"
        elif error > 0:
            accion = "DERECHA"
        else:
            accion = "IZQUIERDA"

        return self._comando(base + giro, base - giro, accion)


# ================= El cerebro completo =================

class Cerebro:
    def __init__(self):
        self.controlador = Controlador()
        self.x_anterior = None

    def pensar(self, imagen, t):
        linea = detectar_linea(imagen, self.x_anterior)

        if linea["encontrada"]:
            self.x_anterior = linea["x_abajo"]

        senales, mascaras = detectar_senales(imagen)
        comando = self.controlador.actualizar(linea, senales, t)

        return {"imagen": imagen, "linea": linea, "senales": senales, "mascaras": mascaras, "comando": comando}


COLORES_ESTADO = {
    "SIGUIENDO": (0, 255, 0),
    "SIGA": (0, 255, 0),
    "PARE": (0, 0, 255),
    "BUSCANDO": (0, 200, 255),
}


def dibujar_cerebro(r):
    # Lo que "piensa" el robot, dibujado sobre la imagen de la cámara
    vista = r["imagen"].copy()
    linea, comando = r["linea"], r["comando"]
    alto, ancho = vista.shape[:2]

    y0 = linea["y_inicio"]
    cv2.rectangle(vista, (0, y0), (ancho - 1, alto - 1), (0, 255, 255), 2)

    for i in range(1, N_FRANJAS):
        y = y0 + i * linea["alto_franja"]
        cv2.line(vista, (0, y), (ancho, y), (0, 255, 255), 1)

    cv2.line(vista, (ancho // 2, y0), (ancho // 2, alto), (255, 255, 255), 1)

    puntos = [(int(p[0]), int(p[1])) for p in linea["puntos"] if p is not None]

    for p in puntos:
        cv2.circle(vista, p, 8, (255, 0, 255), -1)

    if len(puntos) > 1:
        cv2.polylines(vista, [np.array(puntos)], False, (255, 0, 255), 2)

    for s in r["senales"]:
        color = (0, 0, 255) if s["color"] == "rojo" else (0, 200, 0)
        cv2.drawContours(vista, [s["aproximado"]], -1, color, 4 if s["cerca"] else 1)
        x, y, _, _ = cv2.boundingRect(s["aproximado"])
        texto = "PARE" if s["color"] == "rojo" else "SIGA"
        cv2.putText(vista, texto + (" (cerca)" if s["cerca"] else ""), (x, max(y - 8, 70)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

    cv2.rectangle(vista, (0, 0), (ancho, 55), (0, 0, 0), -1)
    color_estado = COLORES_ESTADO.get(comando["estado"], (255, 255, 255))
    cv2.putText(vista, f"{comando['estado']}: {comando['accion']}", (10, 24),
                cv2.FONT_HERSHEY_SIMPLEX, 0.75, color_estado, 2)
    cv2.putText(vista, f"error {linea['error']:+.2f}   llanta I {comando['izq']:+.0f}   D {comando['der']:+.0f}",
                (10, 46), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)

    return vista
