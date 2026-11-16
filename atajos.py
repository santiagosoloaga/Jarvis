# atajos.py - Respuestas rápidas SIN Gemini para los pedidos de todos los días.
#
# Pedirle algo a Gemini son 2-6 segundos de viaje a la nube. Para lo más
# repetido ("¿qué hora es?", "¿qué me falta hoy?", "abrí Spotify", "subí
# el volumen") no hace falta un cerebro: alcanza con reconocer la frase,
# llamar a la herramienta y hablar el resultado. Responde casi al instante.
#
# Regla de oro: si la frase NO encaja exactamente en un patrón, devuelve
# None y el pedido sigue el camino de siempre (Gemini). Mejor dudar que
# ejecutar algo equivocado.
#
# python atajos.py -> prueba las frases de ejemplo sin ejecutar nada.

import re
import unicodedata
from datetime import datetime

# Interruptor: False = todo pasa por Gemini como antes
ATAJOS_ACTIVOS = True

DIAS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
MESES = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre")
UNIDADES = ("cero", "uno", "dos", "tres", "cuatro", "cinco", "seis", "siete",
            "ocho", "nueve", "diez", "once", "doce", "trece", "catorce",
            "quince", "dieciséis", "diecisiete", "dieciocho", "diecinueve")
DECENAS = {20: "veinte", 30: "treinta", 40: "cuarenta", 50: "cincuenta"}


# ---------- Utilidades ----------
def limpiar(texto):
    """'¡Abrí Spotify, por favor!' -> 'abri spotify'."""
    texto = unicodedata.normalize("NFD", texto.lower())
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = re.sub(r"[^a-z0-9ñ ]", " ", texto)
    texto = re.sub(r"\b(jarvis|por favor|porfa|che|dale|hola|gracias)\b", " ", texto)
    # Cortesías que no cambian el pedido: "podés decirme", "me podes..."
    texto = re.sub(r"\b(me )?(puedes|podes|podrias|puedo)( decirme| decime| dime)?\b", " ", texto)
    texto = re.sub(r"\b(decime|dime|decirme|quiero saber|quisiera saber)\b", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


def numero_hablado(n):
    if n < 20:
        return UNIDADES[n]
    if n < 30:
        return "veinte" if n == 20 else "veinti" + UNIDADES[n - 20]
    decena, unidad = divmod(n, 10)
    base = DECENAS[decena * 10]
    return base if unidad == 0 else f"{base} y {UNIDADES[unidad]}"


def hora_hablada(ahora):
    """15:31 -> 'las tres y treinta y uno de la tarde'."""
    h12 = ahora.hour % 12 or 12
    articulo = "la una" if h12 == 1 else f"las {numero_hablado(h12)}"
    minutos = "" if ahora.minute == 0 else f" y {numero_hablado(ahora.minute)}"
    if ahora.hour < 6:
        franja = "de la madrugada"
    elif ahora.hour < 12:
        franja = "de la mañana"
    elif ahora.hour < 20:
        franja = "de la tarde"
    else:
        franja = "de la noche"
    return f"{articulo}{minutos} {franja}"


def _dia(t):
    return "ayer" if re.search(r"\bayer\b", t) else "hoy"


# ---------- Reconocedores: cada uno devuelve (herramienta, texto) o None ----------
# Importamos las herramientas recién al usarlas (evita imports circulares).
def _hora(t):
    if re.fullmatch(r"(que )?(hora|horas)( es| son| tenemos)?( ahora| ya)?", t):
        return "obtener_hora", lambda: f"Son {hora_hablada(datetime.now())}, señor."


def _fecha(t):
    if re.fullmatch(r"(que )?(dia|fecha) (es )?(hoy)?|a cuanto estamos|que dia es", t):
        def decir():
            ahora = datetime.now()
            return (f"Hoy es {DIAS[ahora.weekday()]} {ahora.day} de "
                    f"{MESES[ahora.month - 1]}, señor.")
        return "obtener_hora", decir


def _ver_habitos(t):
    import habitos
    dia = _dia(t)
    sin_dia = re.sub(r"\b(hoy|ayer)\b", " ", t)
    sin_dia = re.sub(r"\s+", " ", sin_dia).strip()
    cumplidos = (r"(que )?(habitos )?(hice|cumpli|logre|complete|termine)( de )?"
                 r"(habitos)?|que habitos (hice|cumpli|logre)|cuantos habitos (hice|cumpli)")
    faltantes = (r"que (me )?(falta|queda|resta)( por hacer| de hacer| hacer)?( de)?"
                 r"( habitos)?|que habitos (me )?(faltan|quedan|me falta)|"
                 r"cuales (me )?(faltan|quedan)( de)?( habitos)?")
    ambos = (r"como vengo( con (los |mis )?habitos)?|"
             r"(analiza|analizame|revisa|revisame|mira|mostrame|ver) "
             r"(mi |el |los |mis )?(tracker|habitos|tracker de habitos|habit quest)"
             r"( de notion)?|como van (mis |los )?habitos")
    for patron, que in ((cumplidos, "cumplidos"), (faltantes, "faltantes"),
                        (ambos, "ambos")):
        if re.fullmatch(patron, sin_dia):
            return "ver_habitos", lambda: habitos.ver_habitos(dia, que)


def _marcar_habitos(t):
    import habitos
    m = re.fullmatch(r"(marca|marcame|marcar|anota|anotame|tilda|tildame|registra)"
                     r"( que| como hecho| como cumplido)? (.+)", t)
    if not m:
        return None
    resto = m.group(3)
    hechos, _ = habitos.detectar_habitos(resto)
    if not hechos:
        return None                       # no sé qué hábito es: que decida Gemini
    dia = _dia(resto)
    return "marcar_habitos", lambda: habitos.marcar_habitos(resto, dia)


def _abrir(t):
    m = re.fullmatch(r"(abri|abre|abreme|abrime|abrir|abrirme|lanza|lanzame|inicia|iniciame|ejecuta|pone|ponme|ponele|prende|prendeme)"
                     r" (el |la |los |las |un |una )?(.+)", t)
    if not m:
        return None
    nombre = m.group(3).strip()
    import herramientas
    programas = {limpiar_clave(k): k for k in herramientas.PROGRAMAS}
    sitios = {limpiar_clave(k): k for k in herramientas.SITIOS}
    if nombre in programas:
        return "abrir_programa", lambda: herramientas.abrir_programa(programas[nombre])
    if nombre in sitios:
        return "abrir_sitio", lambda: herramientas.abrir_sitio(sitios[nombre])
    return None


def limpiar_clave(clave):
    texto = unicodedata.normalize("NFD", clave.lower())
    return "".join(c for c in texto if unicodedata.category(c) != "Mn")


def _volumen(t):
    import control_pc
    n = re.search(r"\b(\d{1,3})\b", t)
    porcentaje = min(100, int(n.group(1))) if n else 10
    if re.fullmatch(r"(sube|subi|subime|subile|subir|aumenta|aumentale)( el)? volumen( un)?( \d{1,3})?( por ciento)?", t):
        return "controlar_volumen", lambda: control_pc.controlar_volumen("subir", porcentaje)
    if re.fullmatch(r"(baja|bajame|bajalo|bajale|bajar|disminui)( el)? volumen( un)?( \d{1,3})?( por ciento)?", t):
        return "controlar_volumen", lambda: control_pc.controlar_volumen("bajar", porcentaje)
    if re.fullmatch(r"(silencia|silenciar|silenciame|mutea|mute|desilencia|desmutea)( el)?( volumen| sonido| audio)?", t):
        return "controlar_volumen", lambda: control_pc.controlar_volumen("silenciar")
    if n and re.fullmatch(r"(pone|poner|fija|fijar|deja|dejar|ajusta)( el)? volumen (al|a|en)( un)? \d{1,3}( por ciento)?", t):
        return "controlar_volumen", lambda: control_pc.controlar_volumen("fijar", porcentaje)


def _musica(t):
    import control_pc
    acciones = (
        (r"(pausa|pausar|pausala|pausalo|pausa( la)?( musica| cancion| video)?)", "pausa"),
        (r"(pone |dale |reanuda |reanudar )?(play|continua|continuar|segui|seguir)( la musica)?", "play"),
        (r"(siguiente|proxima|pasa|salta)( la)?( cancion| tema)?( siguiente)?|(la |el )?(siguiente|proximo)( cancion| tema)?", "siguiente"),
        (r"(anterior|volve|volver)( a)?( la)?( cancion| tema)?( anterior)?|(la |el )?anterior( cancion| tema)?", "anterior"),
    )
    for patron, accion in acciones:
        if re.fullmatch(patron, t):
            return "controlar_musica", lambda: control_pc.controlar_musica(accion)


def _agenda(t):
    m = (re.fullmatch(r"que tengo (hoy|manana|pasado manana)( en (la )?agenda| en el calendario)?", t)
         or re.fullmatch(r"(mi )?(agenda|calendario)( de)? (hoy|manana|pasado manana)", t))
    if not m:
        return None
    dia = {"hoy": "hoy", "manana": "mañana", "pasado manana": "pasado mañana"}[
        re.search(r"(pasado manana|manana|hoy)", t).group(1)]
    from calendario import consultar_agenda
    return "consultar_agenda", lambda: consultar_agenda(dia)


RECONOCEDORES = (_hora, _fecha, _ver_habitos, _marcar_habitos, _abrir,
                 _volumen, _musica, _agenda)


# ---------- Punto de entrada ----------
def responder_rapido(texto):
    """Devuelve (nombre_herramienta, respuesta) o None si no es un atajo."""
    if not ATAJOS_ACTIVOS or not texto:
        return None
    t = limpiar(texto)
    if not t:
        return None
    for reconocedor in RECONOCEDORES:
        try:
            encontrado = reconocedor(t)
            if encontrado is None:
                continue
            nombre, accion = encontrado
            return nombre, accion()
        except Exception as error:      # ante cualquier duda, que lo resuelva Gemini
            print(f"  [atajo] falló ({error}); lo resuelve Gemini")
            return None
    return None


if __name__ == "__main__":
    # Prueba en seco: muestra qué reconocedor atrapa cada frase
    pruebas = ["Jarvis, ¿qué hora es?", "¿Qué día es hoy?", "¿Qué hice hoy?",
               "¿Qué me falta hoy?", "¿Cómo vengo con los hábitos?",
               "Marcá que fui al gimnasio", "Abrí Spotify", "Subí el volumen",
               "Poné el volumen en 30", "Pausa", "Siguiente canción",
               "¿Qué tengo mañana?", "Contame un chiste",
               "¿Qué me falta comprar?", "Abrime el reactor nuclear"]
    for frase in pruebas:
        t = limpiar(frase)
        for r in RECONOCEDORES:
            try:
                if r(t) is not None:
                    print(f"{frase!r:40} -> {r.__name__}")
                    break
            except Exception as error:
                print(f"{frase!r:40} -> {r.__name__} (error: {error})")
                break
        else:
            print(f"{frase!r:40} -> Gemini")
