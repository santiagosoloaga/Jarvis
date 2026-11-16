# probar_voces.py - Escuchá varias voces de Gemini y elegí la tuya.
# Uso (desde la carpeta del proyecto):  python pruebas/probar_voces.py
# Después copiá el nombre de la que más te guste en VOZ_NUBE (voz_nube.py).

import sys
from pathlib import Path

# Este script vive en pruebas/: agregamos la carpeta de arriba para poder
# importar voz_nube.py y compañía.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import time

import sounddevice as sd

import voz_nube

FRASE = ("Hola Santiago, ¿dime qué necesitas? Ya te agendé la reunión de "
         "mañana a las diez y media, y abrí Spotify con tu playlist de "
         "Taylor Swift.")

# Mezcla de voces femeninas y masculinas para comparar
VOCES = ["Kore", "Leda", "Aoede", "Zephyr", "Callirrhoe", "Despina",
         "Puck", "Charon", "Orus", "Fenrir", "Algieba", "Achird"]

for voz in VOCES:
    print(f"\n--- {voz} ---")
    resultado = voz_nube.sintetizar(FRASE, voz=voz)
    if resultado is None:
        print("No se pudo generar (¿clave, internet o cuota?). Corto acá.")
        break
    sd.play(resultado[0], samplerate=resultado[1])
    sd.wait()
    time.sleep(0.5)

print("\nElegí la que más te gustó y ponela en VOZ_NUBE (voz_nube.py).")
