# lanzador.py - Panel de botones para abrir JARVIS sin escribir comandos
# Usa tkinter, que viene incluido con Python (no hay que instalar nada).

import subprocess
import tkinter as tk
import urllib.request
from pathlib import Path

# Carpeta donde esta este archivo (la carpeta jarvis)
CARPETA = Path(__file__).resolve().parent
# El Python del entorno virtual: asi cada programa usa sus librerias
PYTHON = CARPETA / ".venv" / "Scripts" / "python.exe"
# En Windows, abre cada programa en su propia ventana de consola
NUEVA_CONSOLA = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)

# (texto del boton, archivo que ejecuta)
PROGRAMAS = [
    ("JARVIS con interfaz (estilo Iron Man)", "interfaz.py"),
    ("JARVIS manos libres (Hey Jarvis)", "jarvis_wake.py"),
    ("JARVIS por voz (con Enter)", "jarvis_voz.py"),
    ("Chat por texto", "jarvis_chat.py"),
    ("Probar cerebro Gemini + Ollama (texto)", "cerebro.py"),
    ("Probar herramientas solo con Ollama", "herramientas.py"),
]


def abrir(script):
    # Lanza el script en una consola nueva, parada en la carpeta jarvis.
    # "cmd /k" deja la ventana abierta al terminar: si hay un error,
    # lo podes leer (y copiarselo a Mentor) en vez de que se cierre.
    subprocess.Popen(
        ["cmd", "/k", str(PYTHON), script],
        cwd=CARPETA,
        creationflags=NUEVA_CONSOLA,
    )


def ollama_prendido():
    # Ollama atiende en localhost:11434. Si responde, esta prendido.
    try:
        urllib.request.urlopen("http://localhost:11434", timeout=1)
        return True
    except Exception:
        return False


# ---------- LA VENTANA ----------
ventana = tk.Tk()
ventana.title("JARVIS")
ventana.resizable(False, False)

tk.Label(ventana, text="JARVIS", font=("Segoe UI", 20, "bold")).pack(
    pady=(16, 2)
)
estado = tk.Label(ventana, font=("Segoe UI", 10))
estado.pack(pady=(0, 10))


def actualizar_estado():
    if ollama_prendido():
        estado.config(text="Ollama: prendido", fg="green")
    else:
        estado.config(text="Ollama: apagado (abrilo primero)", fg="red")
    ventana.after(5000, actualizar_estado)  # se revisa cada 5 segundos


# Un boton por programa.
# Ojo con "s=script": sin eso, TODOS los botones abririan el ultimo
# programa de la lista (el lambda recordaria la variable, no su valor).
for texto, script in PROGRAMAS:
    tk.Button(
        ventana,
        text=texto,
        width=34,
        font=("Segoe UI", 11),
        command=lambda s=script: abrir(s),
    ).pack(padx=16, pady=4)

# Botones de utilidad
tk.Button(
    ventana,
    text="Abrir la carpeta del proyecto",
    width=34,
    command=lambda: subprocess.Popen(["explorer", str(CARPETA)]),
).pack(padx=16, pady=(14, 4))
tk.Button(
    ventana,
    text="Abrir el proyecto en VS Code",
    width=34,
    command=lambda: subprocess.Popen("code .", cwd=CARPETA, shell=True),
).pack(padx=16, pady=(4, 16))

actualizar_estado()
ventana.mainloop()
