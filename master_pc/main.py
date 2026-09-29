import tkinter as tk

from camara import PanelCamara
from simulador import PanelSimulador


class Aplicacion(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Robot Seguidor de Línea")
        self.geometry("1370x680")
        self.minsize(900, 500)

        # Pestañas: ninguna seleccionada al inicio
        self.pestana = tk.StringVar(value="")
        barra = tk.Frame(self)
        barra.pack(fill="x", padx=8, pady=(8, 0))

        for texto, nombre in (("Simulación", "simulacion"), ("Cámara", "camara")):
            tk.Radiobutton(barra, text=texto, value=nombre, variable=self.pestana, indicatoron=False,
                           width=16, font=("Segoe UI", 11), command=self.cambiar_pestana,
                           takefocus=False).pack(side="left", padx=(0, 2))

        self.contenido = tk.Frame(self, relief="groove", borderwidth=2)
        self.contenido.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        # Cada panel se crea la primera vez que se abre su pestaña
        self.fabricas = {"simulacion": PanelSimulador, "camara": PanelCamara}
        self.paneles = {}
        self.actual = None

        self.protocol("WM_DELETE_WINDOW", self.cerrar)

    def cambiar_pestana(self):
        nombre = self.pestana.get()

        if self.actual is not None:
            self.actual.detener()
            self.actual.pack_forget()

        if nombre not in self.paneles:
            self.paneles[nombre] = self.fabricas[nombre](self.contenido)

        self.actual = self.paneles[nombre]
        self.actual.pack(fill="both", expand=True)
        self.actual.iniciar()

    def cerrar(self):
        for panel in self.paneles.values():
            panel.detener()
            if hasattr(panel, "liberar"):
                panel.liberar()
        self.destroy()


if __name__ == "__main__":
    Aplicacion().mainloop()
