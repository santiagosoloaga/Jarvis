# efectos.py - Sonidos y efecto de voz de JARVIS.
# No usa archivos de audio: los fabricamos con matematica,
# sumando ondas seno (como un sintetizador).
# python efectos.py -> escuchas todos los sonidos.

import numpy as np
import sounddevice as sd

# ---------- CONFIGURACION ----------
FS = 44100                 # muestras por segundo de los sonidos
VOLUMEN_SONIDOS = 0.2      # 0 a 1 (bajito para que no moleste)

EFECTO_VOZ = True          # False = voz "limpia", sin efecto
ECO_MS = 18                # retardo del eco en milisegundos
ECO_FUERZA = 0.35          # 0 a 1: cuanto se nota el eco


# ---------- SONIDOS ----------
def nota(frecuencia, duracion):
    # Onda seno: y(t) = sin(2*pi*f*t), mas un armonico (2f) suave
    # que le da un timbre mas "electronico".
    t = np.arange(int(FS * duracion)) / FS
    onda = (np.sin(2 * np.pi * frecuencia * t)
            + 0.3 * np.sin(2 * np.pi * 2 * frecuencia * t))
    # Envolvente: sube y baja suave en 10 ms, si no hace "clic"
    rampa = min(len(onda) // 4, int(FS * 0.01))
    envolvente = np.ones_like(onda)
    envolvente[:rampa] = np.linspace(0, 1, rampa)
    envolvente[-rampa:] = np.linspace(1, 0, rampa)
    return onda * envolvente


def melodia(frecuencias, duracion=0.07, pausa=0.02):
    # Varias notas seguidas con un silencio cortito entre ellas
    silencio = np.zeros(int(FS * pausa))
    partes = []
    for f in frecuencias:
        partes += [nota(f, duracion), silencio]
    audio = np.concatenate(partes)
    audio = audio / np.max(np.abs(audio)) * VOLUMEN_SONIDOS
    return audio.astype(np.float32)


# Frecuencias en Hz: 880 = La, 1320 = Mi (una quinta arriba)
SONIDOS = {
    "arranque": melodia([660, 880, 1100, 1320], duracion=0.06),
    "despertar": melodia([880, 1320]),          # sube: "te escucho"
    "dormir": melodia([1320, 880]),             # baja: "me duermo"
    "escuchando": melodia([1760], duracion=0.04),  # pip: "habla"
}


def sonar(nombre, esperar=True):
    sd.play(SONIDOS[nombre], samplerate=FS)
    if esperar:
        sd.wait()


# ---------- EFECTO DE VOZ ----------
def efecto_voz(audio, fs):
    # Suma una copia de la voz retrasada unos milisegundos.
    # Un eco TAN corto no se oye como eco: suena "metalico",
    # como una voz que sale de un casco o de un sistema.
    if not EFECTO_VOZ:
        return audio
    x = audio.astype(np.float32)
    retardo = int(fs * ECO_MS / 1000)
    y = x.copy()
    y[retardo:] += ECO_FUERZA * x[:-retardo]
    # Que no se pase del maximo de int16 (si no, "satura" y cruje)
    pico = np.max(np.abs(y))
    if pico > 32767:
        y *= 32767 / pico
    return y.astype(np.int16)


# ---------- PRUEBA ----------
if __name__ == "__main__":
    import time
    for nombre in SONIDOS:
        print("Sonando:", nombre)
        sonar(nombre)
        time.sleep(0.5)
