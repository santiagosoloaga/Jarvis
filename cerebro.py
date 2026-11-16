# cerebro.py - El cerebro de JARVIS: Gemini (nube) + Ollama (local)
# Usa Gemini cuando hay internet y cupo gratis; si falla, usa Ollama.

import logging
import os

from dotenv import load_dotenv
from google import genai
from google.genai import types

import herramientas

load_dotenv()  # lee el archivo .env y carga GEMINI_API_KEY
# Oculta avisos tecnicos de la libreria de Google
logging.getLogger("google_genai").setLevel(logging.ERROR)

# ---------- CONFIGURACION ----------
# "auto"   = Gemini; si falla (sin internet o sin cupo), Ollama
# "gemini" = solo Gemini
# "local"  = solo Ollama (privado y sin internet)
MODO = "auto"

# Modelos de Gemini a probar, en orden. Google cambia los nombres
# seguido: si fallan todos, fijate los disponibles en AI Studio.
MODELOS_GEMINI = ["gemini-3.6-flash", "gemini-3.5-flash-lite"]

_cliente = None


def cliente():
    # Crea la conexion con Gemini una sola vez y la reutiliza
    global _cliente
    if _cliente is None:
        clave = os.environ.get("GEMINI_API_KEY")
        if not clave:
            raise RuntimeError("falta GEMINI_API_KEY en el archivo .env")
        _cliente = genai.Client(api_key=clave)
    return _cliente


def a_formato_gemini(historial):
    # Nuestro historial usa roles system/user/assistant (estilo Ollama).
    # Gemini usa "user" y "model", y la personalidad va aparte.
    sistema = ""
    contenidos = []
    for mensaje in historial:
        if isinstance(mensaje, dict):
            rol, texto = mensaje["role"], mensaje.get("content")
        else:  # mensajes que guarda Ollama al usar herramientas
            rol, texto = mensaje.role, mensaje.content
        if rol == "system":
            sistema = texto
        elif rol in ("user", "assistant") and texto:
            contenidos.append(types.Content(
                role="user" if rol == "user" else "model",
                parts=[types.Part.from_text(text=texto)],
            ))
    return sistema, contenidos


def mostrar_herramientas_usadas(respuesta):
    # Gemini ejecuta las herramientas solo; aca mostramos cuales uso
    for turno in respuesta.automatic_function_calling_history or []:
        for parte in turno.parts or []:
            if parte.function_call:
                llamada = parte.function_call
                print(f"  [herramienta] {llamada.name} {dict(llamada.args or {})}")
            if parte.function_response:
                print(f"  [resultado] {parte.function_response.response}")


def pensar_gemini(historial):
    sistema, contenidos = a_formato_gemini(historial)
    config = types.GenerateContentConfig(
        system_instruction=sistema,
        # Le pasamos las MISMAS funciones de herramientas.py.
        # La libreria las ejecuta sola cuando Gemini las pide.
        tools=list(herramientas.HERRAMIENTAS.values()),
    )
    ultimo_error = None
    for modelo in MODELOS_GEMINI:
        try:
            respuesta = cliente().models.generate_content(
                model=modelo, contents=contenidos, config=config
            )
        except Exception as error:
            ultimo_error = error
            # Mostramos el motivo corto (ej: "429 RESOURCE_EXHAUSTED")
            print(f"  [cerebro] {modelo} falló: {str(error)[:120]}")
            continue  # probamos con el siguiente modelo de la lista
        mostrar_herramientas_usadas(respuesta)
        if respuesta.text:
            return respuesta.text
    raise RuntimeError("ningún modelo de Gemini respondió")


def pensar(historial):
    # El ENRUTADOR de cerebros
    if MODO in ("auto", "gemini"):
        try:
            print("  [cerebro] Gemini (nube)")
            return pensar_gemini(historial)
        except Exception as error:
            if MODO == "gemini":
                raise
            print(f"  [cerebro] Gemini falló: {error}")
    print("  [cerebro] Ollama (local)")
    return herramientas.pensar_con_herramientas(historial)


# ---------- PRUEBA POR TEXTO ----------
# python cerebro.py -> charlás por teclado para probar el cerebro
if __name__ == "__main__":
    personalidad = (
        "Sos JARVIS, el asistente de Santiago. Respondés en español"
        " rioplatense, en una o dos frases." + herramientas.INSTRUCCIONES
    )
    historial = [{"role": "system", "content": personalidad}]
    print(f"Modo: {MODO}. Escribí 'salir' para terminar.\n")
    while True:
        pregunta = input("Vos: ").strip()
        if pregunta.lower() == "salir":
            break
        if not pregunta:
            continue
        historial.append({"role": "user", "content": pregunta})
        respuesta = pensar(historial)
        historial.append({"role": "assistant", "content": respuesta})
        print("JARVIS:", respuesta, "\n")
