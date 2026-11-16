# cerebro.py - El cerebro de JARVIS: Gemini (nube) + Ollama (local)
# Usa Gemini cuando hay internet y cupo gratis; si falla, usa Ollama.

from google.genai import types

import control_pc
import gemini
import herramientas

# ---------- CONFIGURACION ----------
# "auto"   = Gemini; si falla (sin internet o sin cupo), Ollama
# "gemini" = solo Gemini
# "local"  = solo Ollama (privado y sin internet)
MODO = "auto"

# Modelos de Gemini a probar, en orden. Google cambia los nombres
# seguido: si fallan todos, fijate los disponibles en AI Studio.
# Cuota gratis aprox.: Flash-Lite 500 pedidos/dia, Flash solo 20.
# Por eso Flash-Lite va primero y Flash queda de respaldo.
MODELOS_GEMINI = ["gemini-3.5-flash-lite", "gemini-3.6-flash"]

# Cuantos mensajes de la charla le mandamos al cerebro (ademas de la
# personalidad). Mandar TODO el historial lo hace cada vez mas lento
# y gasta cuota; con los ultimos 20 (10 idas y vueltas) alcanza.
MAX_MENSAJES = 20

ultimo_cerebro = "ninguno todavía"   # la interfaz lo muestra
cliente = gemini.cliente              # jarvis_wake lo usa al arrancar


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
                herramientas.ultima_accion = llamada.name
                print(f"  [herramienta] {llamada.name} {dict(llamada.args or {})}")
            if parte.function_response:
                print(f"  [resultado] {parte.function_response.response}")


def pensar_gemini(historial):
    global ultimo_cerebro
    sistema, contenidos = a_formato_gemini(historial)
    config = types.GenerateContentConfig(
        system_instruction=sistema,
        # Le pasamos las MISMAS funciones de herramientas.py.
        # La libreria las ejecuta sola cuando Gemini las pide.
        tools=list(herramientas.HERRAMIENTAS.values()),
    )
    # gemini.pedir prueba los modelos en orden y saltea los agotados
    respuesta, modelo = gemini.pedir(MODELOS_GEMINI, contenidos, config)
    mostrar_herramientas_usadas(respuesta)
    if not respuesta.text:
        raise RuntimeError(f"{modelo} respondió vacío")
    ultimo_cerebro = f"Gemini ({modelo})"
    return respuesta.text


def recortar_historial(historial, maximo=MAX_MENSAJES):
    # Devuelve una COPIA corta: personalidad + ultimos "maximo" mensajes.
    # Es copia a proposito: lo que Ollama agregue al usar herramientas
    # (mensajes "tool") queda ahi y no ensucia el historial original.
    sistema = [m for m in historial[:1] if _rol(m) == "system"]
    charla = historial[len(sistema):][-maximo:]
    # La charla tiene que empezar con un mensaje tuyo (Gemini lo exige)
    while charla and _rol(charla[0]) != "user":
        charla.pop(0)
    return sistema + charla


def _rol(mensaje):
    return mensaje["role"] if isinstance(mensaje, dict) else mensaje.role


def pensar(historial):
    # El ENRUTADOR de cerebros. Cada llamada = un mensaje nuevo tuyo.
    global ultimo_cerebro
    control_pc.nuevo_turno()        # para la confirmacion de bloquear
    corto = recortar_historial(historial)
    if MODO in ("auto", "gemini"):
        try:
            print("  [cerebro] Gemini (nube)")
            return pensar_gemini(corto)
        except Exception as error:
            if MODO == "gemini":
                raise
            print(f"  [cerebro] Gemini falló: {error}")
    print("  [cerebro] Ollama (local)")
    ultimo_cerebro = "Ollama (local)"
    return herramientas.pensar_con_herramientas(corto)


# ---------- PRUEBA POR TEXTO ----------
# python cerebro.py -> charlás por teclado para probar el cerebro
if __name__ == "__main__":
    from personalidad import PERSONALIDAD
    instrucciones = PERSONALIDAD + herramientas.INSTRUCCIONES
    historial = [{"role": "system", "content": instrucciones}]
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
