# probar_tts.py - Diagnóstico de la voz en la nube. Uso (desde la carpeta del proyecto):  python pruebas/probar_tts.py
# Lista los modelos de voz que tu clave puede usar, prueba cada uno con la API
# v1beta (la que necesitan) y reproduce el primero que funcione, con y sin la
# instrucción de acento. Muestra el error COMPLETO de lo que falle.

import sys
from pathlib import Path

# Este script vive en pruebas/: agregamos la carpeta de arriba para poder
# importar voz_nube.py y compañía.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import os

import numpy as np
import sounddevice as sd
from dotenv import load_dotenv
from google import genai
from google.genai import types

import voz_nube

load_dotenv()
cliente = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"),
                       http_options=types.HttpOptions(api_version="v1beta"))
TEXTO = "Hola Santiago, ¿dime qué necesitas? Ya abrí Spotify, che."
ACENTO = "Decilo con acento argentino cordobés, natural y cálido:"

config = types.GenerateContentConfig(
    response_modalities=["AUDIO"],
    speech_config=types.SpeechConfig(
        voice_config=types.VoiceConfig(
            prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Kore"))))

print("--- Modelos de voz disponibles para tu clave (v1beta) ---")
modelos = []
try:
    for m in cliente.models.list():
        if "tts" in m.name.lower():
            modelos.append(m.name.replace("models/", ""))
            print(" ", m.name)
except Exception as error:
    print("No pude listar los modelos:", str(error)[:300])
if not modelos:
    modelos = ["gemini-3.8-flash-lite-tts", "gemini-3.8-flash-tts",
               "gemini-3.1-flash-tts-preview", "gemini-2.5-flash-preview-tts"]
    print("  (uso la lista conocida)")

funciono = None
print("\n--- Pruebas ---")
for modelo in modelos:
    for etiqueta, texto in (("sin acento", TEXTO), ("con acento", f"{ACENTO} {TEXTO}")):
        try:
            r = cliente.models.generate_content(model=modelo, contents=texto, config=config)
            datos = r.candidates[0].content.parts[0].inline_data
            print(f"[ OK ] {modelo} ({etiqueta}): {len(datos.data)} bytes, {datos.mime_type}")
            funciono = funciono or modelo
            if etiqueta == "con acento":
                audio, fs = voz_nube._a_numpy(datos.data)
                print(f"       reproduciendo {modelo} con acento...")
                sd.play(audio, samplerate=fs)
                sd.wait()
        except Exception as error:
            print(f"[FALLA] {modelo} ({etiqueta}): {str(error)[:300]}")

if funciono:
    print(f"\nPonelo en voz_nube.py:  MODELO_TTS = \"{funciono}\"")
else:
    print("\nNingún modelo de voz funcionó con tu clave.")
