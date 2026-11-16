# jarvis_chat.py - Mini-proyecto 1: el chatbot de JARVIS
# Personalidad, memoria, comandos y enrutador de modelos.

import ollama
from datetime import datetime

# ---------- CONFIGURACION ----------
# Modelo rapido: charla y ordenes simples
MODELO_RAPIDO = "llama3.2:3b"
# Modelo que piensa: calculos (mas lento)
MODELO_PENSADOR = "qwen3:4b"
# Si la pregunta empieza con estas palabras, usa el pensador
PALABRAS_PENSAR = ("calculá", "calcula", "resolvé", "resolve")

PERSONALIDAD = (
    "Sos JARVIS, el asistente personal de Santiago. "
    "Respondés en español rioplatense, en pocas frases "
    "y con un toque de humor. "
    "Si no sabés algo, lo decís."
)

AYUDA = (
    "Comandos:\n"
    "  /hora   -> te digo la hora\n"
    "  /reset  -> borro la memoria de la charla\n"
    "  /ayuda  -> muestro esta lista\n"
    "  salir   -> cierro el programa\n"
    "Si empezás con 'calculá' o 'resolvé', uso el pensador."
)


# ---------- FUNCIONES ----------
def elegir_modelo(pregunta):
    # El ENRUTADOR: decide que cerebro usar
    if pregunta.lower().startswith(PALABRAS_PENSAR):
        return MODELO_PENSADOR
    return MODELO_RAPIDO


def responder(historial, modelo):
    # Manda el historial al modelo y muestra la respuesta
    # a medida que llega (streaming)
    pensar = modelo == MODELO_PENSADOR

    print(f"JARVIS [{modelo}]: ", end="", flush=True)
    respuesta_completa = ""
    ya_avise = False

    # think=None: no le pedimos pensar (llama no sabe)
    for pedazo in ollama.chat(
        model=modelo,
        messages=historial,
        stream=True,
        think=True if pensar else None,
    ):
        # Pedazos de "pensamiento": avisamos una sola vez
        if pedazo.message.thinking and not ya_avise:
            print("(pensando...) ", end="", flush=True)
            ya_avise = True

        # Pedazos de la respuesta final: los mostramos
        texto = pedazo.message.content or ""
        print(texto, end="", flush=True)
        respuesta_completa += texto

    print("\n")
    return respuesta_completa


# ---------- PROGRAMA PRINCIPAL ----------
# Caja 0 del historial: la personalidad
historial = [{"role": "system", "content": PERSONALIDAD}]

print("JARVIS listo. Escribí /ayuda para ver los comandos.\n")

while True:
    pregunta = input("Vos: ").strip()

    # ----- COMANDOS (no llaman al modelo) -----
    if pregunta.lower() == "salir":
        print("JARVIS: Nos vemos, Santiago.")
        break

    if not pregunta:
        continue

    if pregunta == "/ayuda":
        print(AYUDA + "\n")
        continue

    if pregunta == "/hora":
        ahora = datetime.now().strftime("%H:%M")
        print(f"JARVIS: Son las {ahora}, Santiago.\n")
        continue

    if pregunta == "/reset":
        # Nos quedamos solo con la personalidad
        historial = [historial[0]]
        print("JARVIS: Memoria borrada. ¿En qué te ayudo?\n")
        continue

    # ----- CHARLA NORMAL (va al modelo) -----
    historial.append({"role": "user", "content": pregunta})
    modelo = elegir_modelo(pregunta)

    try:
        respuesta = responder(historial, modelo)
    except Exception as error:
        # Si algo falla, avisamos sin cerrar el programa
        print(f"\nJARVIS: Tuve un problema: {error}\n")
        # Sacamos la pregunta que no se pudo responder
        historial.pop()
        continue

    historial.append({"role": "assistant", "content": respuesta})