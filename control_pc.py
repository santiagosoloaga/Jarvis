# control_pc.py - Herramientas para controlar la compu (solo Windows)
# Volumen y musica: "apretamos" las teclas multimedia del teclado
# desde Python, como si las tocaras vos. No hace falta instalar nada.

import ctypes
import time
import urllib.parse
import webbrowser
from datetime import datetime
from pathlib import Path

# ctypes.windll solo existe en Windows (en otro sistema queda en None)
USER32 = ctypes.windll.user32 if hasattr(ctypes, "windll") else None

# Codigos de las teclas multimedia de Windows ("virtual keys")
TECLA_VOLUMEN_MUTE = 0xAD
TECLA_VOLUMEN_BAJAR = 0xAE
TECLA_VOLUMEN_SUBIR = 0xAF
TECLA_SIGUIENTE = 0xB0
TECLA_ANTERIOR = 0xB1
TECLA_PLAY_PAUSA = 0xB3
SOLTAR_TECLA = 0x0002


def apretar(tecla, veces=1):
    # Simula apretar y soltar una tecla, "veces" veces seguidas
    for _ in range(veces):
        USER32.keybd_event(tecla, 0, 0, 0)             # apretar
        USER32.keybd_event(tecla, 0, SOLTAR_TECLA, 0)  # soltar
        time.sleep(0.01)


# ---------- VOLUMEN ----------
def controlar_volumen(accion: str, porcentaje: int = 10) -> str:
    """
    Sube, baja, silencia o fija el volumen de la compu.

    Args:
        accion: Una de: subir, bajar, silenciar, fijar
        porcentaje: Cuánto subir o bajar, o a qué nivel fijarlo (0 a 100)
    """
    accion = accion.lower().strip()
    # Cada toque de tecla mueve el volumen de Windows un 2 %
    pasos = max(1, round(int(porcentaje) / 2))
    if accion == "subir":
        apretar(TECLA_VOLUMEN_SUBIR, pasos)
        return f"Subí el volumen un {porcentaje} %."
    if accion == "bajar":
        apretar(TECLA_VOLUMEN_BAJAR, pasos)
        return f"Bajé el volumen un {porcentaje} %."
    if accion == "silenciar":
        apretar(TECLA_VOLUMEN_MUTE)
        return "Listo, silenciado (o desilenciado si ya lo estaba)."
    if accion == "fijar":
        nivel = min(100, max(0, int(porcentaje)))
        apretar(TECLA_VOLUMEN_BAJAR, 50)       # primero a 0 %
        apretar(TECLA_VOLUMEN_SUBIR, round(nivel / 2))
        return f"Volumen en {nivel} %."
    return "No entendí. Puedo: subir, bajar, silenciar o fijar el volumen."


# ---------- MUSICA ----------
TECLAS_MUSICA = {
    "pausa": TECLA_PLAY_PAUSA, "pausar": TECLA_PLAY_PAUSA,
    "play": TECLA_PLAY_PAUSA, "reproducir": TECLA_PLAY_PAUSA,
    "siguiente": TECLA_SIGUIENTE, "anterior": TECLA_ANTERIOR,
}


def controlar_musica(accion: str) -> str:
    """
    Controla la música o el video que esté sonando (Spotify, YouTube, etc.).

    Args:
        accion: Una de: pausa, play, siguiente, anterior
    """
    tecla = TECLAS_MUSICA.get(accion.lower().strip())
    if tecla is None:
        return "Puedo hacer: pausa, play, siguiente o anterior."
    apretar(tecla)
    return f"Listo: {accion}."


# ---------- YOUTUBE ----------
def buscar_en_youtube(busqueda: str) -> str:
    """
    Busca videos en YouTube y abre los resultados en el navegador.

    Args:
        busqueda: Qué buscar, por ejemplo "soldar componentes SMD"
    """
    url = ("https://www.youtube.com/results?search_query="
           + urllib.parse.quote(busqueda))
    webbrowser.open(url)
    return f"Busqué '{busqueda}' en YouTube."


# ---------- CAPTURA DE PANTALLA ----------
CARPETA_CAPTURAS = Path(__file__).resolve().parent / "capturas"


def captura_de_pantalla() -> str:
    """Saca una captura de toda la pantalla y la guarda en la carpeta capturas."""
    from PIL import ImageGrab  # libreria Pillow (se importa solo si hace falta)
    CARPETA_CAPTURAS.mkdir(exist_ok=True)
    nombre = datetime.now().strftime("captura_%Y-%m-%d_%H-%M-%S.png")
    ImageGrab.grab().save(CARPETA_CAPTURAS / nombre)
    return f"Guardé la captura como {nombre} en la carpeta capturas."


# ---------- BLOQUEAR LA COMPU (con confirmacion) ----------
# Una accion "peligrosa" no se ejecuta en el primer pedido: JARVIS
# pregunta primero, y solo bloquea si confirmas en menos de 1 minuto.
# La confirmacion la controla ESTE codigo, no el modelo: aunque el
# modelo se equivoque, nunca bloquea de una.
_pedido_bloqueo = 0.0


def bloquear_compu(confirmado: bool = False) -> str:
    """
    Bloquea la compu. La primera vez hay que llamarla con confirmado=false: devuelve una pregunta para el usuario. Solo si el usuario responde que sí, llamarla otra vez con confirmado=true.

    Args:
        confirmado: true solo si el usuario ya confirmó que quiere bloquear
    """
    global _pedido_bloqueo
    ahora = time.time()
    if confirmado and ahora - _pedido_bloqueo < 60:
        _pedido_bloqueo = 0.0
        USER32.LockWorkStation()
        return "Compu bloqueada."
    _pedido_bloqueo = ahora
    return ("Antes de bloquear, preguntale al usuario: "
            "'¿Seguro que querés bloquear la compu?'")


HERRAMIENTAS_PC = [
    controlar_volumen, controlar_musica, buscar_en_youtube,
    captura_de_pantalla, bloquear_compu,
]
