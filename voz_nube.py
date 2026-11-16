# voz_nube.py - Voz humana de JARVIS con Gemini TTS (la misma clave del .env).
#
# Piper (la voz local) es rápido y offline, pero suena a robot. Gemini TTS
# suena mucho más natural. Si algo falla (sin internet, cuota gastada...)
# devuelve None y JARVIS usa Piper solo: nunca se queda mudo.
#
# IMPORTANTE: los modelos de voz solo existen en la API "v1beta". Si el
# cliente usa la versión estable (v1) responde "Unknown name speechConfig".
#
# python voz_nube.py -> dice una frase de prueba.
# python probar_voces.py -> te deja escuchar varias voces y elegir.

import io
import os
import time
import wave

import numpy as np

# ---------- CONFIGURACION ----------
MODELO_TTS = "gemini-3.8-flash-lite-tts"   # el más rápido y barato (mismo estilo). Más expresivo: "gemini-3.8-flash-tts"
VOZ_NUBE = "Kore"                          # elegila con probar_voces.py
# Estilo: va en el campo oficial "speech_metadata" (NO se lee en voz alta).
# Probado con probar_acento.py. "" = sin estilo (voz tal cual viene).
ESTILO = "Argentine Spanish from Córdoba, with the cordobés singsong tonada"
DESCANSO_CUOTA = 300       # segundos que descansa la nube si se acaba la cuota
DESCANSO_ERROR = 60        # segundos que descansa ante cualquier otro error

_cliente = None
_descanso_hasta = 0.0


def _obtener_cliente():
    global _cliente
    if _cliente is None:
        from dotenv import load_dotenv
        from google import genai
        from google.genai import types
        load_dotenv()
        _cliente = genai.Client(
            api_key=os.environ.get("GEMINI_API_KEY"),
            http_options=types.HttpOptions(api_version="v1beta"))
    return _cliente


def _pedir_audio(texto, voz, estilo):
    from google.genai import types
    parte = {"text": texto}
    if estilo:
        parte["speech_metadata"] = {"style": estilo}
    config = types.GenerateContentConfig(
        response_modalities=["AUDIO"],
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voz))))
    respuesta = _obtener_cliente().models.generate_content(
        model=MODELO_TTS, contents=[{"role": "user", "parts": [parte]}],
        config=config)
    return respuesta.candidates[0].content.parts[0].inline_data.data


def _a_numpy(datos):
    # Puede venir como WAV o como PCM "crudo" (16 bits, mono, 24 kHz).
    if datos[:4] == b"RIFF":
        with wave.open(io.BytesIO(datos)) as archivo:
            fs = archivo.getframerate()
            audio = np.frombuffer(archivo.readframes(archivo.getnframes()),
                                  dtype=np.int16)
        return audio, fs
    return np.frombuffer(datos, dtype=np.int16), 24000


def sintetizar(texto, voz=None, estilo=None):
    """Devuelve (audio int16, frecuencia) o None si no se pudo (usar Piper)."""
    global _descanso_hasta
    if not texto.strip() or time.time() < _descanso_hasta:
        return None
    try:
        datos = _pedir_audio(texto, voz or VOZ_NUBE,
                             ESTILO if estilo is None else estilo)
        return _a_numpy(datos)
    except Exception as error:                # la nube nunca debe tumbar a JARVIS
        mensaje = str(error)
        cuota = any(p in mensaje for p in ("429", "RESOURCE_EXHAUSTED", "quota"))
        _descanso_hasta = time.time() + (DESCANSO_CUOTA if cuota else DESCANSO_ERROR)
        motivo = "cuota gastada" if cuota else mensaje[:300]
        print(f"  [voz nube] no pude ({motivo}); uso Piper un rato")
        return None


if __name__ == "__main__":
    import sounddevice as sd
    resultado = sintetizar("Hola Santiago, ¿dime qué necesitas?")
    if resultado is None:
        print("No se pudo generar la voz (mirá el mensaje de arriba).")
    else:
        sd.play(resultado[0], samplerate=resultado[1])
        sd.wait()
