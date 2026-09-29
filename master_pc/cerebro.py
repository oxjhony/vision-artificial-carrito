# Cerebro del robot: recibe una imagen de la cámara y devuelve la velocidad de las dos llantas.
# Es el mismo para el simulador y para el robot real.
#
# ORIGEN DE CADA TÉCNICA
#
#   notebook 3 (operaciones matemáticas)
#       cv2.cvtColor(COLOR_BGR2GRAY)  escala de grises
#       cv2.subtract                  resta de imágenes (invertir máscaras, dominancia de color)
#       cv2.threshold(THRESH_BINARY)  umbralización
#       cv2.bitwise_and               operación lógica AND
#       cv2.rectangle / line / circle dibujo
#
#   notebook 4 (K-Means en imágenes)
#       KMeans(n_clusters=2)          separa piso y línea y fija el umbral solo,
#                                     en vez de dejarlo clavado en un número
#
#   extra.py / extra2.py
#       cv2.GaussianBlur              suavizado con kernel impar
#       cv2.Canny                     detección de bordes
#       cv2.erode / cv2.dilate        morfología con iteraciones (apertura y cierre a mano)
#
# NO se usa ninguna función de detección de contornos (findContours, moments,
# approxPolyDP, convexHull, contourArea, arcLength, boundingRect, morphologyEx).
# Los centroides, los perímetros y la separación de regiones se calculan con
# proyecciones y aritmética sobre las máscaras, que es lo que hacían esas funciones.

import cv2
import numpy as np
from sklearn.cluster import KMeans

from configuracion import (
    AREA_MIN_SENAL, ASPECTO_MAX, ASPECTO_MIN, BRILLO_MIN_SENAL, DOMINANCIA_COLOR,
    CANNY_MINIMO, CIERRE_SENAL, COMPACIDAD_MIN, CUADROS_CONFIRMAR, DILATACION_LINEA,
    EROSION_LINEA, FRACCION_MAX_FRANJA, GAUSS_KERNEL, KD, KMEANS_CADA, KMEANS_K,
    KMEANS_MUESTRAS, KMEANS_N_INIT, KMEANS_SEMILLA, KP, LLENADO_MAX, LLENADO_MIN,
    MIN_PIXELES_FRANJA, N_FRANJAS, NITIDEZ_MIN, PESOS_FRANJAS, ROI_INICIO, SENAL_Y_CERCA,
    SEPARACION_MINIMA, SUAVIZADO_UMBRAL, TIEMPO_PARE, UMBRAL_INICIAL, VEL_BASE,
    VEL_BUSQUEDA, VEL_MAX, VENTANA_SEGUIMIENTO,
)

KERNEL_3 = np.ones((3, 3), np.uint8)    # el mismo kernel de extra.py
KERNEL_5 = np.ones((5, 5), np.uint8)


# ================= 0. Preparar la imagen =================

def a_grises(cuadro):
    # Suavizado con kernel impar y escala de grises (extra.py + notebook 3)
    lado = GAUSS_KERNEL if GAUSS_KERNEL % 2 == 1 else GAUSS_KERNEL + 1
    suave = cv2.GaussianBlur(cuadro, (lado, lado), 0)

    return cv2.cvtColor(suave, cv2.COLOR_BGR2GRAY), suave


def invertir(mascara):
    # Resta de imágenes (notebook 3): 255 - mascara. Lo oscuro pasa a ser lo blanco.
    blanco = np.full(mascara.shape, 255, np.uint8)

    return cv2.subtract(blanco, mascara)


# ================= 1. Umbral automático con K-Means (notebook 4) =================

class CalibradorUmbral:
    """Busca el umbral que separa el piso de la línea en vez de usar un número fijo.

    El notebook 4 agrupa los colores de una imagen con K-Means. Aquí se hace lo
    mismo con los niveles de gris de la ROI y K = 2: un grupo es el piso y el otro
    la línea. El umbral queda en el punto medio entre los dos centroides, así que
    se mueve solo cuando cambia la luz del salón.

    Si los dos centroides quedan muy juntos, en la imagen no hay dos cosas
    distintas que separar: no hay línea, y conviene decirlo en vez de umbralizar
    ruido (que es como el robot terminaba siguiendo el piso entero).
    """

    def __init__(self):
        self.umbral = float(UMBRAL_INICIAL)
        self.separacion = 255.0
        self.centros = (0.0, 255.0)
        self.cuadros = 0

    def actualizar(self, gris_roi):
        if self.cuadros % KMEANS_CADA == 0:
            self._calibrar(gris_roi)

        self.cuadros += 1

        return self.umbral

    def _calibrar(self, gris_roi):
        # Igual que el notebook 4: la imagen se convierte en una tabla de píxeles
        # y se pasa a float32. Aquí solo hay un canal (gris) en vez de tres.
        valores = gris_roi.reshape((-1, 1))

        if valores.shape[0] > KMEANS_MUESTRAS:
            paso = valores.shape[0] // KMEANS_MUESTRAS
            valores = valores[::paso]

        valores = valores.astype(np.float32)

        # Si toda la ROI tiene casi el mismo gris no hay dos grupos que encontrar
        # (piso parejo, imagen tapada o sobreexpuesta). K-Means no aporta nada aquí.
        rango = float(valores.max() - valores.min())

        if rango < SEPARACION_MINIMA:
            self.centros = (float(valores.min()), float(valores.max()))
            self.separacion = rango
            return

        modelo = KMeans(n_clusters=KMEANS_K, random_state=KMEANS_SEMILLA, n_init=KMEANS_N_INIT)
        modelo.fit(valores)

        centros = np.sort(modelo.cluster_centers_.ravel())

        self.centros = (float(centros[0]), float(centros[-1]))
        self.separacion = float(centros[-1] - centros[0])

        # El umbral va en la mitad, entre el grupo oscuro y el claro
        nuevo = float(centros.mean())
        self.umbral = (1 - SUAVIZADO_UMBRAL) * self.umbral + SUAVIZADO_UMBRAL * nuevo

    @property
    def hay_dos_grupos(self):
        return self.separacion >= SEPARACION_MINIMA


# ================= 2. Encontrar la línea =================

def mascara_linea(gris, umbral):
    # Umbralización (notebook 3): lo más claro que el umbral es piso
    _, piso = cv2.threshold(gris, int(umbral), 255, cv2.THRESH_BINARY)

    # La línea es lo contrario del piso
    mascara = invertir(piso)

    # Apertura a mano (extra.py, modo "Erosion -> Dilatacion"): quita puntos sueltos
    mascara = cv2.erode(mascara, KERNEL_3, iterations=EROSION_LINEA)
    mascara = cv2.dilate(mascara, KERNEL_3, iterations=DILATACION_LINEA)

    return mascara


def centroide(franja, x_referencia, media_ventana):
    """Centroide de los píxeles blancos de una franja, sin cv2.moments.

    La proyección por columnas dice cuántos píxeles de línea hay en cada columna.
    El centroide en x es el promedio de las columnas pesado por esa cuenta, que es
    exactamente la fórmula cx = M10 / M00 de los momentos.

    Para no saltar a otro tramo de la pista, primero se mira solo una ventana
    alrededor de donde estaba la línea en la franja de abajo (recorte de ROI). Si
    ahí no aparece nada, se vuelve a mirar la franja completa.
    """
    alto, ancho = franja.shape
    columnas = franja.sum(axis=0, dtype=np.float64) / 255.0
    total_franja = columnas.sum()

    # Chequeo de cordura: una línea no puede ocupar media franja. Si la ocupa, lo
    # que se umbralizó fue el piso y seguirlo es peor que no ver nada.
    if total_franja > FRACCION_MAX_FRANJA * ancho * alto:
        return None

    ventanas = []

    if x_referencia is not None and media_ventana is not None:
        x0 = int(max(0, x_referencia - media_ventana))
        x1 = int(min(ancho, x_referencia + media_ventana + 1))
        ventanas.append((x0, x1))

    ventanas.append((0, ancho))

    for x0, x1 in ventanas:
        recorte = columnas[x0:x1]
        total = recorte.sum()

        if total < MIN_PIXELES_FRANJA:
            continue

        xs = np.arange(x0, x1, dtype=np.float64)
        cx = float((xs * recorte).sum() / total)

        filas = franja[:, x0:x1].sum(axis=1, dtype=np.float64) / 255.0
        ys = np.arange(alto, dtype=np.float64)
        cy = float((ys * filas).sum() / total)

        return cx, cy

    return None


def detectar_linea(gris, calibrador, x_anterior=None):
    alto, ancho = gris.shape
    centro = ancho / 2

    y_inicio = int(alto * ROI_INICIO)
    alto_franja = (alto - y_inicio) // N_FRANJAS

    umbral = calibrador.actualizar(gris[y_inicio:])
    mascara = mascara_linea(gris, umbral)

    resultado = {
        "encontrada": False, "error": 0.0, "x_abajo": None, "puntos": [None] * N_FRANJAS,
        "mascara": mascara, "y_inicio": y_inicio, "alto_franja": alto_franja,
        "umbral": umbral, "separacion": calibrador.separacion,
    }

    # Sin dos grupos de brillo no hay línea: el piso está parejo o la imagen se lavó
    if not calibrador.hay_dos_grupos:
        return resultado

    media_ventana = VENTANA_SEGUIMIENTO * ancho / 2
    x_referencia = centro if x_anterior is None else x_anterior
    puntos = [None] * N_FRANJAS

    # De abajo hacia arriba: cada franja sigue a la de abajo
    for i in reversed(range(N_FRANJAS)):
        y_a = y_inicio + i * alto_franja
        punto = centroide(mascara[y_a:y_a + alto_franja], x_referencia, media_ventana)

        if punto is not None:
            puntos[i] = (punto[0], punto[1] + y_a)
            x_referencia = punto[0]

    resultado["puntos"] = puntos
    encontrados = [(p, w) for p, w in zip(puntos, PESOS_FRANJAS) if p is not None]

    if encontrados:
        suma_pesos = sum(w for _, w in encontrados)
        error = sum((p[0] - centro) / centro * w for p, w in encontrados) / suma_pesos

        resultado["encontrada"] = True
        resultado["error"] = float(np.clip(error, -1, 1))
        resultado["x_abajo"] = next(p[0] for p in reversed(puntos) if p is not None)

    return resultado


# ================= 3. Reconocer las señales =================

def mascara_color(suave, canal):
    """Máscara de un color por dominancia de canal, con aritmética y lógica del notebook 3.

    Un píxel es rojo si su canal R le saca ventaja al mayor de los otros dos. Esa
    ventaja es una resta de imágenes, y pedir además que el píxel esté iluminado
    (para descartar sombras de color) es un AND lógico entre dos umbralizaciones.
    Sirve igual que HSV para este caso y sale todo del notebook 3.
    """
    azul, verde, rojo = suave[:, :, 0], suave[:, :, 1], suave[:, :, 2]

    if canal == "rojo":
        propio, otros = rojo, np.maximum(verde, azul)
    else:
        propio, otros = verde, np.maximum(rojo, azul)

    ventaja = cv2.subtract(propio, otros)

    # El brillo se mide con el canal más alto, NO con la escala de grises: en grises
    # el rojo pesa solo 0.299, así que un rojo saturado se va por debajo de cualquier
    # piso de brillo en cuanto baja la luz, y la señal se pierde.
    brillo = np.maximum(np.maximum(azul, verde), rojo)

    # Ventaja relativa al brillo del píxel, llevada a escala 0..255. Cuando baja la
    # luz, la ventaja y el brillo bajan juntos y la razón no cambia: así la máscara
    # no depende de cuánta luz haya en el salón.
    relativa = (ventaja.astype(np.float32) * 255 / np.maximum(brillo, 1))
    relativa = np.clip(relativa, 0, 255).astype(np.uint8)

    _, mascara = cv2.threshold(relativa, DOMINANCIA_COLOR, 255, cv2.THRESH_BINARY)

    _, iluminado = cv2.threshold(brillo, BRILLO_MIN_SENAL, 255, cv2.THRESH_BINARY)
    mascara = cv2.bitwise_and(mascara, iluminado)

    # Cierre a mano (extra.py, modo "Dilatacion -> Erosion"): tapa las letras blancas
    mascara = cv2.dilate(mascara, KERNEL_5, iterations=CIERRE_SENAL)
    mascara = cv2.erode(mascara, KERNEL_5, iterations=CIERRE_SENAL)

    return mascara


def tramos(bandera):
    """Inicio y fin de cada tramo contiguo de True en un vector."""
    indices = np.flatnonzero(bandera)

    if indices.size == 0:
        return []

    cortes = np.flatnonzero(np.diff(indices) > 1)
    inicios = np.concatenate(([indices[0]], indices[cortes + 1]))
    finales = np.concatenate((indices[cortes], [indices[-1]]))

    return list(zip(inicios.tolist(), (finales + 1).tolist()))


def regiones(mascara, min_pixeles):
    """Separa una máscara en regiones con proyecciones, sin detección de contornos.

    Primero se parte por columnas ocupadas y después, dentro de cada columna, por
    filas ocupadas. Dos señales lado a lado quedan en regiones distintas.
    """
    encontradas = []

    for x0, x1 in tramos(mascara.any(axis=0)):
        columna = mascara[:, x0:x1]

        for y0, y1 in tramos(columna.any(axis=1)):
            bloque = columna[y0:y1]
            pixeles = int(np.count_nonzero(bloque))

            if pixeles >= min_pixeles:
                encontradas.append({
                    "x0": x0, "x1": x1, "y0": y0, "y1": y1,
                    "pixeles": pixeles, "bloque": bloque,
                })

    return encontradas


def es_senal(region, bordes):
    """Decide si una región de color es una señal, con propiedades medidas sobre la máscara.

    IMPORTANTE, y va en el póster: la cámara mira el piso en diagonal, así que el
    octágono pintado en la pista NO llega a la imagen como un octágono. La
    perspectiva lo estira y lo inclina, y la firma de 8 lados se pierde. Se midió
    contra figuras de geometría conocida: un octágono regular da una compacidad
    radial de 0.92, pero la señal real vista por la cámara da 0.71, que es el valor
    de un cuadrado. Contar vértices aquí sería afirmar algo que la imagen no
    sostiene.

    Lo que sí se puede medir con seguridad, y basta porque en la pista los únicos
    objetos rojos y verdes son las señales:

    * compacidad radial = distancia mínima ÷ máxima del centroide al borde
      (percentiles 5 y 95 para que un píxel suelto no la arruine). Es invariante a
      la rotación: octágono 0.92, cuadrado 0.72, triángulo 0.52, barra fina 0.16.
      Rechaza cables, franjas y reflejos alargados.
    * relación de aspecto y factor de llenado: descartan lo claramente alargado.
    * nitidez: qué parte del borde confirma Canny (AND del notebook 3). Una señal
      impresa tiene un borde marcado; una mancha de color difusa, no.

    No se usa la circularidad 4·pi·A/P²: se midió que con un perímetro discreto
    depende más de la inclinación de la figura que de su forma (un cuadrado da 0.40
    y el mismo cuadrado girado 45 grados da 0.79), así que rechazaría señales
    válidas y aceptaría rombos.
    """
    bloque = region["bloque"]
    alto = region["y1"] - region["y0"]
    ancho = region["x1"] - region["x0"]

    if alto == 0 or ancho == 0:
        return False, {}

    aspecto = ancho / alto
    llenado = region["pixeles"] / (ancho * alto)

    # El marco de ceros deja que la dilatación crezca por los cuatro lados: sin él,
    # una señal pegada al borde del recorte pierde parte del anillo del borde.
    relleno = np.pad(bloque, 1)
    anillo = cv2.subtract(cv2.dilate(relleno, KERNEL_3), cv2.erode(relleno, KERNEL_3))
    perimetro = max(np.count_nonzero(anillo) / 2.0, 1.0)

    # Centroide por promedio de coordenadas y radios hasta el borde
    filas_y, filas_x = np.nonzero(bloque)
    cy, cx = filas_y.mean(), filas_x.mean()

    borde_y, borde_x = np.nonzero(anillo)
    radios = np.hypot(borde_x - 1 - cx, borde_y - 1 - cy)

    if radios.size == 0:
        return False, {}

    radio_lejos = np.percentile(radios, 95)
    compacidad = float(np.percentile(radios, 5) / radio_lejos) if radio_lejos > 0 else 0.0

    recorte_bordes = bordes[region["y0"]:region["y1"], region["x0"]:region["x1"]]
    confirmados = cv2.bitwise_and(recorte_bordes, anillo[1:-1, 1:-1])
    nitidez = np.count_nonzero(confirmados) / perimetro

    medidas = {
        "aspecto": aspecto, "llenado": llenado,
        "compacidad": compacidad, "nitidez": nitidez,
    }

    es = (ASPECTO_MIN <= aspecto <= ASPECTO_MAX
          and LLENADO_MIN <= llenado <= LLENADO_MAX
          and compacidad >= COMPACIDAD_MIN
          and nitidez >= NITIDEZ_MIN)

    return es, medidas


def detectar_senales(suave, gris, separacion):
    alto, ancho = gris.shape
    min_pixeles = AREA_MIN_SENAL * alto * ancho

    # Umbrales de Canny atados al contraste real de la escena, no fijos: cuando baja
    # la luz los gradientes se encogen y unos umbrales fijos dejarian de ver el borde.
    canny_alto = float(np.clip(separacion, CANNY_MINIMO * 2, 255))
    bordes = cv2.Canny(gris, canny_alto / 2, canny_alto)
    senales = []
    mascaras = {}

    for color in ("rojo", "verde"):
        mascara = mascara_color(suave, color)
        mascaras[color] = mascara

        for region in regiones(mascara, min_pixeles):
            es, medidas = es_senal(region, bordes)

            if not es:
                continue

            cy = (region["y0"] + region["y1"]) / 2

            senales.append({
                "color": color,
                "caja": (region["x0"], region["y0"], region["x1"], region["y1"]),
                "medidas": medidas,
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
        self.calibrador = CalibradorUmbral()
        self.x_anterior = None

    def pensar(self, imagen, t):
        gris, suave = a_grises(imagen)

        linea = detectar_linea(gris, self.calibrador, self.x_anterior)

        if linea["encontrada"]:
            self.x_anterior = linea["x_abajo"]

        senales, mascaras = detectar_senales(suave, gris, linea["separacion"])
        comando = self.controlador.actualizar(linea, senales, t)

        return {"imagen": imagen, "linea": linea, "senales": senales,
                "mascaras": mascaras, "comando": comando}


COLORES_ESTADO = {
    "SIGUIENDO": (0, 255, 0),
    "SIGA": (0, 255, 0),
    "PARE": (0, 0, 255),
    "BUSCANDO": (0, 200, 255),
}


def dibujar_cerebro(r):
    # Lo que "piensa" el robot, dibujado sobre la imagen de la cámara.
    # Solo se usan rectangle, line, circle y putText (notebook 3).
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

    for a, b in zip(puntos, puntos[1:]):
        cv2.line(vista, a, b, (255, 0, 255), 2)

    for s in r["senales"]:
        color = (0, 0, 255) if s["color"] == "rojo" else (0, 200, 0)
        x0, y0_s, x1, y1_s = s["caja"]
        cv2.rectangle(vista, (x0, y0_s), (x1, y1_s), color, 4 if s["cerca"] else 1)
        texto = "PARE" if s["color"] == "rojo" else "SIGA"
        cv2.putText(vista, texto + (" (cerca)" if s["cerca"] else ""), (x0, max(y0_s - 8, 70)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

    cv2.rectangle(vista, (0, 0), (ancho, 74), (0, 0, 0), -1)
    color_estado = COLORES_ESTADO.get(comando["estado"], (255, 255, 255))
    cv2.putText(vista, f"{comando['estado']}: {comando['accion']}", (10, 24),
                cv2.FONT_HERSHEY_SIMPLEX, 0.75, color_estado, 2)
    cv2.putText(vista, f"error {linea['error']:+.2f}   llanta I {comando['izq']:+.0f}   D {comando['der']:+.0f}",
                (10, 46), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)
    cv2.putText(vista, f"umbral K-Means {linea['umbral']:.0f}   separacion {linea['separacion']:.0f}",
                (10, 66), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)

    return vista
