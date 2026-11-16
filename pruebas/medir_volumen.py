# medir_volumen.py - Muestra el volumen del microfono durante 10 segundos
# Sirve para elegir UMBRAL_VOLUMEN en jarvis_wake.py:
# quedate callado unos segundos y despues habla normal.

import numpy as np
import sounddevice as sd

FRECUENCIA = 16000
BLOQUE = 1600  # 0,1 s

print("Midiendo 10 segundos: primero callate, despues habla...\n")
with sd.InputStream(samplerate=FRECUENCIA, channels=1, dtype="float32",
                    blocksize=BLOQUE) as mic:
    for _ in range(100):  # 100 bloques de 0,1 s = 10 s
        bloque, _ = mic.read(BLOQUE)
        volumen = float(np.sqrt(np.mean(bloque[:, 0] ** 2)))
        barra = "#" * int(volumen * 500)
        print(f"{volumen:.4f} {barra}")

print("\nElegi un UMBRAL_VOLUMEN entre el valor en silencio y al hablar.")
