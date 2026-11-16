# prueba_boca.py - JARVIS dice una frase en voz alta
import numpy as np
import sounddevice as sd
from piper import PiperVoice

# El archivo .onnx que descargaste con piper.download_voices
VOZ = "es_AR-daniela-high.onnx"

voz = PiperVoice.load(VOZ)
frase = "Hola Santiago, soy JARVIS. Ya puedo hablar."

# Piper genera el audio en pedazos: los juntamos
pedazos = list(voz.synthesize(frase))
audio = np.concatenate([p.audio_int16_array for p in pedazos])

sd.play(audio, samplerate=pedazos[0].sample_rate)
sd.wait()  # esperamos a que termine de hablar