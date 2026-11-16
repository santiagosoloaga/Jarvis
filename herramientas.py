# herramientas.py - Las "manos" de JARVIS (tool calling)
# Cada funcion de aca es una herramienta que el LLM puede pedir usar.
# El LLM NO ejecuta nada: solo pide. El que ejecuta es este codigo.

import ast
import json
import math
import operator
import re
import subprocess
import threading
import urllib.parse
import urllib.request
import webbrowser
from datetime import datetime
from pathlib import Path

import ollama

from control_pc import HERRAMIENTAS_PC
from informacion import HERRAMIENTAS_INFO

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


# Como se "presenta" JARVIS ante los sitios web. Algunos (como DolarApi)
# rechazan con error 403 el nombre que usa Python por defecto.
CABECERAS = {"User-Agent": "JARVIS/1.0 (asistente personal de Santiago)"}


def leer_json(url):
    # Pide una pagina web y la convierte en un diccionario de Python
    pedido = urllib.request.Request(url, headers=CABECERAS)
    with urllib.request.urlopen(pedido, timeout=10) as respuesta:
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


# ---------- HERRAMIENTA 5: calculadora exacta ----------
# NUNCA uses eval() con texto que viene de afuera: ejecutaria cualquier
# codigo. Aca leemos la cuenta como un arbol (ast) y solo permitimos
# numeros, operaciones basicas y algunas funciones matematicas.
OPERACIONES = {
    ast.Add: operator.add, ast.Sub: operator.sub,
    ast.Mult: operator.mul, ast.Div: operator.truediv,
    ast.Pow: operator.pow, ast.Mod: operator.mod,
    ast.USub: operator.neg, ast.UAdd: operator.pos,
}
FUNCIONES = {
    "raiz": math.sqrt, "sqrt": math.sqrt, "abs": abs,
    "sin": math.sin, "cos": math.cos, "tan": math.tan,
    "log": math.log10, "ln": math.log,
}
CONSTANTES = {"pi": math.pi, "e": math.e}


def _evaluar(nodo):
    # Recorre el arbol de la cuenta, pieza por pieza
    if isinstance(nodo, ast.Constant) and isinstance(nodo.value, (int, float)):
        return nodo.value
    if isinstance(nodo, ast.BinOp) and type(nodo.op) in OPERACIONES:
        izquierda, derecha = _evaluar(nodo.left), _evaluar(nodo.right)
        if isinstance(nodo.op, ast.Pow) and abs(derecha) > 1000:
            raise ValueError("exponente demasiado grande")
        return OPERACIONES[type(nodo.op)](izquierda, derecha)
    if isinstance(nodo, ast.UnaryOp) and type(nodo.op) in OPERACIONES:
        return OPERACIONES[type(nodo.op)](_evaluar(nodo.operand))
    if isinstance(nodo, ast.Name) and nodo.id in CONSTANTES:
        return CONSTANTES[nodo.id]
    if (isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Name)
            and nodo.func.id in FUNCIONES and len(nodo.args) == 1):
        return FUNCIONES[nodo.func.id](_evaluar(nodo.args[0]))
    raise ValueError("operación no permitida")


def calcular(expresion: str) -> str:
    """
    Calcula una cuenta matemática de forma exacta. Usala siempre que haya que hacer una cuenta.

    Args:
        expresion: La cuenta escrita como en Python, por ejemplo "17.5 * 23", "2 ** 10", "raiz(144)" o "sin(pi / 6)"
    """
    texto = expresion.replace("×", "*").replace("^", "**").replace(",", ".")
    try:
        resultado = _evaluar(ast.parse(texto, mode="eval").body)
    except ZeroDivisionError:
        return "No se puede dividir por cero."
    except Exception:
        return f"No pude calcular '{expresion}'."
    if isinstance(resultado, float):
        resultado = round(resultado, 6)
    return f"{expresion} = {resultado}"


# ---------- HERRAMIENTA 6: pomodoro ----------
def iniciar_pomodoro(minutos_estudio: float = 25, minutos_descanso: float = 5) -> str:
    """
    Inicia un pomodoro: un bloque de estudio y después un descanso. Avisa en voz alta cuando termina cada parte.

    Args:
        minutos_estudio: Minutos de estudio (normalmente 25)
        minutos_descanso: Minutos de descanso (normalmente 5)
    """
    estudio, descanso = float(minutos_estudio), float(minutos_descanso)
    fin_estudio = threading.Timer(
        estudio * 60, avisar,
        args=[f"Terminó el bloque de estudio. Descansá {descanso:g} minutos."],
    )
    fin_descanso = threading.Timer(
        (estudio + descanso) * 60, avisar,
        args=["Terminó el descanso. A estudiar de nuevo."],
    )
    for temporizador in (fin_estudio, fin_descanso):
        temporizador.daemon = True
        temporizador.start()
    return (f"Pomodoro iniciado: {estudio:g} minutos de estudio "
            f"y {descanso:g} de descanso.")


# ---------- HERRAMIENTA 7 y 8: notas rapidas ----------
# Se guardan en notas.txt, en la carpeta jarvis (Git lo ignora).
ARCHIVO_NOTAS = Path(__file__).resolve().parent / "notas.txt"


def anotar(texto: str) -> str:
    """
    Guarda una nota rápida para recordar más tarde.

    Args:
        texto: Lo que hay que anotar, por ejemplo "comprar resistencias"
    """
    fecha = datetime.now().strftime("%d/%m %H:%M")
    with open(ARCHIVO_NOTAS, "a", encoding="utf-8") as archivo:
        archivo.write(f"[{fecha}] {texto}\n")
    return f"Anotado: {texto}."


def leer_notas() -> str:
    """Lee las últimas notas guardadas."""
    if not ARCHIVO_NOTAS.exists():
        return "No tenés notas guardadas."
    lineas = ARCHIVO_NOTAS.read_text(encoding="utf-8").splitlines()
    ultimas = [linea for linea in lineas if linea.strip()][-10:]
    if not ultimas:
        return "No tenés notas guardadas."
    return "Tus últimas notas: " + "; ".join(ultimas)


# ---------- HERRAMIENTA 9: abrir sitios web ----------
# LISTA BLANCA de paginas. Si agregas una, sumala tambien al docstring.
SITIOS = {
    "youtube": "https://www.youtube.com",
    "gmail": "https://mail.google.com",
    "google drive": "https://drive.google.com",
    "calendario": "https://calendar.google.com",
    "github": "https://github.com",
    "mercadolibre": "https://www.mercadolibre.com.ar",
    "wikipedia": "https://es.wikipedia.org",
}


def abrir_sitio(nombre: str) -> str:
    """
    Abre una página web en el navegador.

    Args:
        nombre: Uno de: youtube, gmail, google drive, calendario, github, mercadolibre, wikipedia
    """
    nombre = nombre.lower().strip()
    if nombre not in SITIOS:
        return f"No tengo '{nombre}' en mi lista. Puedo abrir: {', '.join(SITIOS)}."
    webbrowser.open(SITIOS[nombre])
    return f"Abrí {nombre}."


# ---------- HERRAMIENTA 10: dolar hoy ----------
OTROS_NOMBRES_DOLAR = {"mep": "bolsa", "ccl": "contadoconliqui"}


def formato_pesos(valor):
    # 1515.5 -> "$1.516" (punto para los miles, como en Argentina)
    return "$" + f"{valor:,.0f}".replace(",", ".")


def obtener_dolar(tipo: str = "blue") -> str:
    """
    Devuelve la cotización del dólar en Argentina, compra y venta.

    Args:
        tipo: Uno de: oficial, blue, mep, ccl, mayorista, cripto, tarjeta
    """
    tipo = tipo.lower().strip()
    tipo = OTROS_NOMBRES_DOLAR.get(tipo, tipo)
    cotizaciones = leer_json("https://dolarapi.com/v1/dolares")
    for dolar in cotizaciones:
        if dolar.get("casa") == tipo:
            texto = f"Dólar {dolar.get('nombre', tipo)}:"
            if dolar.get("compra"):
                texto += f" compra {formato_pesos(dolar['compra'])},"
            texto += f" venta {formato_pesos(dolar['venta'])}."
            return texto
    disponibles = ", ".join(d.get("casa", "?") for d in cotizaciones)
    return f"No encontré el dólar '{tipo}'. Hay: {disponibles}."


# ---------- HERRAMIENTA: buscar informacion (Wikipedia) ----------
WIKIPEDIA = "https://es.wikipedia.org/w/api.php"
MAX_CARACTERES_INFO = 700   # resumen corto: se lee en voz alta


def recortar(texto, maximo):
    # Corta en el ultimo punto antes del maximo (no a mitad de frase)
    if len(texto) <= maximo:
        return texto
    corte = texto.rfind(". ", 0, maximo)
    return texto[:corte + 1] if corte > 0 else texto[:maximo] + "..."


def buscar_informacion(tema: str) -> str:
    """
    Busca información sobre un tema en Wikipedia en español y
    devuelve un resumen. Usala para preguntas de cultura general,
    ciencia, tecnología, historia, personas, lugares o conceptos
    ("¿qué es...?", "¿quién fue...?", "contame sobre...").

    Args:
        tema: Lo que hay que buscar, por ejemplo "servomotor" o "Alan Turing"
    """
    # Un solo pedido hace dos cosas:
    #   generator=search -> busca el articulo que mejor coincide
    #   prop=extracts    -> trae su introduccion en texto plano
    parametros = urllib.parse.urlencode({
        "action": "query", "format": "json", "formatversion": 2,
        "generator": "search", "gsrsearch": tema, "gsrlimit": 1,
        "prop": "extracts", "exintro": 1, "explaintext": 1,
        "redirects": 1,
    })
    datos = leer_json(f"{WIKIPEDIA}?{parametros}")
    paginas = datos.get("query", {}).get("pages", [])
    if isinstance(paginas, dict):        # formato viejo de la API
        paginas = list(paginas.values())
    if not paginas:
        return f"No encontré información sobre {tema} en Wikipedia."

    pagina = paginas[0]
    texto = pagina.get("extract", "")
    # Sacamos lo que esta entre parentesis (pronunciacion, fechas
    # en otros idiomas...): en voz alta suena horrible
    texto = re.sub(r"\s*\([^()]*\)", "", texto)
    texto = " ".join(texto.split())      # espacios y saltos de linea
    if not texto:
        return f"Encontré el artículo {pagina['title']}, pero está vacío."
    texto = recortar(texto, MAX_CARACTERES_INFO)
    return f"Según Wikipedia ({pagina['title']}): {texto}"


# Diccionario nombre -> funcion: asi encontramos la que pidio el modelo
HERRAMIENTAS = {
    f.__name__: f
    for f in [
        obtener_hora, obtener_clima, abrir_programa, poner_recordatorio,
        calcular, iniciar_pomodoro, anotar, leer_notas, abrir_sitio,
        obtener_dolar, buscar_informacion,
    ] + HERRAMIENTAS_PC     # las de control_pc.py
    + HERRAMIENTAS_INFO   # las de informacion.py
}

INSTRUCCIONES = (
    " Tenés herramientas para saber la hora, el clima y el dólar,"
    " hacer cuentas exactas, abrir programas y páginas web, poner"
    " recordatorios y pomodoros, anotar o leer notas, manejar el"
    " volumen y la música, buscar en YouTube, sacar capturas de"
    " pantalla y bloquear la compu (siempre pidiendo confirmación)."
    " Para preguntas de información general (qué es algo, quién fue"
    " alguien, historia, ciencia) usá buscar_informacion y resumí"
    " el resultado en una o dos frases, con tus palabras."
    " Para noticias, resultados deportivos o cualquier dato actual"
    " usá buscar_en_google con palabras clave cortas; te devuelve"
    " titulares con su fecha: contestá con el más reciente que"
    " responda la pregunta. Para resumir un PDF del usuario usá"
    " resumir_pdf, y para preguntas sobre sus planillas de Excel o CSV"
    " usá consultar_planilla (los totales y promedios ya vienen"
    " calculados: usalos tal cual)."
    " Si una herramienta falla, decilo en una frase simple, sin"
    " detalles técnicos."
    " Usalas solo cuando hagan falta."
    " Para cualquier cuenta usá la calculadora: nunca calcules de memoria."
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
ultima_accion = "ninguna"   # la interfaz la muestra en pantalla


def ejecutar(llamada):
    # Ejecuta UNA herramienta pedida por el modelo y devuelve el texto
    global ultima_accion
    nombre = llamada.function.name
    ultima_accion = nombre
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
    print("Probá: '¿qué hora es?', '¿cuánto es 17,5 por 23?',")
    print("'¿a cuánto está el blue?', 'anotá comprar resistencias',")
    print("'¿qué tengo anotado?', 'abrí YouTube', 'empezá un pomodoro'.")
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
