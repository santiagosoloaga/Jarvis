# interfaz.py - La cara de JARVIS: interfaz estilo Iron Man.
#
# Dos cosas pasan AL MISMO TIEMPO:
#   - La ventana (tkinter) redibuja 30 veces por segundo.
#   - JARVIS escucha, piensa y habla (se queda "trabado" esperando).
# Por eso JARVIS corre en otro HILO (thread). Los dos se comunican
# por una COLA: JARVIS deja avisos y la ventana los va leyendo.
#
# Teclas: F11 = pantalla completa | Esc = salir de pantalla completa

import math
import os
import queue
import threading
import time
import tkinter as tk
from collections import deque
from datetime import datetime

import numpy as np

import cerebro
import herramientas
import jarvis_voz
import jarvis_wake
import personalidad

# ---------- CONFIGURACION ----------
ANCHO, ALTO = 1100, 680
FPS = 30
FUENTE = "Consolas"
CLIMA_CADA = 600           # segundos entre consultas del clima

FONDO = "#03070c"
TENUE = "#0c3446"          # lineas de decoracion
TEXTO = "#a9e8ff"

# estado: (color, cartel, velocidad de giro de los anillos)
ESTADOS = {
    "iniciando": ("#00b7ff", "INICIANDO SISTEMAS", 2.5),
    "dormido": ("#1d6d96", "EN ESPERA", 0.4),
    "escuchando": ("#00e5ff", "ESCUCHANDO", 1.2),
    "analizando": ("#7fdcff", "ANALIZANDO VOZ", 3.0),
    "pensando": ("#ffb000", "PROCESANDO", 5.0),
    "hablando": ("#00e5ff", "RESPONDIENDO", 1.5),
    "apagado": ("#2a3540", "DESCONECTADO", 0.0),
}


# ---------- UTILIDADES ----------
def mezclar(color1, color2, t):
    # Mezcla dos colores: t=0 -> color1, t=1 -> color2.
    # tkinter no tiene transparencia: asi simulamos el "brillo".
    a = [int(color1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(color2[i:i + 2], 16) for i in (1, 3, 5)]
    c = [round(x + (y - x) * t) for x, y in zip(a, b)]
    return "#{:02x}{:02x}{:02x}".format(*c)


class Interfaz:
    def __init__(self, raiz):
        self.raiz = raiz
        self.cola = queue.Queue()      # avisos que manda JARVIS

        self.estado = "iniciando"
        self.angulo = 0.0              # giro de los anillos
        self.nivel = 0.0               # tamaño del nucleo (0 a 1)
        self.volumen_mic = 0.0
        self.hora_mic = 0.0
        self.voz = None                # (audio, fs, momento de inicio)
        self.registro = deque(maxlen=9)
        self.charla = deque(maxlen=4)
        self.clima = "consultando..."

        raiz.title("J.A.R.V.I.S.")
        raiz.configure(bg=FONDO)
        raiz.geometry(f"{ANCHO}x{ALTO}")
        self.lienzo = tk.Canvas(raiz, bg=FONDO, highlightthickness=0)
        self.lienzo.pack(fill="both", expand=True)

        raiz.bind("<F11>", lambda e: raiz.attributes(
            "-fullscreen", not raiz.attributes("-fullscreen")))
        raiz.bind("<Escape>", lambda e: raiz.attributes(
            "-fullscreen", False))
        raiz.protocol("WM_DELETE_WINDOW", self.cerrar)

    # ----- lo que se ejecuta en el HILO DE JARVIS -----
    def avisar(self, tipo, dato=None):
        # JARVIS nunca toca la ventana: solo deja el aviso en la cola
        self.cola.put((tipo, dato))

    def al_hablar(self, audio, fs):
        self.cola.put(("voz", (audio, fs, time.time())))

    # ----- lo que se ejecuta en el HILO DE LA VENTANA -----
    def leer_avisos(self):
        while True:
            try:
                tipo, dato = self.cola.get_nowait()
            except queue.Empty:
                return
            if tipo == "estado":
                self.estado = dato
                if dato == "apagado":
                    self.raiz.after(2500, self.cerrar)
            elif tipo == "volumen":
                self.volumen_mic = dato
                self.hora_mic = time.time()
            elif tipo == "voz":
                self.voz = dato
                self.estado = "hablando"
            elif tipo == "registro":
                self.registro.append(dato)
            elif tipo == "vos":
                self.charla.append(("VOS", dato))
            elif tipo == "jarvis":
                self.charla.append(("JARVIS", dato))

    def nivel_objetivo(self):
        # Que tan "grande" tiene que estar el nucleo segun el estado
        t = time.time()
        if self.estado == "hablando" and self.voz:
            audio, fs, inicio = self.voz
            i = int((t - inicio) * fs)
            ventana = audio[i:i + fs // 20]      # 50 ms de la voz
            if len(ventana) == 0:
                return 0.15
            rms = np.sqrt(np.mean(ventana.astype(np.float32) ** 2))
            return min(1.0, 0.15 + rms / 6000)
        if self.estado in ("escuchando", "dormido"):
            mic = 0.0
            if t - self.hora_mic < 0.3:          # dato reciente
                mic = min(1.0, self.volumen_mic / 0.06)
            respirar = 0.12 + 0.06 * math.sin(t * 1.5)
            return max(respirar, mic)
        if self.estado in ("pensando", "analizando"):
            return 0.35 + 0.12 * math.sin(t * 9)
        if self.estado == "iniciando":
            return 0.25 + 0.2 * math.sin(t * 4)
        return 0.05

    def animar(self):
        self.leer_avisos()
        color, cartel, velocidad = ESTADOS.get(
            self.estado, ESTADOS["dormido"])
        self.angulo = (self.angulo + velocidad * 2) % 360
        # Suavizado: nos acercamos un 25 % por cuadro al objetivo,
        # asi el nucleo no "salta" de golpe
        self.nivel += (self.nivel_objetivo() - self.nivel) * 0.25

        self.lienzo.delete("all")
        ancho = self.lienzo.winfo_width() or ANCHO
        alto = self.lienzo.winfo_height() or ALTO
        cx, cy = ancho / 2, alto / 2 - 50

        self.dibujar_reactor(cx, cy, color)
        self.lienzo.create_text(
            cx, cy + 215, text=cartel, fill=color,
            font=(FUENTE, 15, "bold"))
        self.dibujar_titulo()
        self.dibujar_registro(alto)
        self.dibujar_datos(ancho)
        self.dibujar_charla(ancho, alto)

        self.raiz.after(1000 // FPS, self.animar)

    # ----- dibujos -----
    def dibujar_reactor(self, cx, cy, color):
        c = self.lienzo
        # Marcas del dial (como un reloj): 72 rayitas, 1 larga cada 6
        for i in range(72):
            a = math.radians(i * 5)
            r1 = 168 if i % 6 == 0 else 178
            c.create_line(cx + r1 * math.cos(a), cy + r1 * math.sin(a),
                          cx + 186 * math.cos(a), cy + 186 * math.sin(a),
                          fill=TENUE, width=2)
        # Anillo exterior: 3 arcos que giran
        r = 155
        for k in range(3):
            c.create_arc(cx - r, cy - r, cx + r, cy + r,
                         start=self.angulo + k * 120, extent=75,
                         style="arc", outline=color, width=4)
        # Anillo medio: 6 arcos que giran al reves
        r = 132
        for k in range(6):
            c.create_arc(cx - r, cy - r, cx + r, cy + r,
                         start=-self.angulo * 1.6 + k * 60, extent=30,
                         style="arc", outline=mezclar(color, FONDO, 0.4),
                         width=2)
        # Circulo fino fijo
        r = 112
        c.create_oval(cx - r, cy - r, cx + r, cy + r,
                      outline=mezclar(color, FONDO, 0.7))
        # Nucleo: varios circulos cada vez mas oscuros = "brillo"
        radio = 35 + 55 * self.nivel
        for i, apagado in enumerate((0.85, 0.7, 0.5, 0.25)):
            r = radio * (1.5 - i * 0.15)
            c.create_oval(cx - r, cy - r, cx + r, cy + r,
                          outline=mezclar(color, FONDO, apagado), width=2)
        r = radio * 0.55
        c.create_oval(cx - r, cy - r, cx + r, cy + r,
                      fill=mezclar(color, "#ffffff", 0.3), outline="")

    def esquinas(self, x1, y1, x2, y2, largo=14):
        # Corchetes en las esquinas de un panel (detalle "HUD")
        for x, y, dx, dy in ((x1, y1, 1, 1), (x2, y1, -1, 1),
                             (x1, y2, 1, -1), (x2, y2, -1, -1)):
            self.lienzo.create_line(x, y, x + dx * largo, y,
                                    fill=TENUE, width=2)
            self.lienzo.create_line(x, y, x, y + dy * largo,
                                    fill=TENUE, width=2)

    def dibujar_titulo(self):
        self.lienzo.create_text(
            30, 28, anchor="w", text="J.A.R.V.I.S.", fill=TEXTO,
            font=(FUENTE, 24, "bold"))
        self.lienzo.create_text(
            32, 56, anchor="w", fill=TENUE, font=(FUENTE, 10),
            text="ASISTENTE PERSONAL  //  PROYECTO SANTIAGO")

    def dibujar_registro(self, alto):
        x, y = 30, 100
        self.esquinas(x - 10, y - 12, x + 290, y + 215)
        self.lienzo.create_text(x, y, anchor="nw", fill=TENUE,
                                font=(FUENTE, 10, "bold"),
                                text="REGISTRO DEL SISTEMA")
        for i, linea in enumerate(self.registro):
            color = "#ff5a5a" if "FALLA" in linea else TEXTO
            self.lienzo.create_text(
                x, y + 24 + i * 20, anchor="nw", fill=color,
                font=(FUENTE, 9), text=linea[:40])

    def dibujar_datos(self, ancho):
        x, y = ancho - 290, 100
        self.esquinas(x - 10, y - 12, x + 270, y + 280)
        ahora = datetime.now()
        filas = [
            ("HORA", ahora.strftime("%H:%M:%S"), 22),
            ("FECHA", personalidad.fecha_hablada(ahora).upper(), 11),
            ("CLIMA", self.clima, 10),
            ("CEREBRO", cerebro.ultimo_cerebro, 10),
            ("ÚLTIMA ACCIÓN", herramientas.ultima_accion, 10),
        ]
        for titulo, valor, tamaño in filas:
            self.lienzo.create_text(x, y, anchor="nw", fill=TENUE,
                                    font=(FUENTE, 9, "bold"), text=titulo)
            item = self.lienzo.create_text(
                x, y + 16, anchor="nw", fill=TEXTO, width=260,
                font=(FUENTE, tamaño), text=valor)
            caja = self.lienzo.bbox(item) or (0, 0, 0, y + 16)
            y = caja[3] + 14

    def dibujar_charla(self, ancho, alto):
        y = alto - 150
        self.esquinas(20, y - 12, ancho - 20, alto - 15)
        for quien, texto in self.charla:
            color = "#ffb000" if quien == "VOS" else TEXTO
            item = self.lienzo.create_text(
                35, y, anchor="nw", fill=color, width=ancho - 80,
                font=(FUENTE, 11), text=f"{quien}: {texto[:220]}")
            caja = self.lienzo.bbox(item) or (0, 0, 0, y)
            y = caja[3] + 6

    # ----- tareas de fondo -----
    def actualizar_clima(self):
        # Otro hilo chiquito: consulta el clima sin congelar la ventana
        while True:
            try:
                self.clima = herramientas.obtener_clima(personalidad.CIUDAD)
            except Exception:
                self.clima = "sin conexión"
            time.sleep(CLIMA_CADA)

    def correr_jarvis(self):
        try:
            jarvis_wake.main()
        except BaseException as error:  # incluye SystemExit
            self.avisar("registro", f"[FALLA] {error}")
        self.avisar("estado", "apagado")

    def cerrar(self):
        self.raiz.destroy()
        os._exit(0)   # corta tambien el hilo de JARVIS (y el micro)

    def arrancar(self):
        # Conectamos los "ganchos": ahora los avisos llegan a la cola
        jarvis_wake.evento = self.avisar
        jarvis_voz.al_reproducir = self.al_hablar
        # daemon=True: si se cierra la ventana, el hilo muere con ella
        threading.Thread(target=self.correr_jarvis, daemon=True).start()
        threading.Thread(target=self.actualizar_clima, daemon=True).start()
        self.animar()


if __name__ == "__main__":
    raiz = tk.Tk()
    Interfaz(raiz).arrancar()
    raiz.mainloop()
