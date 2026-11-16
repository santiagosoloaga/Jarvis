# jarvis_wake.py - JARVIS manos libres, en modo conversacion
# Lo llamas por su nombre ("ey yarbis", "che Jarvis", "Jarvis, ¿que hora es?"),
# charlan todo lo que quieras, y con "Chau Jarvis" vuelve a dormir.

import string
import unicodedata
from collections import deque

import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel
from piper import PiperVoice

import cerebro
import herramientas
from jarvis_voz import hablar, PERSONALIDAD, MODELO_WHISPER, VOZ, FRECUENCIA

# ---------- CONFIGURACION ----------
# Como detecta su nombre:
#   "whisper"      = Whisper escucha en español: entiende tu pronunciacion
#   "openwakeword" = detector "Hey Jarvis" entrenado en ingles (mas liviano)
DETECTOR = "whisper"

# Formas en que Whisper puede escribir "Jarvis" segun como lo digas.
# Se buscan como pedazos de palabra: "yarbis", "y arbis", "Jarvis"...
RAICES_NOMBRE = ("jarvis", "yarvis", "yarbis", "jarbis", "arvis", "arbis",
                 "jervis", "yervis")

# Solo para DETECTOR = "openwakeword"
WAKE_WORD = "hey_jarvis"
BLOQUE = 1280              # 1280 muestras = 80 ms
UMBRAL = 0.5               # puntaje minimo para despertar (0 a 1)

# Escucha de tu voz
BLOQUE_VOZ = 1600          # 1600 muestras = 0,1 s
UMBRAL_VOLUMEN = 0.01      # volumen minimo para considerar que hablas
                           # (medido: silencio ~0.004, voz 0.01-0.07)
SILENCIO_FINAL = 1.2       # segundos callado = terminaste la frase
ESPERA_MAXIMA = 6.0        # segundos sin que empieces a hablar (despierto)
GRABACION_MAXIMA = 20.0    # corte de seguridad por frase
SILENCIOS_PARA_DORMIR = 2  # turnos seguidos sin hablar -> vuelve a dormir

PALABRAS_APAGAR = ("apagate",)


# ---------- UTILIDADES DE TEXTO ----------
def normalizar(texto):
    # "¡Chau, Jarvis!" -> "chau jarvis" (sin tildes, signos ni mayusculas)
    texto = unicodedata.normalize("NFD", texto.lower())
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    signos = string.punctuation + "¡¿"
    return " ".join(texto.translate(str.maketrans("", "", signos)).split())


def posicion_nombre(palabras):
    # Devuelve en que palabra esta "Jarvis" (o una variante), o None
    for i, palabra in enumerate(palabras):
        if any(raiz in palabra for raiz in RAICES_NOMBRE):
            return i
    return None


def buscar_llamado(texto):
    # "Ey Yarbis, ¿qué hora es?" -> (True, "que hora es")
    # "Hoy comí arroz"           -> (False, "")
    palabras = normalizar(texto).split()
    i = posicion_nombre(palabras)
    if i is None:
        return False, ""
    return True, " ".join(palabras[i + 1:])  # lo que dijiste despues


def es_despedida(texto):
    palabras = normalizar(texto).split()
    saludo = any(p in palabras for p in ("chau", "chao", "adios"))
    nombre = posicion_nombre(palabras) is not None
    return saludo and (nombre or len(palabras) == 1)


def quiere_apagar(texto):
    return any(p in normalizar(texto) for p in PALABRAS_APAGAR)


# ---------- ESCUCHAR UNA FRASE ----------
def escuchar_hasta_silencio(oido, espera_maxima=ESPERA_MAXIMA, pista=None,
                            aviso="(escuchando... habla)"):
    # Graba desde que empezas a hablar hasta que haces una pausa.
    # espera_maxima=None: espera para siempre a que hables.
    # pista: palabra que ayuda a Whisper a escribirla bien ("Jarvis").
    print(aviso)
    duracion = BLOQUE_VOZ / FRECUENCIA      # 0,1 s por bloque
    previos = deque(maxlen=3)   # 0,3 s antes de hablar (no corta la 1ra silaba)
    grabado = []
    hablo = False
    silencio = 0.0
    espera = 0.0

    with sd.InputStream(
        samplerate=FRECUENCIA, channels=1, dtype="float32",
        blocksize=BLOQUE_VOZ,
    ) as mic:
        while True:
            bloque, _ = mic.read(BLOQUE_VOZ)
            muestras = bloque[:, 0].copy()
            # Volumen = raiz del promedio de los cuadrados (RMS)
            volumen = float(np.sqrt(np.mean(muestras ** 2)))

            if volumen > UMBRAL_VOLUMEN:
                if not hablo:
                    grabado.extend(previos)  # sumamos lo de justo antes
                hablo = True
                silencio = 0.0
            elif hablo:
                silencio += duracion
            else:
                espera += duracion
                previos.append(muestras)

            if hablo:
                grabado.append(muestras)
                if silencio >= SILENCIO_FINAL:
                    break                     # terminaste la frase
                if len(grabado) * duracion >= GRABACION_MAXIMA:
                    break                     # corte de seguridad
            elif espera_maxima is not None and espera >= espera_maxima:
                return ""                     # no hablaste

    audio = np.concatenate(grabado)
    # vad_filter=True: Whisper ignora los silencios y no "inventa" texto
    segmentos, _ = oido.transcribe(
        audio, language="es", vad_filter=True, initial_prompt=pista
    )
    return " ".join(s.text.strip() for s in segmentos).strip()


# ---------- DORMIDO: esperar que lo llames ----------
def esperar_nombre_whisper(oido):
    # Escucha cada frase y se fija si dijiste "Jarvis" (como lo digas).
    # Devuelve lo que dijiste despues del nombre (puede ser "").
    while True:
        texto = escuchar_hasta_silencio(
            oido, espera_maxima=None, pista="Hey Jarvis.",
            aviso="\n(dormido) Esperando que digas 'Jarvis'...",
        )
        llamado, resto = buscar_llamado(texto)
        if llamado:
            print(f"(despierto) escuché: {texto}")
            return resto
        if texto:
            print(f"(sigo dormido) escuché: {texto}")


def esperar_wake_word(detector):
    # Version con openWakeWord ("Hey Jarvis" en ingles)
    print("\n(dormido) Esperando 'Hey Jarvis'...")
    with sd.InputStream(
        samplerate=FRECUENCIA, channels=1, dtype="int16", blocksize=BLOQUE
    ) as mic:
        while True:
            bloque, _ = mic.read(BLOQUE)
            puntaje = detector.predict(bloque[:, 0])[WAKE_WORD]
            if puntaje > UMBRAL:
                print(f"(despierto) puntaje: {puntaje:.2f}")
                detector.reset()
                return ""


# ---------- MODO CONVERSACION ----------
def responder(boca, historial, texto):
    historial.append({"role": "user", "content": texto})
    try:
        respuesta = cerebro.pensar(historial)  # Gemini u Ollama
    except Exception as error:
        print("JARVIS: Tuve un problema:", error)
        historial.pop()
        return
    print("JARVIS:", respuesta)
    historial.append({"role": "assistant", "content": respuesta})
    hablar(boca, respuesta)


def conversar(oido, boca, historial, primer_pedido=""):
    # Charla sin volver a llamarlo, hasta "Chau Jarvis".
    # Devuelve "dormir" o "apagar".
    if primer_pedido:
        texto = primer_pedido                 # "Jarvis, ¿que hora es?"
    else:
        hablar(boca, "¿Sí?")
        texto = None

    silencios = 0
    while True:
        if texto is None:
            texto = escuchar_hasta_silencio(oido)

        if not texto:
            silencios += 1
            if silencios >= SILENCIOS_PARA_DORMIR:
                hablar(boca, "Me vuelvo a dormir. Llamame cuando quieras.")
                return "dormir"
            texto = None
            continue
        silencios = 0
        print("Vos:", texto)

        if es_despedida(texto):
            hablar(boca, "Chau, Santiago. Acá estoy si me necesitás.")
            return "dormir"
        if quiere_apagar(texto):
            hablar(boca, "Me apago. Nos vemos, Santiago.")
            return "apagar"

        responder(boca, historial, texto)
        texto = None                          # a escuchar la siguiente


# ---------- PROGRAMA PRINCIPAL ----------
def main():
    print("Cargando oído y boca...")
    oido = WhisperModel(MODELO_WHISPER, device="cpu", compute_type="int8")
    boca = PiperVoice.load(VOZ)

    detector = None
    if DETECTOR == "openwakeword":
        import openwakeword.utils
        from openwakeword.model import Model
        openwakeword.utils.download_models([WAKE_WORD])
        detector = Model(wakeword_models=[WAKE_WORD],
                         inference_framework="onnx")

    # Los recordatorios se dicen en voz alta
    herramientas.avisar = lambda texto: hablar(boca, texto)

    personalidad = PERSONALIDAD + herramientas.INSTRUCCIONES
    historial = [{"role": "system", "content": personalidad}]
    hablar(boca, "Listo. Llamame por mi nombre cuando me necesites.")

    while True:
        if DETECTOR == "openwakeword":
            pedido = esperar_wake_word(detector)
        else:
            pedido = esperar_nombre_whisper(oido)
        if conversar(oido, boca, historial, pedido) == "apagar":
            break
        # "chau jarvis" o silencio -> vuelve a dormir


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nJARVIS apagado con Ctrl+C.")
