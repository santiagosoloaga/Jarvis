# jarvis_voz.py - Mini-proyecto 2: JARVIS te escucha y te habla
# Oido (Whisper) + cerebro (Ollama) + boca (Piper)

import numpy as np
import ollama
import sounddevice as sd
from faster_whisper import WhisperModel
from piper import PiperVoice, SynthesisConfig

import efectos
from personalidad import PERSONALIDAD

# ---------- CONFIGURACION ----------
MODELO_LLM = "llama3.2:3b"
MODELO_WHISPER = "small"       # si va lento, proba "base"
VOZ = "es_AR-daniela-high.onnx"
# Voces masculinas para probar (bajalas antes con piper.download_voices):
#   "es_ES-davefx-medium.onnx"  (España)
#   "es_MX-ald-medium.onnx"     (México)
VELOCIDAD = 1.05               # >1 = mas pausado y "elegante"; <1 = rapido
FRECUENCIA = 16000             # muestras por segundo del microfono
SEGUNDOS = 5                   # cuanto tiempo graba cada vez

AJUSTES_VOZ = SynthesisConfig(length_scale=VELOCIDAD)

# "Gancho": si alguien (la interfaz) pone aca una funcion, se la
# llama con cada audio que JARVIS dice, para dibujar su voz.
al_reproducir = None


# ---------- OIDO: microfono -> texto ----------
def escuchar(oido):
    print("Grabando... (hablá ahora)")
    audio = sd.rec(
        int(SEGUNDOS * FRECUENCIA),
        samplerate=FRECUENCIA,
        channels=1,
        dtype="float32",
    )
    sd.wait()
    segmentos, info = oido.transcribe(audio[:, 0], language="es")
    return " ".join(s.text.strip() for s in segmentos).strip()


# ---------- CEREBRO: historial -> respuesta ----------
def pensar(historial):
    respuesta = ollama.chat(model=MODELO_LLM, messages=historial)
    return respuesta.message.content


# ---------- BOCA: texto -> parlante ----------
def sintetizar(boca, texto):
    # Fabrica el audio SIN reproducirlo. Devuelve (audio, frecuencia).
    # Separarlo sirve para preparar frases antes y tenerlas listas.
    pedazos = list(boca.synthesize(texto, syn_config=AJUSTES_VOZ))
    if not pedazos:
        return None
    fs = pedazos[0].sample_rate
    audio = np.concatenate([p.audio_int16_array for p in pedazos])
    return efectos.efecto_voz(audio, fs), fs


def reproducir(sonido, esperar=True):
    # esperar=False: suena "de fondo" mientras el programa sigue
    if sonido is None:
        return
    audio, fs = sonido
    if al_reproducir:
        al_reproducir(audio, fs)
    sd.play(audio, samplerate=fs)
    if esperar:
        sd.wait()


def hablar(boca, texto):
    reproducir(sintetizar(boca, texto))


# ---------- PROGRAMA PRINCIPAL ----------
def main():
    print("Cargando oído y boca (la primera vez tarda)...")
    oido = WhisperModel(MODELO_WHISPER, device="cpu", compute_type="int8")
    boca = PiperVoice.load(VOZ)

    historial = [{"role": "system", "content": PERSONALIDAD}]
    hablar(boca, "Hola Santiago, te escucho.")

    while True:
        orden = input("\nEnter = hablar | 'salir' = terminar: ")
        if orden.strip().lower() == "salir":
            hablar(boca, "Nos vemos, Santiago.")
            break

        texto = escuchar(oido)
        if not texto:
            print("No escuché nada. Probá de nuevo.")
            continue
        print("Vos:", texto)

        historial.append({"role": "user", "content": texto})
        try:
            respuesta = pensar(historial)
        except Exception as error:
            print("JARVIS: Tuve un problema:", error)
            historial.pop()
            continue

        print("JARVIS:", respuesta)
        historial.append({"role": "assistant", "content": respuesta})
        hablar(boca, respuesta)


# Solo arranca si corrés ESTE archivo.
# Si otro archivo lo importa (como jarvis_wake.py), no arranca.
if __name__ == "__main__":
    main()
