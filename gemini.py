# gemini.py - Conexion con Gemini, compartida por cerebro.py e
# informacion.py. Maneja la CUOTA GRATIS de forma inteligente:
# si un modelo responde "429" (cuota agotada), lo deja descansar un
# rato y no lo vuelve a probar en cada pedido.

import logging
import os
import re
import time

from dotenv import load_dotenv
from google import genai

load_dotenv()                     # lee GEMINI_API_KEY del archivo .env
logging.getLogger("google_genai").setLevel(logging.ERROR)

# ---------- CONFIGURACION ----------
DESCANSO_POR_DEFECTO = 30 * 60    # segundos sin probar un modelo agotado

_cliente = None
_descansando = {}                 # modelo -> momento en que vuelve


def cliente():
    # Crea la conexion una sola vez y la reutiliza
    global _cliente
    if _cliente is None:
        clave = os.environ.get("GEMINI_API_KEY")
        if not clave:
            raise RuntimeError("falta GEMINI_API_KEY en el archivo .env")
        _cliente = genai.Client(api_key=clave)
    return _cliente


def motivo_corto(error):
    # Traduce el error largo de Google a algo legible
    texto = str(error)
    if "429" in texto or "RESOURCE_EXHAUSTED" in texto:
        return "cuota agotada"
    if "404" in texto or "NOT_FOUND" in texto:
        return "modelo inexistente (¿cambió el nombre?)"
    if "API key" in texto or "PERMISSION_DENIED" in texto:
        return "problema con la clave"
    return texto[:80]


def segundos_de_descanso(error):
    # Si Google dice "retry in 37s", esperamos eso (limite por minuto).
    # Si no lo dice, suele ser el limite DIARIO: descanso largo.
    encontrado = re.search(r"retry in (\d+(?:\.\d+)?)s", str(error),
                           re.IGNORECASE)
    if encontrado:
        return float(encontrado.group(1)) + 1
    return DESCANSO_POR_DEFECTO


def pedir(modelos, contenido, config=None):
    # Prueba los modelos en orden y devuelve (respuesta, modelo usado).
    # Saltea los que estan "descansando" por cuota agotada.
    ahora = time.time()
    ultimo_motivo = "todos los modelos están descansando"
    for modelo in modelos:
        vuelve = _descansando.get(modelo, 0)
        if vuelve > ahora:
            print(f"  [gemini] {modelo}: descansando "
                  f"{int(vuelve - ahora)} s más, lo salteo")
            continue
        try:
            respuesta = cliente().models.generate_content(
                model=modelo, contents=contenido, config=config)
            return respuesta, modelo
        except Exception as error:
            ultimo_motivo = motivo_corto(error)
            print(f"  [gemini] {modelo}: {ultimo_motivo}")
            if ultimo_motivo == "cuota agotada":
                _descansando[modelo] = time.time() + segundos_de_descanso(error)
    raise RuntimeError(f"Gemini no respondió ({ultimo_motivo})")
