# jarvis_wake.py - Mini-proyecto 3: JARVIS se activa con "Hey Jarvis"
# Reusa el oido, el cerebro y la boca que ya escribimos en jarvis_voz.py

import sounddevice as sd
import openwakeword.utils
from openwakeword.model import Model
from faster_whisper import WhisperModel
from piper import PiperVoice

# Importamos lo que ya escribimos en jarvis_voz.py
from jarvis_voz import (
    escuchar,
    pensar,
    hablar,
    PERSONALIDAD,
    MODELO_WHISPER,
    VOZ,
    FRECUENCIA,
)

# ---------- CONFIGURACION ----------
WAKE_WORD = "hey_jarvis"   # modelo de openWakeWord ("Hey Jarvis")
BLOQUE = 1280              # 1280 muestras = 80 ms a 16.000 Hz
UMBRAL = 0.5               # puntaje minimo para despertar (0 a 1)
PALABRAS_APAGAR = ("apagate", "apágate")


# ---------- ESPERAR LA WAKE WORD ----------
def esperar_wake_word(detector):
    # Escucha en bloques de 80 ms hasta oir "Hey Jarvis"
    print("\n(dormido) Esperando 'Hey Jarvis'...")
    with sd.InputStream(
        samplerate=FRECUENCIA,
        channels=1,
        dtype="int16",      # openWakeWord espera numeros enteros
        blocksize=BLOQUE,
    ) as mic:
        while True:
            bloque, _ = mic.read(BLOQUE)        # 80 ms de audio
            puntajes = detector.predict(bloque[:, 0])
            puntaje = puntajes[WAKE_WORD]       # de 0 a 1
            if puntaje > UMBRAL:
                print(f"(despierto) puntaje: {puntaje:.2f}")
                detector.reset()   # olvida el audio anterior
                return             # al salir, se cierra el microfono


# ---------- PROGRAMA PRINCIPAL ----------
def main():
    print("Preparando el detector (la 1ra vez descarga)...")
    openwakeword.utils.download_models([WAKE_WORD])
    detector = Model(
        wakeword_models=[WAKE_WORD],
        inference_framework="onnx",
    )

    print("Cargando oído y boca...")
    oido = WhisperModel(MODELO_WHISPER, device="cpu", compute_type="int8")
    boca = PiperVoice.load(VOZ)

    historial = [{"role": "system", "content": PERSONALIDAD}]
    hablar(boca, "Listo. Decime Hey Jarvis cuando me necesites.")

    while True:
        esperar_wake_word(detector)    # 1) duerme hasta oir su nombre
        hablar(boca, "¿Sí?")           # 2) avisa que te escucha

        texto = escuchar(oido)         # 3) graba 5 segundos
        if not texto:
            hablar(boca, "No te escuché.")
            continue
        print("Vos:", texto)

        # Apagado por voz: "apagate"
        if any(p in texto.lower() for p in PALABRAS_APAGAR):
            hablar(boca, "Me apago. Nos vemos, Santiago.")
            break

        historial.append({"role": "user", "content": texto})
        try:
            respuesta = pensar(historial)  # 4) piensa
        except Exception as error:
            print("JARVIS: Tuve un problema:", error)
            historial.pop()
            continue

        print("JARVIS:", respuesta)
        historial.append({"role": "assistant", "content": respuesta})
        hablar(boca, respuesta)            # 5) responde y vuelve a dormir


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:              # Ctrl+C
        print("\nJARVIS apagado con Ctrl+C.")
