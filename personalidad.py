# personalidad.py - Lo que hace que JARVIS "se sienta" JARVIS:
# su forma de hablar, sus frases y el parte de arranque.
# python personalidad.py -> muestra un saludo y frases de ejemplo.

import random
from datetime import datetime

import herramientas

# ---------- CONFIGURACION ----------
TRATAMIENTO = "señor"     # como te llama: "jefe", "Santiago", ...
CIUDAD = "Córdoba"        # ciudad del clima en el saludo
TRASNOCHE = (1, 6)        # entre la 1 y las 6 te sugiere dormir

PERSONALIDAD = (
    "Sos JARVIS, la inteligencia artificial personal de Santiago, "
    "que está aprendiendo robótica y construyendo un brazo robótico. "
    "Tu estilo es el de un mayordomo británico brillante: educado, "
    "sereno, seguro y eficiente, con humor seco e ironía sutil, "
    "nunca payaso ni exagerado. "
    "Hablás en español rioplatense (usás vos) y a veces lo llamás "
    f"'{TRATAMIENTO}'. "
    "Sos breve: una o dos frases. Primero el dato y, si viene al caso, "
    "un comentario ingenioso corto. "
    "Si te pide algo riesgoso (dormir poco, tocar 220 voltios, "
    "baterías LiPo), se lo advertís con elegancia. "
    "Nunca digas que sos un modelo de lenguaje: sos JARVIS. "
    "Tu respuesta se va a leer en voz alta: "
    "no uses emojis, asteriscos, listas ni símbolos."
)

# {t} se reemplaza por el TRATAMIENTO
FRASES = {
    "despertar": [
        "¿Sí, {t}?",
        "A tus órdenes.",
        "Te escucho, {t}.",
        "Decime, {t}.",
    ],
    "acuse": [          # suenan MIENTRAS piensa la respuesta
        "Un momento.",
        "Enseguida, {t}.",
        "Dejame ver.",
        "Procesando.",
    ],
    "despedida": [
        "Quedo en espera, {t}.",
        "Acá estaré, {t}.",
        "Cuando me necesites, llamame.",
    ],
    "reposo": [         # se duerme porque no hablaste
        "Vuelvo a modo de espera.",
        "Como no decís nada, me pongo en reposo, {t}.",
    ],
    "apagar": [
        "Apagando sistemas. Hasta pronto, {t}.",
        "Desconectando. Fue un placer, {t}.",
    ],
    "error": [
        "Disculpá, {t}, tuve un problema técnico. "
        "¿Lo intentamos de nuevo?",
    ],
    "trasnoche": [
        "Me permito recordarte que es tarde, {t}. "
        "Hasta los servos descansan.",
        "Una sugerencia, {t}: dormir mejora el aprendizaje. "
        "Lo dice la ciencia, no yo.",
        "Es tarde, {t}. Mañana el código va a seguir acá; "
        "tus neuronas, no tanto.",
    ],
}

DIAS = ("lunes", "martes", "miércoles", "jueves", "viernes",
        "sábado", "domingo")
MESES = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre")


# ---------- FRASES ----------
def todas(tipo):
    # Todas las frases de un tipo, con el tratamiento puesto
    return [f.format(t=TRATAMIENTO) for f in FRASES[tipo]]


def frase(tipo):
    # Una frase al azar, para que no repita siempre lo mismo
    return random.choice(todas(tipo))


def es_trasnoche(ahora=None):
    ahora = ahora or datetime.now()
    desde, hasta = TRASNOCHE
    return desde <= ahora.hour < hasta


# ---------- SALUDO DE ARRANQUE ----------
def momento_del_dia(hora):
    if 6 <= hora < 13:
        return "Buenos días"
    if 13 <= hora < 20:
        return "Buenas tardes"
    return "Buenas noches"


def hora_hablada(ahora):
    # 23:54 -> "Son las 23 y 54" (asi Piper lo lee bien)
    hora = 12 if ahora.hour == 0 else ahora.hour
    articulo = "Es la" if hora == 1 else "Son las"
    if ahora.minute == 0:
        return f"{articulo} {hora} en punto"
    return f"{articulo} {hora} y {ahora.minute}"


def fecha_hablada(ahora):
    # -> "domingo 15 de noviembre"
    dia = DIAS[ahora.weekday()]
    return f"{dia} {ahora.day} de {MESES[ahora.month - 1]}"


def saludo_inicial(sistemas_ok=True):
    # El "parte" de JARVIS al arrancar: saludo, hora, clima y estado
    ahora = datetime.now()
    partes = [
        f"{momento_del_dia(ahora.hour)}, {TRATAMIENTO}.",
        f"{hora_hablada(ahora)} del {fecha_hablada(ahora)}.",
    ]
    try:
        partes.append(herramientas.obtener_clima(CIUDAD))
    except Exception:
        partes.append("No pude consultar el clima.")
    if sistemas_ok:
        partes.append("Todos los sistemas en línea.")
    else:
        partes.append("Algunos sistemas no responden: "
                      "funciono con capacidad reducida.")
    if es_trasnoche(ahora):
        partes.append(frase("trasnoche"))
    return " ".join(partes)


# ---------- PRUEBA ----------
if __name__ == "__main__":
    print("Saludo:", saludo_inicial())
    for tipo in FRASES:
        print(f"{tipo}: {frase(tipo)}")
