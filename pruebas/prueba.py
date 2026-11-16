import ollama  # librería para hablarle al servidor de Ollama

# Le mandamos una lista con UN solo mensaje, del rol "user"
respuesta = ollama.chat(
    model="llama3.2:3b",
    messages=[{"role": "user", "content": "Decime hola en una frase"}],
)

print(respuesta.message.content)  # el texto de la respuesta está en .message.content