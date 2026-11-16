# jarvis_wake.py - JARVIS manos libres, en modo conversacion
# Lo llamas por su nombre ("ey yarbis", "che Jarvis", "Jarvis, ¿que hora es?"),
# charlan todo lo que quieras, y con "Chau Jarvis" vuelve a dormir.

import random
import string
import unicodedata
from collections import deque

import numpy as np
import ollama
import sounddevice as sd
from faster_whisper import WhisperModel
from piper import PiperVoice

import cerebro
import efectos
import herramientas
import personalidad
from jarvis_voz import (hablar, sintetizar, reproducir,
                        MODELO_WHISPER, VOZ, FRECUENCIA)

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

# Toques de JARVIS
PROBABILIDAD_ACUSE = 0.5   # 0 a 1: cada cuanto dice "Un momento" al pensar
PIP_AL_ESCUCHAR = True     # pip corto cuando te toca hablar
SALUDO_COMPLETO = True     # False = saludo corto, sin hora ni clima


# ---------- AVISOS PARA LA INTERFAZ ----------
# Por defecto no hace nada. interfaz.py la reemplaza por una que
# deja cada aviso en una cola, para dibujarlo en pantalla.
#   evento("estado", "escuchando") / evento("vos", texto) / ...
def evento(tipo, dato=None):
    pass


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
            evento("volumen", volumen)

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

    evento("estado", "analizando")
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
        evento("estado", "dormido")
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
    evento("estado", "dormido")
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
def responder(boca, historial, texto, frases_listas):
    historial.append({"role": "user", "content": texto})

    # "Un momento, señor" suena MIENTRAS el cerebro piensa:
    # disimula la demora en vez de sumarle tiempo.
    if random.random() < PROBABILIDAD_ACUSE:
        reproducir(random.choice(frases_listas["acuse"]), esperar=False)
    evento("estado", "pensando")

    try:
        respuesta = cerebro.pensar(historial)  # Gemini u Ollama
    except Exception as error:
        print("JARVIS: Tuve un problema:", error)
        historial.pop()
        sd.wait()
        decir(boca, personalidad.frase("error"))
        return

    print("JARVIS:", respuesta)
    evento("jarvis", respuesta)
    historial.append({"role": "assistant", "content": respuesta})
    sonido = sintetizar(boca, respuesta)  # fabrica el audio...
    sd.wait()                             # ...termina el "un momento"...
    reproducir(sonido)                    # ...y responde


def decir(boca, texto):
    # Habla y ademas avisa a la interfaz lo que dijo
    evento("jarvis", texto)
    hablar(boca, texto)


def despedirse(boca, tipo):
    # De noche tarde, JARVIS te sugiere ir a dormir
    if tipo == "despedida" and personalidad.es_trasnoche():
        decir(boca, personalidad.frase("trasnoche"))
    else:
        decir(boca, personalidad.frase(tipo))
    efectos.sonar("dormir")


def conversar(oido, boca, historial, frases_listas, primer_pedido=""):
    # Charla sin volver a llamarlo, hasta "Chau Jarvis".
    # Devuelve "dormir" o "apagar".
    efectos.sonar("despertar")
    if primer_pedido:
        texto = primer_pedido                 # "Jarvis, ¿que hora es?"
    else:
        reproducir(random.choice(frases_listas["despertar"]))
        texto = None

    silencios = 0
    while True:
        if texto is None:
            evento("estado", "escuchando")
            if PIP_AL_ESCUCHAR:
                efectos.sonar("escuchando")
            texto = escuchar_hasta_silencio(oido)

        if not texto:
            silencios += 1
            if silencios >= SILENCIOS_PARA_DORMIR:
                despedirse(boca, "reposo")
                return "dormir"
            texto = None
            continue
        silencios = 0
        print("Vos:", texto)
        evento("vos", texto)

        if es_despedida(texto):
            despedirse(boca, "despedida")
            return "dormir"
        if quiere_apagar(texto):
            despedirse(boca, "apagar")
            return "apagar"

        responder(boca, historial, texto, frases_listas)
        texto = None                          # a escuchar la siguiente


# ---------- ARRANQUE ----------
def registrar(linea):
    # Muestra una linea del arranque en la consola y en la interfaz
    print(" ", linea)
    evento("registro", linea)


def cargar(nombre, accion):
    # Ejecuta una parte del arranque y muestra [ OK ] o [FALLA]
    try:
        resultado = accion()
    except Exception as error:
        registrar(f"[FALLA] {nombre}: {str(error)[:70]}")
        return None
    registrar(f"[ OK ] {nombre}")
    return resultado


def arrancar():
    print("=" * 46)
    print("   J.A.R.V.I.S.  -  iniciando sistemas")
    print("=" * 46)
    efectos.sonar("arranque")

    oido = cargar(f"Oído (Whisper {MODELO_WHISPER})",
                  lambda: WhisperModel(MODELO_WHISPER, device="cpu",
                                       compute_type="int8"))
    boca = cargar(f"Voz ({VOZ})", lambda: PiperVoice.load(VOZ))
    if oido is None or boca is None:
        raise SystemExit("Sin oído o sin voz no puedo funcionar.")

    local = cargar("Cerebro local (Ollama)", ollama.list) is not None
    nube = True
    if cerebro.MODO != "local":
        nube = cargar("Cerebro en la nube (Gemini)",
                      cerebro.cliente) is not None
    registrar(f"[ OK ] Herramientas: {len(herramientas.HERRAMIENTAS)}")

    # Frases cortas preparadas de antemano: suenan al instante
    frases_listas = {
        tipo: [sintetizar(boca, f) for f in personalidad.todas(tipo)]
        for tipo in ("despertar", "acuse")
    }
    registrar("[ OK ] Frases precargadas")
    print("=" * 46)
    return oido, boca, frases_listas, local and nube


# ---------- PROGRAMA PRINCIPAL ----------
def main():
    oido, boca, frases_listas, sistemas_ok = arrancar()

    detector = None
    if DETECTOR == "openwakeword":
        import openwakeword.utils
        from openwakeword.model import Model
        openwakeword.utils.download_models([WAKE_WORD])
        detector = Model(wakeword_models=[WAKE_WORD],
                         inference_framework="onnx")

    # Los recordatorios se dicen en voz alta
    herramientas.avisar = lambda texto: decir(boca, texto)

    instrucciones = personalidad.PERSONALIDAD + herramientas.INSTRUCCIONES
    historial = [{"role": "system", "content": instrucciones}]

    if SALUDO_COMPLETO:
        saludo = personalidad.saludo_inicial(sistemas_ok)
    else:
        saludo = f"En línea, {personalidad.TRATAMIENTO}."
    print("JARVIS:", saludo)
    decir(boca, saludo)

    while True:
        if DETECTOR == "openwakeword":
            pedido = esperar_wake_word(detector)
        else:
            pedido = esperar_nombre_whisper(oido)
        estado = conversar(oido, boca, historial, frases_listas, pedido)
        if estado == "apagar":
            evento("estado", "apagado")
            break
        # "chau jarvis" o silencio -> vuelve a dormir


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nJARVIS apagado con Ctrl+C.")
