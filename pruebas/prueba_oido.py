# prueba_oido.py - Graba 5 segundos y los pasa a texto
import sounddevice as sd
from faster_whisper import WhisperModel

FRECUENCIA = 16000   # Whisper espera audio de 16.000 muestras/seg
SEGUNDOS = 5

# Cargamos Whisper una sola vez (la 1ra vez se descarga)
print("Cargando Whisper...")
modelo = WhisperModel("base", device="cpu", compute_type="int8")

input("Apretá Enter y hablá durante 5 segundos...")
print("Grabando...")
audio = sd.rec(
    int(SEGUNDOS * FRECUENCIA),  # cuantas muestras grabar
    samplerate=FRECUENCIA,
    channels=1,                  # mono: un solo microfono
    dtype="float32",
)
sd.wait()  # esperamos a que termine la grabacion
print("Listo. Transcribiendo...")

# audio[:, 0] = la unica columna (canal) como lista plana
segmentos, info = modelo.transcribe(audio[:, 0], language="es")
texto = " ".join(s.text.strip() for s in segmentos)
print("Escuché:", texto)