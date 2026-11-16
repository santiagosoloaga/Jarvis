# calendario.py - JARVIS y tu Google Calendar
#   1) agregar_evento    -> "agendame Termodinámica el jueves a las 10"
#   2) consultar_agenda  -> "¿qué tengo mañana?"
#
# IDEA CLAVE: la IA NO calcula fechas. Le pasa a estas funciones el
# texto tal cual lo dijiste ("jueves", "mañana", "19/11", "10 y media")
# y es ESTE codigo el que lo convierte en una fecha exacta. Igual que
# con las planillas: las cuentas las hace Python, no el modelo.
#
# PRIMERA VEZ: corré  python calendario.py  para autorizar a JARVIS
# en el navegador. Se guarda token.json y no te lo vuelve a pedir.
#
# SEGURIDAD: credentials.json y token.json son la llave de tu
# calendario. Estan en .gitignore: NUNCA los subas a GitHub.

import re
import unicodedata
from datetime import date, datetime, timedelta
from pathlib import Path

# ---------- CONFIGURACION ----------
CARPETA = Path(__file__).resolve().parent
CREDENCIALES = CARPETA / "credentials.json"   # lo bajás de Google Cloud
TOKEN = CARPETA / "token.json"                # se crea solo al autorizar

# Permiso MINIMO: ver y editar eventos. No da acceso a la configuracion
# de la cuenta ni a otros servicios de Google.
PERMISOS = ["https://www.googleapis.com/auth/calendar.events"]

CALENDARIO = "primary"                  # tu calendario principal
ZONA = "America/Argentina/Cordoba"
DESFASE = "-03:00"                      # Argentina no tiene horario de verano
DURACION_POR_DEFECTO = 60               # minutos
MAX_EVENTOS = 8                         # cuantos lee en voz alta

DIAS_SEMANA = ("lunes", "martes", "miercoles", "jueves", "viernes",
               "sabado", "domingo")
MESES = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre")

_servicio = None                        # conexion reutilizable


# ---------- CONEXION CON GOOGLE ----------
def servicio():
    # Se conecta una sola vez. Los import van ACA adentro: si no
    # instalaste las librerias de Google, el resto de JARVIS sigue
    # funcionando y solo falla esta herramienta, con un aviso claro.
    global _servicio
    if _servicio is not None:
        return _servicio
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    credenciales = None
    if TOKEN.exists():
        credenciales = Credentials.from_authorized_user_file(str(TOKEN), PERMISOS)
    if not credenciales or not credenciales.valid:
        if credenciales and credenciales.expired and credenciales.refresh_token:
            credenciales.refresh(Request())          # renueva sin preguntar
        else:
            if not CREDENCIALES.exists():
                raise RuntimeError("falta credentials.json en la carpeta jarvis")
            flujo = InstalledAppFlow.from_client_secrets_file(
                str(CREDENCIALES), PERMISOS)
            credenciales = flujo.run_local_server(port=0)  # abre el navegador
        TOKEN.write_text(credenciales.to_json(), encoding="utf-8")
    _servicio = build("calendar", "v3", credentials=credenciales,
                      cache_discovery=False)
    return _servicio


# ---------- ENTENDER FECHAS Y HORAS (Python, no la IA) ----------
def _limpiar(texto):
    # "Miércoles" -> "miercoles" (sin tildes ni mayusculas)
    texto = unicodedata.normalize("NFD", str(texto).lower())
    return "".join(c for c in texto if unicodedata.category(c) != "Mn").strip()


def interpretar_dia(texto, hoy=None):
    # Convierte lo que dijiste en una fecha. Devuelve date o None.
    hoy = hoy or date.today()
    t = _limpiar(texto)
    if t in ("", "hoy"):
        return hoy
    if "pasado manana" in t:
        return hoy + timedelta(days=2)
    if t == "manana":
        return hoy + timedelta(days=1)

    # "jueves", "el jueves", "el jueves que viene"
    for numero, nombre in enumerate(DIAS_SEMANA):
        if re.search(rf"\b{nombre}\b", t):
            faltan = (numero - hoy.weekday()) % 7
            return hoy + timedelta(days=faltan or 7)   # mismo dia = la otra semana

    # "2026-11-19"
    iso = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", t)
    if iso:
        anio, mes, dia = map(int, iso.groups())
        return _fecha_valida(anio, mes, dia)

    # "19/11", "19-11", "19/11/2026", "19/11/26"
    numeros = re.fullmatch(r"(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?", t)
    if numeros:
        dia, mes, anio = numeros.groups()
        return _con_anio(int(dia), int(mes), anio, hoy)

    # "19 de noviembre", "19 de noviembre de 2026"
    palabras = re.fullmatch(r"(\d{1,2}) de ([a-z]+)(?: de (\d{4}))?", t)
    if palabras and palabras.group(2) in MESES:
        dia, mes, anio = palabras.groups()
        return _con_anio(int(dia), MESES.index(mes) + 1, anio, hoy)
    return None


def _fecha_valida(anio, mes, dia):
    try:
        return date(anio, mes, dia)
    except ValueError:                 # 31/02 y cosas asi
        return None


def _con_anio(dia, mes, anio, hoy):
    # Sin año: este año, o el que viene si esa fecha ya pasó
    if anio:
        anio = int(anio)
        return _fecha_valida(anio + 2000 if anio < 100 else anio, mes, dia)
    fecha = _fecha_valida(hoy.year, mes, dia)
    if fecha and fecha < hoy:
        fecha = _fecha_valida(hoy.year + 1, mes, dia)
    return fecha


def interpretar_hora(texto):
    # "10" "10:30" "10.30" "10hs" "10 y media" "3 de la tarde" -> (h, m)
    # Devuelve None si no hay hora (evento de dia completo) y lanza
    # ValueError si hay algo que no se entiende.
    t = _limpiar(texto)
    t = re.sub(r"(\d)\s*hs?\b", r"\1", t)      # "10hs", "10 h" -> "10"
    t = re.sub(r"(\d)h(\d)", r"\1:\2", t)       # "10h30" -> "10:30"
    t = t.strip(" :")
    if not t:
        return None
    encontrado = re.match(r"(\d{1,2})(?:[:.](\d{2}))?", t)
    if not encontrado:
        raise ValueError(f"no entiendo la hora '{texto}'")
    hora = int(encontrado.group(1))
    minutos = int(encontrado.group(2) or 0)
    if "y media" in t:
        minutos = 30
    elif "y cuarto" in t:
        minutos = 15
    if any(p in t for p in ("tarde", "noche")) and hora < 12:
        hora += 12                     # "3 de la tarde" -> 15
    if not (0 <= hora <= 23 and 0 <= minutos <= 59):
        raise ValueError(f"la hora '{texto}' no existe")
    return hora, minutos


def fecha_hablada(fecha):
    # date(2026, 11, 19) -> "jueves 19 de noviembre"
    nombre = ("lunes", "martes", "miércoles", "jueves", "viernes",
              "sábado", "domingo")[fecha.weekday()]
    return f"{nombre} {fecha.day} de {MESES[fecha.month - 1]}"


def armar_evento(titulo, fecha, hora_minuto, duracion):
    # Arma el "paquete" que entiende Google Calendar
    if hora_minuto is None:                      # dia completo
        return {
            "summary": titulo,
            "start": {"date": fecha.isoformat()},
            "end": {"date": (fecha + timedelta(days=1)).isoformat()},
        }
    inicio = datetime(fecha.year, fecha.month, fecha.day, *hora_minuto)
    fin = inicio + timedelta(minutes=duracion)
    return {
        "summary": titulo,
        "start": {"dateTime": inicio.isoformat(), "timeZone": ZONA},
        "end": {"dateTime": fin.isoformat(), "timeZone": ZONA},
    }


# ---------- HERRAMIENTA 1: agregar un evento ----------
def agregar_evento(titulo: str, dia: str, hora: str = "",
                   duracion_minutos: int = DURACION_POR_DEFECTO) -> str:
    """
    Agrega un evento al Google Calendar del usuario. Pasá el día y la hora TAL CUAL los dijo el usuario, sin convertirlos: este código calcula la fecha exacta.

    Args:
        titulo: Qué es, por ejemplo "Estudiar Termodinámica" o "Reunión en Cabildo"
        dia: Como lo dijo el usuario: "hoy", "mañana", "jueves", "19/11" o "19 de noviembre"
        hora: Como la dijo el usuario: "10", "10:30", "3 de la tarde". Vacío si es todo el día
        duracion_minutos: Cuánto dura, en minutos (normalmente 60)
    """
    titulo = str(titulo).strip()
    if not titulo:
        return "Necesito saber qué evento querés agendar."
    fecha = interpretar_dia(dia)
    if fecha is None:
        return (f"No entendí el día '{dia}'. Decime por ejemplo "
                "'mañana', 'el jueves' o '19 de noviembre'.")
    try:
        hora_minuto = interpretar_hora(hora)
        duracion = int(float(duracion_minutos or DURACION_POR_DEFECTO))
    except ValueError as error:
        return f"No pude agendarlo: {error}."
    if not 1 <= duracion <= 24 * 60:
        return "La duración tiene que ser entre 1 minuto y 24 horas."
    if hora_minuto and datetime(fecha.year, fecha.month, fecha.day,
                                *hora_minuto) < datetime.now():
        return (f"El {fecha_hablada(fecha)} a esa hora ya pasó. "
                "¿Querés otro día?")

    evento = armar_evento(titulo, fecha, hora_minuto, duracion)
    try:
        servicio().events().insert(calendarId=CALENDARIO, body=evento).execute()
    except ModuleNotFoundError:
        return ("Me faltan las librerías de Google Calendar. Instalalas "
                "con pip install -r requirements.txt.")
    except Exception as error:
        return f"No pude conectarme con Google Calendar ({str(error)[:80]})."

    cuando = fecha_hablada(fecha)
    if hora_minuto:
        cuando += f" a las {hora_minuto[0]}:{hora_minuto[1]:02d}"
    else:
        cuando += ", todo el día"
    return f"Agendé '{titulo}' el {cuando}."


# ---------- HERRAMIENTA 2: consultar la agenda ----------
def consultar_agenda(dia: str = "hoy") -> str:
    """
    Dice qué eventos tiene el usuario en su Google Calendar un día. Pasá el día tal cual lo dijo el usuario.

    Args:
        dia: Como lo dijo el usuario: "hoy", "mañana", "jueves" o "19/11"
    """
    fecha = interpretar_dia(dia)
    if fecha is None:
        return f"No entendí el día '{dia}'."
    desde = f"{fecha.isoformat()}T00:00:00{DESFASE}"
    hasta = f"{(fecha + timedelta(days=1)).isoformat()}T00:00:00{DESFASE}"
    try:
        resultado = servicio().events().list(
            calendarId=CALENDARIO, timeMin=desde, timeMax=hasta,
            singleEvents=True, orderBy="startTime", maxResults=MAX_EVENTOS,
        ).execute()
    except ModuleNotFoundError:
        return ("Me faltan las librerías de Google Calendar. Instalalas "
                "con pip install -r requirements.txt.")
    except Exception as error:
        return f"No pude conectarme con Google Calendar ({str(error)[:80]})."

    eventos = resultado.get("items", [])
    if not eventos:
        return f"No tenés nada agendado el {fecha_hablada(fecha)}."
    partes = []
    for evento in eventos:
        nombre = evento.get("summary", "sin título")
        inicio = evento.get("start", {}).get("dateTime")
        if inicio:                     # "2026-11-19T10:00:00-03:00" -> 10:00
            partes.append(f"a las {inicio[11:16]}, {nombre}")
        else:
            partes.append(f"todo el día, {nombre}")
    return f"El {fecha_hablada(fecha)} tenés: " + "; ".join(partes) + "."


HERRAMIENTAS_CALENDARIO = [agregar_evento, consultar_agenda]


# ---------- PRIMERA VEZ / PRUEBA ----------
# python calendario.py -> autoriza a JARVIS y muestra tu agenda de hoy
if __name__ == "__main__":
    print("Conectando con Google Calendar (la primera vez se abre el navegador)...")
    servicio()
    print("¡Autorizado! Se guardó token.json.\n")
    print(consultar_agenda("hoy"))
    print(consultar_agenda("mañana"))
