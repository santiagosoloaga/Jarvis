# probar_acento.py - Busca la forma de lograr acento cordobés con Gemini TTS.
# Uso (desde la carpeta del proyecto):  python pruebas/probar_acento.py
#
# Paso 1: pide a Google su biblioteca de voces en español de Argentina
#         (Google recomienda elegir una voz regional en vez de dar órdenes).
# Paso 2: prueba el campo de "estilo" oficial (speech_metadata), que NO se
#         lee en voz alta como mi instrucción anterior, y reproduce cada uno.
# Mirá la duración que imprime: la frase sola dura ~4 s. Si dura mucho más,
# es que leyó la instrucción en voz alta.

import sys
from pathlib import Path

# Este script vive en pruebas/: agregamos la carpeta de arriba para poder
# importar voz_nube.py y compañía.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import os

from dotenv import load_dotenv
from google import genai
from google.genai import types

import sounddevice as sd
import voz_nube

load_dotenv()
cliente = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"),
                       http_options=types.HttpOptions(api_version="v1beta"))
MODELO = voz_nube.MODELO_TTS
TEXTO = "Hola Santiago, ¿dime qué necesitas? Ya abrí Spotify, che."

# ---------- Paso 1: biblioteca de voces ----------
print("--- Biblioteca de voces es-AR ---")
for codigo in (["es-AR"], ["es-US"]):
    try:
        respuesta = cliente.voices.list(language_code=codigo)
        voces = getattr(respuesta, "voices", None)
        if voces is None:
            voces = list(respuesta)
        print(f"{codigo}: {len(voces)} voces")
        for voz in voces[:25]:
            print("  ", str(voz).replace("\n", " ")[:220])
        if voces:
            break
    except Exception as error:
        print(f"{codigo}: no pude listar ({str(error)[:200]})")

# ---------- Paso 2: estilo oficial (speech_metadata) ----------
print("\n--- Estilos con speech_metadata ---")
config = types.GenerateContentConfig(
    response_modalities=["AUDIO"],
    speech_config=types.SpeechConfig(
        voice_config=types.VoiceConfig(
            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                voice_name=voz_nube.VOZ_NUBE))))
ESTILOS = [
    "",
    "Argentine Spanish from Córdoba, with the cordobés singsong tonada",
    "Rioplatense Argentine Spanish, casual and warm, with voseo",
]
for estilo in ESTILOS:
    parte = {"text": TEXTO}
    if estilo:
        parte["speech_metadata"] = {"style": estilo}
    try:
        r = cliente.models.generate_content(
            model=MODELO, contents=[{"role": "user", "parts": [parte]}],
            config=config)
        audio, fs = voz_nube._a_numpy(r.candidates[0].content.parts[0].inline_data.data)
        print(f"[ OK ] estilo={estilo or '(ninguno)'!r}: {len(audio) / fs:.1f} s")
        sd.play(audio, samplerate=fs)
        sd.wait()
    except Exception as error:
        print(f"[FALLA] estilo={estilo or '(ninguno)'!r}: {str(error)[:300]}")
