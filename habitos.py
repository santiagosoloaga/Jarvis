# habitos.py - JARVIS marca tus hábitos en el tracker "Habit Quest" de Notion.
#
# Le decís "hoy fui al gimnasio y estudié" y tilda esas casillas en la fila
# de hoy de tu base "Registro diario". El XP, los niveles y el personaje los
# calcula Notion solo (son fórmulas), así que acá solo tildamos casillas.
#
# Configuración (una sola vez):
#   1. notion.so/profile/integrations -> "Nueva integración" -> copiá el
#      secreto y pegalo en .env como:  NOTION_TOKEN=ntn_xxxxx
#   2. En Notion, abrí la página "Habit Quest — Tracker de hábitos" ->
#      menú "..." -> "Conexiones" -> agregá tu integración.
#   Sin el paso 2 Notion responde "object_not_found" (es lo más común).

import json
import os
import re
import unicodedata
import urllib.error
import urllib.request
from datetime import date, timedelta

# --- Configuración ---
# Las claves y los IDs de tu workspace viven en .env (salen de las URLs de las páginas):
#   NOTION_TOKEN=...            secreto de la integración
#   NOTION_BASE_REGISTRO=...    ID de la base "Registro diario"
#   NOTION_PAGINA_JUGADOR=...   ID de la página del jugador (relación "Jugador")
VERSION_API = "2022-06-28"
URL_API = "https://api.notion.com/v1"

DIAS_CORTOS = ("Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom")
MESES_CORTOS = ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago",
                "sep", "oct", "nov", "dic")

# Nombre EXACTO de la casilla en Notion -> palabras con las que lo nombrás.
# Cada palabra se busca al comienzo de una palabra de lo que dijiste
# ("estudi" encuentra estudié, estudiar, estudiando...).
HABITOS = {
    "🌅 Despertar antes de 10": ["despert", "levant"],
    "📝 Planificar": ["planific"],
    "🧹 Ordenar": ["orden", "limpi"],
    "😴 Dormir temprano": ["dorm", "acost"],
    "🏋️ Gimnasio": ["gimnasio", "gym", "entren"],
    "👟 8k pasos": ["pasos", "camin", "8k"],
    "💧 Agua": ["agua", "hidrat"],
    "🥗 Comer sano": ["comer sano", "comi sano", "comida sana", "saludable"],
    "📚 Estudiar": ["estudi", "robotica"],
    "🚀 Proyecto": ["proyecto", "jarvis"],
    "🎨 Dibujar/leer": ["dibuj", "lei ", "leer", "lectura", "leyendo"],
}
NEGACIONES = ("no ", "nunca ", "todavia no", "sin ")


# ---------- Utilidades ----------
def _limpiar(texto: str) -> str:
    """Minúsculas y sin tildes, para comparar fácil."""
    texto = unicodedata.normalize("NFD", str(texto).lower())
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", texto).strip()


def interpretar_dia_habito(texto: str, hoy: date | None = None) -> date | None:
    """Hoy, ayer, anteayer o una fecha concreta. Nunca el futuro."""
    hoy = hoy or date.today()
    t = _limpiar(texto)
    if t in ("", "hoy"):
        return hoy
    if t == "ayer":
        return hoy - timedelta(days=1)
    if t in ("anteayer", "antes de ayer", "antier"):
        return hoy - timedelta(days=2)
    if t.endswith("manana"):   # mañana / pasado mañana: no se puede marcar el futuro
        return None
    # "el jueves" = el jueves más reciente que ya pasó (acá no existe el futuro)
    from calendario import DIAS_SEMANA, interpretar_dia
    for numero, nombre in enumerate(DIAS_SEMANA):
        if re.search(rf"\b{nombre}\b", t):
            return hoy - timedelta(days=(hoy.weekday() - numero) % 7 or 7)
    fecha = interpretar_dia(t, hoy)   # "12/11", "12 de noviembre"...
    if fecha is not None and fecha > hoy:
        try:   # calendario.py adivina el futuro; para hábitos fue el año pasado
            fecha = fecha.replace(year=fecha.year - 1)
        except ValueError:
            return None
    if fecha is None or fecha > hoy:
        return None
    return fecha


def titulo_dia(fecha: date) -> str:
    """'Lun 16 nov': así se llaman las filas de tu Registro diario."""
    return f"{DIAS_CORTOS[fecha.weekday()]} {fecha.day} {MESES_CORTOS[fecha.month - 1]}"


def detectar_habitos(texto: str) -> tuple[list[str], list[str]]:
    """Devuelve (hábitos que SÍ hiciste, frases que ignoré por ser negativas)."""
    hechos: list[str] = []
    ignorados: list[str] = []
    # Cortamos en frases: "gimnasio, no estudié y tomé agua" -> 3 frases
    frases = re.split(r"[,;.]|\by\b|\be\b|\bpero\b|\baunque\b|\bademas\b|\btambien\b", _limpiar(texto) + " ")
    for frase in frases:
        frase = " " + frase.strip() + " "
        if len(frase.strip()) < 2:
            continue
        negativa = any(f" {n.strip()} " in frase or frase.strip().startswith(n)
                       for n in NEGACIONES)
        for casilla, palabras in HABITOS.items():
            if any(re.search(rf"\b{re.escape(p.strip())}", frase) for p in palabras):
                if negativa:
                    ignorados.append(frase.strip())
                elif casilla not in hechos:
                    hechos.append(casilla)
    return hechos, ignorados


def nombre_hablado(casilla: str) -> str:
    """'🏋️ Gimnasio' -> 'Gimnasio' (para decirlo en voz alta)."""
    return re.sub(r"^[^\wÁÉÍÓÚáéíóúñÑ]+\s*", "", casilla).strip()


# ---------- Comunicación con Notion ----------
def _config(nombre: str) -> str:
    """Lee un valor de configuración del entorno (o del .env); avisa claro si falta."""
    valor = os.environ.get(nombre)
    if not valor:
        from dotenv import load_dotenv
        load_dotenv()
        valor = os.environ.get(nombre)
    if not valor:
        raise RuntimeError(f"Falta {nombre} en el archivo .env")
    return valor


def _pedir(metodo: str, ruta: str, cuerpo: dict | None = None) -> dict:
    token = _config("NOTION_TOKEN")
    datos = json.dumps(cuerpo).encode("utf-8") if cuerpo is not None else None
    pedido = urllib.request.Request(
        f"{URL_API}{ruta}", data=datos, method=metodo,
        headers={"Authorization": f"Bearer {token}",
                 "Notion-Version": VERSION_API,
                 "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(pedido, timeout=15) as respuesta:
            return json.loads(respuesta.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detalle = ""
        try:
            detalle = json.loads(error.read().decode("utf-8")).get("code", "")
        except (ValueError, OSError):
            pass
        raise RuntimeError(f"Notion respondió {error.code} {detalle}".strip()) from error


def _fila_del_dia(fecha: date) -> dict:
    """Busca la fila de esa fecha; si no existe la crea."""
    resultado = _pedir("POST", f"/databases/{_config('NOTION_BASE_REGISTRO')}/query", {
        "filter": {"property": "Fecha", "date": {"equals": fecha.isoformat()}},
        "page_size": 1})
    if resultado.get("results"):
        return resultado["results"][0]
    return _pedir("POST", "/pages", {
        "parent": {"database_id": _config("NOTION_BASE_REGISTRO")},
        "properties": {
            "Día": {"title": [{"text": {"content": titulo_dia(fecha)}}]},
            "Fecha": {"date": {"start": fecha.isoformat()}},
            "Jugador": {"relation": [{"id": _config("NOTION_PAGINA_JUGADOR")}]},
        }})


def _casillas_tildadas(pagina: dict) -> list[str]:
    props = pagina.get("properties", {})
    return [c for c in HABITOS if props.get(c, {}).get("checkbox")]


def _fecha_hablada(fecha: date) -> str:
    hoy = date.today()
    if fecha == hoy:
        return "hoy"
    if fecha == hoy - timedelta(days=1):
        return "ayer"
    return titulo_dia(fecha)


# ---------- HERRAMIENTAS ----------
def marcar_habitos(habitos: str, dia: str = "hoy") -> str:
    """
    Marca en el tracker de hábitos de Notion lo que el usuario hizo.
    Usala cuando diga que cumplió hábitos: gimnasio, estudiar, agua, etc.

    Args:
        habitos: Lo que hizo, TAL CUAL lo dijo (por ejemplo "fui al gimnasio,
            estudié y tomé agua"). No lo reinterpretes.
        dia: Cuándo: hoy, ayer, anteayer, o una fecha como "12/11".
    """
    fecha = interpretar_dia_habito(dia)
    if fecha is None:
        return f"No entendí el día '{dia}'. Decime hoy, ayer o una fecha pasada."
    hechos, ignorados = detectar_habitos(habitos)
    if not hechos:
        extra = " Ignoré lo que dijiste en negativo." if ignorados else ""
        return ("No reconocí ningún hábito en lo que dijiste." + extra +
                " Los hábitos son: " +
                ", ".join(nombre_hablado(c) for c in HABITOS) + ".")
    try:
        fila = _fila_del_dia(fecha)
        antes = set(_casillas_tildadas(fila))
        nuevos = [c for c in hechos if c not in antes]
        if nuevos:
            fila = _pedir("PATCH", f"/pages/{fila['id']}", {
                "properties": {c: {"checkbox": True} for c in nuevos}})
    except RuntimeError as error:
        return f"No pude hablar con Notion: {error}."
    ya_estaban = [c for c in hechos if c in antes]
    total = len(_casillas_tildadas(fila))
    partes = []
    if nuevos:
        partes.append("Marqué " + ", ".join(nombre_hablado(c) for c in nuevos)
                      + f" para {_fecha_hablada(fecha)}.")
    if ya_estaban:
        partes.append("Ya estaban marcados: "
                      + ", ".join(nombre_hablado(c) for c in ya_estaban) + ".")
    if ignorados:
        partes.append("Dejé sin marcar lo que dijiste en negativo.")
    partes.append(f"Llevás {total} de {len(HABITOS)} hábitos.")
    try:   # el XP lo calcula Notion con una fórmula
        xp = fila["properties"]["XP"]["formula"].get("number")
        if xp is not None:
            partes.append(f"Sumás {round(xp)} de XP ese día.")
    except (KeyError, TypeError):
        pass
    return " ".join(partes)


def ver_habitos(dia: str = "hoy", que: str = "ambos") -> str:
    """
    Analiza el tracker de hábitos de Notion (Habit Quest, la "planilla" o
    "tabla" de hábitos): dice qué hábitos cumplió el usuario y cuáles le
    faltan en un día. Usala SIEMPRE que pida ver, revisar o analizar sus
    hábitos o el tracker de Notion, o pregunte qué cumplió o qué le falta.
    Nunca digas que no tenés acceso a Notion: tenés esta herramienta.

    Args:
        dia: hoy, ayer, anteayer, o una fecha como "12/11".
        que: "cumplidos" (solo lo que cumplió), "faltantes" (solo lo que le
            falta) o "ambos". Si pregunta solo qué cumplió, usá "cumplidos";
            si pregunta qué le falta, usá "faltantes".
    """
    fecha = interpretar_dia_habito(dia)
    if fecha is None:
        return f"No entendí el día '{dia}'. Decime hoy, ayer o una fecha pasada."
    try:
        resultado = _pedir("POST", f"/databases/{_config('NOTION_BASE_REGISTRO')}/query", {
            "filter": {"property": "Fecha", "date": {"equals": fecha.isoformat()}},
            "page_size": 1})
    except RuntimeError as error:
        return f"No pude hablar con Notion: {error}."
    cuando = _fecha_hablada(fecha).capitalize()
    if not resultado.get("results"):
        return f"No hay registro para {_fecha_hablada(fecha)} todavía."
    hechos = _casillas_tildadas(resultado["results"][0])
    faltan = [c for c in HABITOS if c not in hechos]
    def lista(casillas):
        return ", ".join(nombre_hablado(c) for c in casillas)

    que = _limpiar(que)
    if que.startswith("cumpl") or que.startswith("hech"):
        if not hechos:
            return f"{cuando} todavía no cumpliste ningún hábito."
        return f"{cuando} cumpliste {len(hechos)} de {len(HABITOS)}: {lista(hechos)}."
    if que.startswith("falt") or que.startswith("pend"):
        if not faltan:
            return f"{cuando} no te falta ninguno: ¡día perfecto!"
        return f"{cuando} te faltan {len(faltan)}: {lista(faltan)}."
    if not hechos:
        return f"{cuando} no marcaste ningún hábito todavía. Te faltan los {len(HABITOS)}."
    texto = f"{cuando} cumpliste {len(hechos)} de {len(HABITOS)}: {lista(hechos)}."
    texto += (f" Te faltan {lista(faltan)}." if faltan else " ¡Día perfecto!")
    return texto


HERRAMIENTAS_HABITOS = [marcar_habitos, ver_habitos]


if __name__ == "__main__":
    # Prueba rápida:  python habitos.py
    print(ver_habitos("hoy"))
