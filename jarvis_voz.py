# jarvis_voz.py - Mini-proyecto 2: JARVIS te escucha y te habla
# Oido (Whisper) + cerebro (Ollama) + boca (Piper)

import numpy as np
import ollama
import sounddevice as sd
from faster_whisper import WhisperModel
from piper import PiperVoice

# ---------- CONFIGURACION ----------
MODELO_LLM = "llama3.2:3b"
MODELO_WHISPER = "small"       # si va lento, proba "base"
VOZ = "es_AR-daniela-high.onnx"
FRECUENCIA = 16000             # muestras por segundo del microfono
SEGUNDOS = 5                   # cuanto tiempo graba cada vez

PERSONALIDAD = (
    "Sos JARVIS, el asistente personal de Santiago. "
    "Respondés en español rioplatense, en una o dos frases. "
    "Tu respuesta se va a leer en voz alta: "
    "no uses emojis, asteriscos, listas ni símbolos."
)


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
def hablar(boca, texto):
    pedazos = list(boca.synthesize(texto))
    if not pedazos:
        return
    audio = np.concatenate([p.audio_int16_array for p in pedazos])
    sd.play(audio, samplerate=pedazos[0].sample_rate)
    sd.wait()


# ---------- PROGRAMA PRINCIPAL ----------
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