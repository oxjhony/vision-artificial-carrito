# Pestaña de la cámara: conecta el robot por Bluetooth y una cámara (del computador o del celular),
# pasa cada imagen por el Cerebro y envía al mBot el comando que decide.

import math
import re
import sys
import threading
import time
import tkinter as tk
import urllib.request

import cv2
import numpy as np

from cerebro import Cerebro, dibujar_cerebro
from configuracion import CAM_H, CAM_W
from Robot import Robot
from vista_tk import mostrar

MAC_POR_DEFECTO = "00:1B:10:21:2C:1B"
FUENTE_POR_DEFECTO = "Camara0"

VERDE = "#1e9e3a"
ROJO = "#d93025"
NARANJA = "#e37400"
AZUL = "#1a73e8"
GRIS = "#5f6368"

# Letra que entiende el firmware del mBot para cada acción del cerebro
LETRAS = {"ADELANTE": "w", "IZQUIERDA": "a", "DERECHA": "d"}
ENVIAR = {"w": Robot.adelante, "s": Robot.atras, "a": Robot.izquierda, "d": Robot.derecha, "x": Robot.parar}


def interpretar_fuente(texto):
    # "Camara0", "cámara 1"... -> número de cámara del computador; cualquier otra cosa -> URL
    texto = texto.strip()
    numero = re.fullmatch(r"c[aá]mara\s*(\d+)", texto, re.IGNORECASE)
    return int(numero.group(1)) if numero else texto


def abrir_captura(fuente):
    if isinstance(fuente, int) and sys.platform == "win32":
        return cv2.VideoCapture(fuente, cv2.CAP_DSHOW)
    return cv2.VideoCapture(fuente)


def droidcam_ocupado(url):
    # DroidCam atiende a un solo cliente: si ya hay otro, responde una página "DroidCam is Busy"
    try:
        with urllib.request.urlopen(url, timeout=3) as respuesta:
            if "text/html" not in respuesta.headers.get("Content-Type", ""):
                return False    # es el video, no una página
            return b"droidcam_busy" in respuesta.read()
    except (OSError, ValueError):
        return False


def letra_de_comando(comando):
    if comando["izq"] == 0 and comando["der"] == 0:
        return "x"
    return LETRAS.get(comando["accion"], "w")


# ================= Conexiones (cada una en su propio hilo) =================

class ConexionRobot:
    """Conecta con el mBot y le envía continuamente el último comando (unos 10 por segundo)."""

    def __init__(self):
        self.estado = ("Sin conectar", GRIS)
        self.fase = "libre"          # libre / conectando / conectado
        self.comando = "x"
        self._activo = False
        self._perdida = False

    def conectar(self, mac):
        self.fase = "conectando"
        self.estado = ("Conectando...", AZUL)
        threading.Thread(target=self._trabajar, args=(mac,), daemon=True).start()

    def desconectar(self):
        self._activo = False

    def _trabajar(self, mac):
        robot = Robot(mac)

        try:
            robot.conectar()
        except Exception as error:
            print(f"Error al conectar con {mac}: {error}")
            self.estado = (f"Falló: no se pudo conectar con {mac}. Revisa que el robot esté encendido "
                           f"y emparejado, y que la MAC sea correcta.", ROJO)
            self.fase = "libre"
            return

        self._activo, self._perdida = True, False
        self.estado = ("Conectado", VERDE)
        self.fase = "conectado"
        threading.Thread(target=self._escuchar, args=(robot.bluetooth_socket,), daemon=True).start()

        # Enviar el comando actual; "x" solo se repite si cambia, para no llenar el canal
        ultimo = None
        while self._activo:
            letra = self.comando
            try:
                if letra != "x" or ultimo != "x":
                    ENVIAR[letra](robot)        # incluye una pausa de 0.1 s
                else:
                    time.sleep(0.1)
                ultimo = letra
            except OSError:
                self._activo, self._perdida = False, True

        if not self._perdida:
            try:
                robot.parar()
            except OSError:
                self._perdida = True

        robot.cerrar()
        self.estado = ("Desconectado: se perdió la conexión", NARANJA) if self._perdida else ("Desconectado", NARANJA)
        self.fase = "libre"

    def _escuchar(self, socket_bt):
        # Lee lo que responde el mBot (si no, se acumula) y detecta si se cae la conexión
        try:
            while self._activo:
                if not socket_bt.recv(1024):
                    break
        except OSError:
            pass

        if self._activo:
            self._activo, self._perdida = False, True


class ConexionCamara:
    """Lee la cámara en segundo plano y guarda siempre el cuadro más reciente."""

    def __init__(self):
        self.estado = ("Sin conectar", GRIS)
        self.fase = "libre"
        self.cuadro = None
        self.numero = 0              # cuántos cuadros se han leído (para saber si hay uno nuevo)
        self._activo = False

    def conectar(self, texto):
        self.fase = "conectando"
        self.estado = ("Conectando...", AZUL)
        threading.Thread(target=self._trabajar, args=(interpretar_fuente(texto),), daemon=True).start()

    def desconectar(self):
        self._activo = False

    def _trabajar(self, fuente):
        nombre = f"cámara {fuente} del computador" if isinstance(fuente, int) else fuente
        captura = abrir_captura(fuente)

        if not captura.isOpened():
            captura.release()
            if isinstance(fuente, str) and droidcam_ocupado(fuente):
                self.estado = ("Falló: el celular (DroidCam) está ocupado. Cierra el navegador "
                               "u otro programa que esté mostrando la cámara y vuelve a conectar.", ROJO)
            else:
                self.estado = (f"Falló: no se pudo abrir {nombre}", ROJO)
            self.fase = "libre"
            return

        self._activo = True
        self.estado = (f"Conectada: {nombre}", VERDE)
        self.fase = "conectado"
        perdida = False
        fallos = 0

        while self._activo:
            ok, cuadro = captura.read()

            if ok:
                self.cuadro = cuadro
                self.numero += 1
                fallos = 0
            else:
                fallos += 1
                if fallos >= 30:
                    perdida = True
                    break
                time.sleep(0.03)

        self._activo = False
        captura.release()
        self.cuadro = None
        self.estado = ("Desconectada: la cámara dejó de enviar imágenes", NARANJA) if perdida else ("Desconectada", NARANJA)
        self.fase = "libre"


# ================= Dibujo de las llantas =================

class VistaLlantas(tk.Canvas):
    """Dos llantas unidas por un eje que giran hacia donde va el robot, y una flecha verde (anda) o roja (para)."""

    ANGULO_GIRO = 30  # grados

    def __init__(self, padre):
        super().__init__(padre, width=340, height=220, bg="white", highlightthickness=0)
        self.angulo = 0.0
        self.objetivo = 0.0
        self.anda = False
        self.dibujar()

    def actualizar(self, letra):
        self.objetivo = {"a": -self.ANGULO_GIRO, "d": self.ANGULO_GIRO}.get(letra, 0.0)
        self.anda = letra in ("w", "s", "a", "d")

        # Giro suave hacia el ángulo objetivo
        self.angulo += (self.objetivo - self.angulo) * 0.3
        self.dibujar()

    def _rotar(self, puntos, cx, cy):
        a = math.radians(self.angulo)
        c, s = math.cos(a), math.sin(a)
        return [coord for x, y in puntos for coord in (cx + x * c - y * s, cy + x * s + y * c)]

    def dibujar(self):
        self.delete("all")
        cx, cy = 170, 88

        # Eje (la unión entre las llantas)
        self.create_line(*self._rotar([(-80, 0), (80, 0)], cx, cy), width=8, fill="#555555", capstyle="round")
        self.create_oval(cx - 9, cy - 9, cx + 9, cy + 9, fill="#555555", outline="")

        # Llantas
        for lado in (-1, 1):
            x = lado * 92
            llanta = [(x - 14, -38), (x + 14, -38), (x + 14, 38), (x - 14, 38)]
            self.create_polygon(*self._rotar(llanta, cx, cy), fill="#222222", outline="#000000")

            for y in range(-30, 31, 12):   # labrado de la llanta
                self.create_line(*self._rotar([(x - 12, y), (x + 12, y)], cx, cy), fill="#666666")

        # Flecha: verde si anda, roja si para
        color = VERDE if self.anda else ROJO
        flecha = [(170, 142), (203, 174), (184, 174), (184, 212), (156, 212), (156, 174), (137, 174)]
        self.create_polygon(*[c for p in flecha for c in p], fill=color, outline="")


# ================= Pestaña =================

def imagen_vacia(texto):
    imagen = np.full((CAM_H, CAM_W, 3), 40, np.uint8)
    (ancho, alto), _ = cv2.getTextSize(texto, cv2.FONT_HERSHEY_SIMPLEX, 1.0, 2)
    cv2.putText(imagen, texto, ((CAM_W - ancho) // 2, (CAM_H + alto) // 2),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, (200, 200, 200), 2, cv2.LINE_AA)
    return imagen


class PanelCamara(tk.Frame):
    def __init__(self, padre):
        super().__init__(padre)

        self.robot = ConexionRobot()
        self.camara = ConexionCamara()
        self.cerebro = Cerebro()
        self.inicio = time.monotonic()
        self.numero_procesado = 0
        self.letra = "x"
        self.corriendo = False
        self._tarea = None

        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        # --- Mitad izquierda: conexiones y llantas ---
        izquierda = tk.Frame(self, width=380)
        izquierda.grid(row=0, column=0, sticky="ns", padx=(8, 4), pady=8)

        self.entrada_mac, self.boton_robot, self.estado_robot = self._seccion(
            izquierda, "Robot (Bluetooth)", "MAC del mBot:", MAC_POR_DEFECTO, self._pulsar_robot)

        self.entrada_fuente, self.boton_camara, self.estado_camara = self._seccion(
            izquierda, "Cámara", "URL o Camara0, Camara1, ...:", FUENTE_POR_DEFECTO, self._pulsar_camara)

        movimiento = tk.LabelFrame(izquierda, text="Movimiento", font=("Segoe UI", 10, "bold"), padx=8, pady=6)
        movimiento.pack(fill="x", pady=(8, 0))

        self.llantas = VistaLlantas(movimiento)
        self.llantas.pack()
        self.texto_accion = tk.Label(movimiento, text="Detenido", font=("Segoe UI", 10))
        self.texto_accion.pack(pady=(4, 0))

        # Bloqueo de emergencia: el robot solo recibe "parar", decida lo que decida el cerebro
        self.bloqueado = False
        self.boton_bloqueo = tk.Button(movimiento, font=("Segoe UI", 10, "bold"), fg="white",
                                       command=self.alternar_bloqueo, takefocus=False)
        self.boton_bloqueo.pack(fill="x", pady=(6, 0), ipady=2)
        self._pintar_bloqueo()
        self.winfo_toplevel().bind("<space>", self._tecla_bloqueo, add="+")

        # --- Mitad derecha: la cámara ---
        tk.Frame(self, width=2, bg="#cccccc").grid(row=0, column=0, sticky="nse")

        derecha = tk.Frame(self)
        derecha.grid(row=0, column=1, sticky="nsew", padx=(4, 8), pady=8)

        self.pantalla = tk.Label(derecha, bg="black")
        self.pantalla.pack(expand=True)
        mostrar(self.pantalla, imagen_vacia("Sin camara"))

    def _seccion(self, padre, titulo, etiqueta, valor, accion):
        marco = tk.LabelFrame(padre, text=titulo, font=("Segoe UI", 10, "bold"), padx=8, pady=6)
        marco.pack(fill="x", pady=(0, 8))

        tk.Label(marco, text=etiqueta, anchor="w").pack(fill="x")

        fila = tk.Frame(marco)
        fila.pack(fill="x", pady=(2, 0))

        entrada = tk.Entry(fila, font=("Consolas", 10), width=28)
        entrada.insert(0, valor)
        entrada.pack(side="left", fill="x", expand=True, ipady=2)

        boton = tk.Button(fila, text="Conectar", width=12, command=accion, takefocus=False)
        boton.pack(side="left", padx=(6, 0))

        estado = tk.Label(marco, text="Sin conectar", fg=GRIS, font=("Segoe UI", 10, "bold"),
                          anchor="w", justify="left", wraplength=330)
        estado.pack(fill="x", pady=(4, 0))

        return entrada, boton, estado

    # --- Botones ---

    def _pulsar_robot(self):
        if self.robot.fase == "conectado":
            self.robot.desconectar()
        elif self.robot.fase == "libre":
            self.robot.conectar(self.entrada_mac.get().strip())

    def _pulsar_camara(self):
        if self.camara.fase == "conectado":
            self.camara.desconectar()
        elif self.camara.fase == "libre":
            self.cerebro = Cerebro()
            self.inicio = time.monotonic()
            self.camara.conectar(self.entrada_fuente.get())

    def alternar_bloqueo(self):
        self.bloqueado = not self.bloqueado
        if self.bloqueado:
            self.robot.comando = "x"
        self._pintar_bloqueo()

    def _pintar_bloqueo(self):
        if self.bloqueado:
            self.boton_bloqueo.configure(text="BLOQUEADO - Desbloquear (Espacio)",
                                         bg=ROJO, activebackground=ROJO)
        else:
            self.boton_bloqueo.configure(text="Bloquear movimiento (Espacio)", bg=GRIS, activebackground=GRIS)

    def _tecla_bloqueo(self, evento):
        # Espacio bloquea/desbloquea, salvo mientras se escribe en una casilla
        if self.corriendo and not isinstance(evento.widget, tk.Entry):
            self.alternar_bloqueo()

    # --- Ciclo de la pestaña ---

    def iniciar(self):
        if not self.corriendo:
            self.corriendo = True
            self._ciclo()

    def detener(self):
        # Al salir de la pestaña el robot se detiene, pero las conexiones se mantienen
        self.corriendo = False
        self.robot.comando = "x"
        if self._tarea is not None:
            self.after_cancel(self._tarea)
            self._tarea = None

    def liberar(self):
        self.robot.desconectar()
        self.camara.desconectar()

        # Dar tiempo a que el robot reciba "parar" antes de cerrar el programa
        limite = time.monotonic() + 1.0
        while self.robot.fase == "conectado" and time.monotonic() < limite:
            time.sleep(0.02)

    def _ciclo(self):
        if not self.corriendo:
            return

        self._actualizar_estados()

        cuadro = self.camara.cuadro
        if cuadro is None:
            if self.numero_procesado != -1:
                mostrar(self.pantalla, imagen_vacia("Sin camara"))
                self.numero_procesado = -1
            self.letra = "x"
            self.texto_accion.configure(text="Detenido (sin cámara)")

        elif self.camara.numero != self.numero_procesado:
            self.numero_procesado = self.camara.numero

            cuadro = cv2.resize(cuadro, (CAM_W, CAM_H))
            r = self.cerebro.pensar(cuadro, time.monotonic() - self.inicio)
            comando = r["comando"]

            self.letra = letra_de_comando(comando)
            mostrar(self.pantalla, dibujar_cerebro(r))

            if self.bloqueado:
                self.texto_accion.configure(text=f"BLOQUEADO (el cerebro decide '{self.letra}', se envía 'x')")
            else:
                self.texto_accion.configure(text=f"{comando['estado']}: {comando['accion']}   (envía '{self.letra}')")

        enviar = "x" if self.bloqueado else self.letra
        self.robot.comando = enviar
        self.llantas.actualizar(enviar)

        self._tarea = self.after(30, self._ciclo)

    def _actualizar_estados(self):
        for conexion, boton, etiqueta in ((self.robot, self.boton_robot, self.estado_robot),
                                         (self.camara, self.boton_camara, self.estado_camara)):
            texto, color = conexion.estado
            etiqueta.configure(text=texto, fg=color)

            if conexion.fase == "conectando":
                boton.configure(text="Conectando...", state="disabled")
            elif conexion.fase == "conectado":
                boton.configure(text="Desconectar", state="normal")
            else:
                boton.configure(text="Conectar", state="normal")
