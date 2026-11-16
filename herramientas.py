# herramientas.py - Las "manos" de JARVIS (tool calling)
# Cada funcion de aca es una herramienta que el LLM puede pedir usar.
# El LLM NO ejecuta nada: solo pide. El que ejecuta es este codigo.

import json
import subprocess
import threading
import urllib.parse
import urllib.request
import webbrowser
from datetime import datetime

import ollama

MODELO = "llama3.2:3b"

# Funcion para avisar recordatorios. Por defecto imprime en pantalla;
# jarvis_wake.py la reemplaza por "decirlo en voz alta".
avisar = print


# ---------- HERRAMIENTA 1: la hora ----------
def obtener_hora() -> str:
    """Devuelve la fecha y la hora actuales de la computadora."""
    ahora = datetime.now()
    return ahora.strftime("Son las %H:%M del %d/%m/%Y")


# ---------- HERRAMIENTA 2: el clima ----------
# Codigos de clima de la Organizacion Meteorologica Mundial (WMO)
ESTADOS = {
    0: "despejado", 1: "mayormente despejado", 2: "parcialmente nublado",
    3: "nublado", 45: "con niebla", 48: "con niebla",
    51: "con llovizna", 53: "con llovizna", 55: "con llovizna",
    61: "con lluvia débil", 63: "con lluvia", 65: "con lluvia fuerte",
    71: "con nieve", 73: "con nieve", 75: "con nieve fuerte",
    80: "con chaparrones", 81: "con chaparrones", 82: "con chaparrones",
    95: "con tormenta", 96: "con tormenta y granizo",
    99: "con tormenta y granizo",
}


def leer_json(url):
    # Pide una pagina web y la convierte en un diccionario de Python
    with urllib.request.urlopen(url, timeout=10) as respuesta:
        return json.load(respuesta)


def obtener_clima(ciudad: str) -> str:
    """
    Devuelve el clima actual de una ciudad.

    Args:
        ciudad: Nombre de la ciudad, por ejemplo "Córdoba"
    """
    # 1) Buscamos las coordenadas de la ciudad
    nombre = urllib.parse.quote(ciudad)
    url = ("https://geocoding-api.open-meteo.com/v1/search"
           f"?name={nombre}&count=10&language=es&format=json")
    lugares = leer_json(url).get("results", [])
    if not lugares:
        return f"No encontré la ciudad {ciudad}."
    # Preferimos ciudades de Argentina (hay otra Córdoba en España)
    argentinas = [l for l in lugares if l.get("country_code") == "AR"]
    lugar = (argentinas or lugares)[0]

    # 2) Pedimos el clima actual en esas coordenadas
    url = ("https://api.open-meteo.com/v1/forecast"
           f"?latitude={lugar['latitude']}&longitude={lugar['longitude']}"
           "&current=temperature_2m,weather_code&timezone=auto")
    actual = leer_json(url)["current"]
    estado = ESTADOS.get(actual["weather_code"], "con clima variable")
    temp = round(actual["temperature_2m"])
    return f"En {lugar['name']} hace {temp} grados y está {estado}."


# ---------- HERRAMIENTA 3: abrir programas ----------
# LISTA BLANCA: solo se puede abrir lo que esta aca.
# Nunca dejes que el LLM ejecute cualquier comando.
PROGRAMAS = {
    "bloc de notas": ["notepad.exe"],
    "calculadora": ["calc.exe"],
    "explorador": ["explorer.exe"],
}


def abrir_programa(nombre: str) -> str:
    """
    Abre un programa de la computadora.

    Args:
        nombre: Uno de: bloc de notas, calculadora, explorador, navegador
    """
    nombre = nombre.lower().strip()
    if nombre == "navegador":
        webbrowser.open("https://www.google.com")
        return "Abrí el navegador."
    if nombre not in PROGRAMAS:
        permitidos = ", ".join(list(PROGRAMAS) + ["navegador"])
        return f"No puedo abrir '{nombre}'. Solo puedo abrir: {permitidos}."
    subprocess.Popen(PROGRAMAS[nombre])
    return f"Abrí {nombre}."


# ---------- HERRAMIENTA 4: recordatorios ----------
def poner_recordatorio(minutos: float, mensaje: str) -> str:
    """
    Programa un recordatorio que JARVIS avisa en voz alta.

    Args:
        minutos: Dentro de cuántos minutos avisar
        mensaje: Qué hay que recordar
    """
    minutos = float(minutos)  # a veces el modelo manda "5" como texto
    temporizador = threading.Timer(
        minutos * 60, avisar, args=[f"Recordatorio: {mensaje}"]
    )
    temporizador.daemon = True  # si cerrás JARVIS, se cancela
    temporizador.start()
    return f"Listo, te aviso en {minutos:g} minutos."


# Diccionario nombre -> funcion: asi encontramos la que pidio el modelo
HERRAMIENTAS = {
    f.__name__: f
    for f in [obtener_hora, obtener_clima, abrir_programa, poner_recordatorio]
}

INSTRUCCIONES = (
    " Tenés herramientas para saber la hora, el clima, abrir programas"
    " y poner recordatorios. Usalas solo cuando hagan falta."
    " Nunca inventes la hora ni el clima: pedíselos a tus herramientas."
    " Cuando una herramienta te devuelve un resultado, ese dato es real"
    " y actual: respondé usándolo y nunca digas que no tenés información."
)

# Cuantas veces seguidas puede pedir herramientas antes de cortar
MAX_VUELTAS = 3

# Plan B para modelos chicos: si es True, JARVIS dice directamente
# el resultado de la herramienta, sin pedirle al LLM que lo redacte.
# Es menos "natural" pero nunca ignora el dato (y es mas rapido).
RESULTADO_DIRECTO = False


# ---------- EL IDA Y VUELTA ----------
def ejecutar(llamada):
    # Ejecuta UNA herramienta pedida por el modelo y devuelve el texto
    nombre = llamada.function.name
    argumentos = llamada.function.arguments or {}
    print(f"  [herramienta] {nombre} {argumentos}")
    funcion = HERRAMIENTAS.get(nombre)
    try:
        if funcion is None:
            resultado = f"No existe la herramienta {nombre}."
        else:
            resultado = funcion(**argumentos)
    except Exception as error:
        resultado = f"La herramienta falló: {error}"
    print(f"  [resultado] {resultado}")
    return nombre, str(resultado)


def pensar_con_herramientas(historial, modelo=MODELO):
    lista = list(HERRAMIENTAS.values())
    resultados = []

    for vuelta in range(MAX_VUELTAS):
        # 1) Le mandamos la charla y la lista de herramientas
        respuesta = ollama.chat(model=modelo, messages=historial, tools=lista)
        mensaje = respuesta.message

        # 2) Si no pidio herramientas, es la respuesta final
        if not mensaje.tool_calls:
            return mensaje.content

        # 3) Pidio herramientas: las ejecutamos nosotros
        historial.append(mensaje)
        for llamada in mensaje.tool_calls:
            nombre, resultado = ejecutar(llamada)
            resultados.append(resultado)
            # 4) Devolvemos el resultado con el rol "tool",
            #    remarcando que es un dato real
            historial.append({
                "role": "tool",
                "content": f"Dato real y actual: {resultado}",
                "tool_name": nombre,
            })

        # Plan B: no le pedimos al modelo que lo redacte
        if RESULTADO_DIRECTO:
            return " ".join(dict.fromkeys(resultados))

        # 5) Volvemos al paso 1: el modelo redacta con los datos
        #    (o pide otra herramienta si le falta algo)

    # Si se paso de vueltas, decimos los resultados tal cual
    # (dict.fromkeys saca los repetidos y mantiene el orden)
    return " ".join(dict.fromkeys(resultados))


# ---------- PRUEBA POR TEXTO ----------
# python herramientas.py -> charlás por teclado (sin voz) para probar
if __name__ == "__main__":
    personalidad = (
        "Sos JARVIS, el asistente de Santiago. Respondés en español"
        " rioplatense, en una o dos frases." + INSTRUCCIONES
    )
    historial = [{"role": "system", "content": personalidad}]
    print("Probá: '¿qué hora es?', '¿cómo está el clima en Córdoba?',")
    print("'abrí la calculadora', 'recordame en 1 minuto tomar agua'.")
    print("Escribí 'salir' para terminar.\n")
    while True:
        pregunta = input("Vos: ").strip()
        if pregunta.lower() == "salir":
            break
        if not pregunta:
            continue
        historial.append({"role": "user", "content": pregunta})
        respuesta = pensar_con_herramientas(historial)
        historial.append({"role": "assistant", "content": respuesta})
        print("JARVIS:", respuesta, "\n")
