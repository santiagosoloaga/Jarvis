# cerebro.py - El cerebro de JARVIS: Gemini (nube) + Ollama (local)
# Usa Gemini cuando hay internet y cupo gratis; si falla, usa Ollama.

from google.genai import types

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


def pensar(historial):
    # El ENRUTADOR de cerebros
    global ultimo_cerebro
    if MODO in ("auto", "gemini"):
        try:
            print("  [cerebro] Gemini (nube)")
            return pensar_gemini(historial)
        except Exception as error:
            if MODO == "gemini":
                raise
            print(f"  [cerebro] Gemini falló: {error}")
    print("  [cerebro] Ollama (local)")
    ultimo_cerebro = "Ollama (local)"
    return herramientas.pensar_con_herramientas(historial)


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
