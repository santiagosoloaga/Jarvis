# jarvis_voz.py - Mini-proyecto 2: JARVIS te escucha y te habla
# Oido (Whisper) + cerebro (Ollama) + boca (Piper)

import re
import time

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

# Motor de voz:
#   "gemini" = voz humana en la nube (voz_nube.py). Si falla, cae sola a Piper.
#   "piper"  = voz local y offline (la de siempre)
MOTOR_VOZ = "gemini"
EFECTO_EN_VOZ_NUBE = False     # True = también le pone el eco "metálico"

# Pista para Whisper: palabras en inglés y nombres que suele escribir mal
PISTA_BASE = ("Español argentino. Jarvis, Habit Quest, Notion, Spotify, "
              "Discord, GitHub, Claude.")

# Detectar si hablás inglés cuesta ~2x de tiempo en Whisper. False = siempre
# español (rápido; las palabras sueltas en inglés igual las entiende).
# True = también entiende frases enteras en inglés, pero tarda más.
DETECTAR_INGLES = False

# "Gancho": si alguien (la interfaz) pone aca una funcion, se la
# llama con cada audio que JARVIS dice, para dibujar su voz.
al_reproducir = None


# ---------- OIDO: microfono -> texto ----------
def transcribir(oido, audio, pista=None, bilingue=True, **extra):
    extra.setdefault("beam_size", 1)    # búsqueda 'voraz': mucho más rápido, casi igual
    # Español por defecto; inglés solo si Whisper está bien seguro.
    # (Detectar entre TODOS los idiomas confunde frases cortas con
    # portugués o italiano, por eso acá solo aceptamos español o inglés.)
    pista = pista or PISTA_BASE
    extra.setdefault("without_timestamps", True)   # no necesitamos marcas de tiempo
    if not bilingue or not DETECTAR_INGLES:
        segmentos, _ = oido.transcribe(audio, language="es",
                                       initial_prompt=pista, **extra)
        return " ".join(s.text.strip() for s in segmentos).strip()
    segmentos, info = oido.transcribe(audio, language=None,
                                      initial_prompt=pista, **extra)
    segmentos = list(segmentos)
    print(f"  [oído] idioma detectado: {info.language} ({info.language_probability:.2f})")
    es_ingles = info.language == "en" and info.language_probability >= 0.7
    if info.language != "es" and not es_ingles:
        # Detectó otro idioma raro: lo tratamos como español
        segmentos, _ = oido.transcribe(audio, language="es",
                                       initial_prompt=pista, **extra)
        segmentos = list(segmentos)
    return " ".join(s.text.strip() for s in segmentos).strip()


def escuchar(oido):
    print("Grabando... (hablá ahora)")
    audio = sd.rec(
        int(SEGUNDOS * FRECUENCIA),
        samplerate=FRECUENCIA,
        channels=1,
        dtype="float32",
    )
    sd.wait()
    return transcribir(oido, audio[:, 0])


# ---------- CEREBRO: historial -> respuesta ----------
def pensar(historial):
    respuesta = ollama.chat(model=MODELO_LLM, messages=historial)
    return respuesta.message.content


# ---------- BOCA: texto -> parlante ----------
def sintetizar(boca, texto):
    # Fabrica el audio SIN reproducirlo. Devuelve (audio, frecuencia).
    # Separarlo sirve para preparar frases antes y tenerlas listas.
    if MOTOR_VOZ == "gemini":
        try:
            import voz_nube
            nube = voz_nube.sintetizar(texto)
        except ImportError:
            nube = None
        if nube is not None:              # si falla, sigue con Piper
            audio, fs = nube
            if EFECTO_EN_VOZ_NUBE:
                audio = efectos.efecto_voz(audio, fs)
            return audio, fs
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
    # Los recordatorios hablan desde OTRO hilo (un Timer), en cualquier
    # momento. Sin cuidado, su sd.play cortaria lo que JARVIS esta
    # diciendo. El CANDADO hace que hable uno por vez, y sd.wait()
    # deja terminar lo que ya estaba sonando antes de empezar.
    with efectos.CANDADO_AUDIO:
        sd.wait()
        if al_reproducir:
            al_reproducir(audio, fs)
        sd.play(audio, samplerate=fs)
        if esperar:
            sd.wait()


def dividir_frases(texto, minimo=40, maximo=2):
    # Parte la respuesta en 1 a 3 pedazos para hablar el primero mientras
    # se fabrica el siguiente. Los pedazos muy cortos se pegan al anterior.
    partes = re.split(r"(?<=[.!?…])\s+", texto.strip())
    frases, actual = [], ""
    for parte in partes:
        actual = (actual + " " + parte).strip()
        if len(actual) >= minimo:
            frases.append(actual)
            actual = ""
    if actual:
        if frases:
            frases[-1] += " " + actual
        else:
            frases.append(actual)
    if len(frases) > maximo:               # no gastar mas pedidos a la nube
        frases = frases[:maximo - 1] + [" ".join(frases[maximo - 1:])]
    return frases


def hablar(boca, texto):
    # Empieza a hablar la primera frase MIENTRAS fabrica la siguiente:
    # lo que tarda la voz se tapa con lo que ya esta sonando.
    inicio = time.time()
    frases = dividir_frases(texto) or [texto]
    sonido = sintetizar(boca, frases[0])
    print(f"  [tiempos] voz lista para sonar a los {time.time() - inicio:.1f} s")
    for siguiente in frases[1:]:
        reproducir(sonido, esperar=False)  # suena de fondo...
        sonido = sintetizar(boca, siguiente)   # ...mientras fabricamos la otra
    reproducir(sonido)


# ---------- PROGRAMA PRINCIPAL ----------
def main():
    print("Cargando oído y boca (la primera vez tarda)...")
    oido = WhisperModel(MODELO_WHISPER, device="cpu", compute_type="int8")
    boca = PiperVoice.load(VOZ)

    historial = [{"role": "system", "content": PERSONALIDAD}]
    hablar(boca, "Hola Santiago, ¿dime qué necesitas?")

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
