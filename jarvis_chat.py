# jarvis_chat.py — Mini-proyecto 1: el chatbot de JARVIS en la terminal
import ollama  # librería para hablarle al servidor de Ollama

MODELO = "llama3.2:3b"  # el "cerebro" que vamos a usar

# El historial ES la memoria de JARVIS. Arranca con el mensaje de sistema (su personalidad).
historial = [
    {
        "role": "system",
        "content": (
            "Sos JARVIS, el asistente personal de Santiago. "
            "Respondés en español rioplatense, en pocas frases y con un toque de humor. "
            "Si no sabés algo, lo decís."
        ),
    }
]

print("JARVIS listo. Escribí 'salir' para terminar.\n")

while True:  # bucle: se repite hasta que lo cortemos con break
    pregunta = input("Vos: ").strip()  # leemos lo que escribís y sacamos espacios de más

    if pregunta.lower() == "salir":  # condición de salida
        print("JARVIS: Nos vemos, Santiago.")
        break
    if not pregunta:  # si apretaste Enter sin escribir nada, volvemos a preguntar
        continue

    historial.append({"role": "user", "content": pregunta})  # 1) guardamos tu mensaje

    print("JARVIS: ", end="", flush=True)
    respuesta_completa = ""
    # 2) le mandamos TODO el historial; con stream=True la respuesta llega de a pedacitos
    for pedazo in ollama.chat(model=MODELO, messages=historial, stream=True):
        texto = pedazo.message.content      # el pedacito de texto nuevo
        print(texto, end="", flush=True)    # lo mostramos apenas llega
        respuesta_completa += texto         # y lo vamos sumando
    print("\n")

    historial.append({"role": "assistant", "content": respuesta_completa})  # 3) guardamos la respuesta