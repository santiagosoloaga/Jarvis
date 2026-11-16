# informacion.py - Herramientas de INFORMACION de JARVIS:
#   1) buscar_en_google     -> noticias, resultados, cosas de hoy
#                              (Google Noticias: gratis y sin clave)
#   2) resumir_pdf          -> resume un PDF tuyo (apuntes, papers)
#   3) consultar_planilla   -> lee un Excel/CSV tuyo y responde sobre el
#
# SEGURIDAD: JARVIS solo puede leer archivos dentro de CARPETAS.
# El modelo nunca elige una ruta: elige un NOMBRE y este codigo lo
# busca en esas carpetas (lista blanca, como con los programas).
#
# PRIVACIDAD: con Gemini gratis, lo que le mandas (incluido el PDF)
# Google lo puede usar para mejorar sus productos. No le pases
# documentos privados (sueldos, datos de clientes, contratos).
# Por eso USAR_GEMINI_EN_ARCHIVOS viene en False: tus archivos se
# procesan 100% en tu compu con Ollama. Ponelo en True solo si
# aceptas mandarlos a Google (Gemini lee mejor tablas e imagenes).

import csv
import os
import re
import unicodedata
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

import ollama
from google.genai import types
from openpyxl import load_workbook
from pypdf import PdfReader

import gemini

# ---------- CONFIGURACION ----------
CASA = Path.home()
CARPETAS = [
    Path(__file__).resolve().parent / "documentos",   # la del proyecto
    CASA / "Documents",
    CASA / "Downloads",
    CASA / "Desktop",
    CASA / "OneDrive" / "Documentos",
    CASA / "OneDrive" / "Escritorio",
]
MAX_ARCHIVOS_REVISADOS = 5000   # para no recorrer el disco entero

# Busqueda: "noticias" = Google Noticias (gratis, sin clave).
# "gemini" = Google Search dentro de Gemini: mejor, pero NO funciona
# con la cuota gratis (necesita cuenta paga en AI Studio).
MODO_BUSQUEDA = "noticias"
MAX_TITULARES = 6
USAR_GEMINI_EN_ARCHIVOS = False  # True = Gemini lee tus PDFs/Excel (Google puede usarlos)
# Modelos para estas tareas, en orden (si uno falla, prueba el otro)
MODELOS_GEMINI = ["gemini-3.5-flash-lite", "gemini-3.6-flash"]
MODELO_LOCAL = "llama3.2:3b"
MAX_TEXTO_LOCAL = 8000          # caracteres de PDF que lee Ollama
MAX_FILAS = 60                  # filas de la planilla que se muestran

# Palabras que no sirven para buscar el archivo
RELLENO = {"el", "la", "los", "las", "de", "del", "mi", "mis", "un",
           "una", "apunte", "apuntes", "archivo", "pdf", "excel",
           "planilla", "documento", "sobre", "que", "tengo"}
CARPETAS_IGNORADAS = {".venv", "node_modules", ".git", "__pycache__",
                      "AppData"}

CABECERAS = {"User-Agent": "JARVIS/1.0 (asistente personal)"}


def pedir_a_gemini(contenido, config=None):
    respuesta, _ = gemini.pedir(MODELOS_GEMINI, contenido, config)
    return respuesta


def normalizar(texto):
    # "Apunte_Materiales-2026.pdf" -> "apunte materiales 2026 pdf"
    texto = unicodedata.normalize("NFD", texto.lower())
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    for signo in "_-.()[],":
        texto = texto.replace(signo, " ")
    return texto


def buscar_archivo(nombre, extensiones):
    # Busca en CARPETAS el archivo que mejor coincide con el nombre.
    # Puntaje = cuantas palabras del pedido aparecen en el nombre del
    # archivo (o de su carpeta). Si empatan, gana el mas nuevo.
    palabras = [p for p in normalizar(nombre).split() if p not in RELLENO]
    if not palabras:
        return None
    mejor, mejor_puntaje, mejor_fecha = None, 0, 0
    revisados = 0
    for carpeta in CARPETAS:
        if not carpeta.is_dir():
            continue
        for raiz, subcarpetas, archivos in os.walk(carpeta):
            # Saltamos carpetas ocultas y pesadas
            subcarpetas[:] = [s for s in subcarpetas
                              if not s.startswith(".")
                              and s not in CARPETAS_IGNORADAS]
            for archivo in archivos:
                revisados += 1
                if revisados > MAX_ARCHIVOS_REVISADOS:
                    return mejor
                ruta = Path(raiz) / archivo
                if ruta.suffix.lower() not in extensiones:
                    continue
                donde = normalizar(f"{ruta.parent.name} {ruta.stem}")
                puntaje = sum(1 for p in palabras if p in donde)
                if puntaje == 0:
                    continue
                fecha = ruta.stat().st_mtime
                if (puntaje, fecha) > (mejor_puntaje, mejor_fecha):
                    mejor, mejor_puntaje, mejor_fecha = ruta, puntaje, fecha
    return mejor


def no_encontrado(nombre, tipo):
    return (f"No encontré ningún {tipo} parecido a '{nombre}'. "
            "Lo busco en Documentos, Descargas, Escritorio y en la "
            "carpeta 'documentos' del proyecto JARVIS.")


# ---------- 1) BUSCAR EN GOOGLE ----------
def hace_cuanto(fecha):
    # datetime -> "hace 3 horas" / "hace 2 días"
    horas = (datetime.now(timezone.utc) - fecha).total_seconds() / 3600
    if horas < 1:
        return "hace minutos"
    if horas < 24:
        return f"hace {int(horas)} horas"
    dias = int(horas // 24)
    return "ayer" if dias == 1 else f"hace {dias} días"


def buscar_en_noticias(pregunta):
    # Google Noticias publica un RSS (un XML) por cada busqueda.
    # hl/gl/ceid = idioma y pais: edicion argentina en español.
    parametros = urllib.parse.urlencode(
        {"q": pregunta, "hl": "es-419", "gl": "AR"})
    # ceid va aparte: su ":" no tiene que convertirse en "%3A"
    url = f"https://news.google.com/rss/search?{parametros}&ceid=AR:es-419"
    pedido = urllib.request.Request(url, headers=CABECERAS)
    with urllib.request.urlopen(pedido, timeout=10) as respuesta:
        raiz = ET.fromstring(respuesta.read())

    # Cada <item> del XML es una noticia: titulo, fecha y medio
    noticias = []
    for item in raiz.iter("item"):
        titulo = item.findtext("title", "")
        medio = item.findtext("source", "")
        try:
            fecha = parsedate_to_datetime(item.findtext("pubDate", ""))
        except (TypeError, ValueError):
            fecha = datetime(2000, 1, 1, tzinfo=timezone.utc)
        if medio and titulo.endswith(f" - {medio}"):
            titulo = titulo[: -len(medio) - 3]       # sacamos " - Ole"
        noticias.append((fecha, titulo, medio))
        if len(noticias) >= 10:                      # los 10 mas relevantes
            break
    if not noticias:
        return f"No encontré noticias sobre: {pregunta}."

    # De esos 10, mostramos primero los mas NUEVOS
    noticias.sort(reverse=True)
    lineas = [f"Titulares de Google Noticias sobre '{pregunta}':"]
    for fecha, titulo, medio in noticias[:MAX_TITULARES]:
        lineas.append(f"- {titulo} ({medio}, {hace_cuanto(fecha)})")
    return "\n".join(lineas)


def buscar_con_gemini(pregunta):
    # Google Search dentro de Gemini (solo con cuenta paga)
    config = types.GenerateContentConfig(
        tools=[types.Tool(google_search=types.GoogleSearch())],
        system_instruction=(
            "Respondé en español rioplatense, en dos o tres frases, "
            "con el dato concreto y la fecha si importa."),
    )
    return (pedir_a_gemini(pregunta, config).text or "").strip()


def buscar_en_google(pregunta: str) -> str:
    """
    Busca en Google Noticias información ACTUAL. Usala para noticias,
    resultados deportivos, eventos recientes o cualquier dato que pueda
    haber cambiado hace poco. Devuelve titulares recientes con su
    fecha y medio: respondé usando esos titulares.

    Args:
        pregunta: Palabras clave cortas, por ejemplo "Argentina Uruguay resultado" o "Talleres"
    """
    if MODO_BUSQUEDA == "gemini":
        try:
            texto = buscar_con_gemini(pregunta)
            if texto:
                return texto
        except Exception as error:
            print(f"  [busqueda] Gemini no pudo ({error}); uso Noticias")
    try:
        return buscar_en_noticias(pregunta)
    except Exception as error:
        return f"No pude buscar en internet ({str(error)[:60]})."


# ---------- 2) RESUMIR UN PDF ----------
PEDIDO_RESUMEN = (
    "Resumí este documento en español rioplatense en 4 o 5 frases: "
    "de qué trata y sus ideas principales. Sin listas ni símbolos: "
    "se va a leer en voz alta."
)


def texto_del_pdf(ruta, maximo):
    # Saca el texto pagina por pagina hasta juntar "maximo" letras
    lector = PdfReader(ruta)
    partes, total = [], 0
    for pagina in lector.pages:
        texto = pagina.extract_text() or ""
        partes.append(texto)
        total += len(texto)
        if total >= maximo:
            break
    return " ".join(" ".join(partes).split())[:maximo], len(lector.pages)


def resumir_pdf(nombre: str) -> str:
    """
    Busca un PDF del usuario por su nombre (apuntes, papers, manuales)
    y devuelve un resumen. Por ejemplo "el apunte de Materiales".

    Args:
        nombre: Palabras del nombre del archivo, por ejemplo "materiales" o "datasheet servo"
    """
    ruta = buscar_archivo(nombre, {".pdf"})
    if ruta is None:
        return no_encontrado(nombre, "PDF")
    print(f"  [archivo] {ruta}")

    # Plan A: Gemini lee el PDF entero (entiende hasta tablas e imagenes)
    if USAR_GEMINI_EN_ARCHIVOS and ruta.stat().st_size < 19_000_000:
        try:
            pdf = types.Part.from_bytes(data=ruta.read_bytes(),
                                        mime_type="application/pdf")
            respuesta = pedir_a_gemini([pdf, PEDIDO_RESUMEN])
            if respuesta.text:
                return f"Resumen de {ruta.name}: {respuesta.text.strip()}"
        except Exception as error:
            print(f"  [pdf] Gemini falló, sigo en local: {str(error)[:80]}")

    # Plan B: sacamos el texto y lo resume Ollama (100% local)
    texto, paginas = texto_del_pdf(ruta, MAX_TEXTO_LOCAL)
    if not texto:
        return (f"Encontré {ruta.name}, pero no tiene texto: "
                "parece un escaneo (imágenes).")
    respuesta = ollama.chat(model=MODELO_LOCAL, messages=[
        {"role": "user", "content": f"{PEDIDO_RESUMEN}\n\n{texto}"},
    ])
    aviso = "" if len(texto) < MAX_TEXTO_LOCAL else (
        f" (Leí solo el principio: tiene {paginas} páginas.)")
    return f"Resumen de {ruta.name}: {respuesta.message.content}{aviso}"


# ---------- 3) CONSULTAR UNA PLANILLA ----------
def a_numero(valor):
    # 1234.5 / "1234.5" / "1.234,5" / "$ 1.234,5" -> 1234.5 ; texto -> None
    if isinstance(valor, bool):
        return None
    if isinstance(valor, (int, float)):
        return float(valor)
    texto = str(valor).replace("$", "").replace(" ", "").strip()
    if "," in texto:                   # formato argentino: 1.234,5
        texto = texto.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(\.\d{3})+", texto):   # 8.500 = ocho mil
        texto = texto.replace(".", "")
    try:
        return float(texto)
    except ValueError:
        return None


def numero_lindo(n):
    # 375007.5 -> "375007.5" ; 30.0 -> "30" (2 decimales, sin ceros de mas)
    return f"{n:.2f}".rstrip("0").rstrip(".")


def es_fila_total(fila):
    # Filas como "Total | | 30": no hay que volver a sumarlas
    return any(isinstance(v, str) and normalizar(v).strip().startswith(
        ("total", "subtotal")) for v in fila)


def describir_tabla(nombre_hoja, filas):
    # Encabezado + estadisticas exactas de cada columna numerica +
    # las primeras filas. Las cuentas las hace Python, no el modelo.
    filas = [f for f in filas if any(v not in (None, "") for v in f)]
    if not filas:
        return f"Hoja '{nombre_hoja}': vacía."
    encabezado = [str(v) if v is not None else f"col{i + 1}"
                  for i, v in enumerate(filas[0])]
    datos = filas[1:]
    para_cuentas = [f for f in datos if not es_fila_total(f)]
    lineas = [f"Hoja '{nombre_hoja}': {len(datos)} filas. "
              f"Columnas: {', '.join(encabezado)}."]
    for i, columna in enumerate(encabezado):
        numeros = [a_numero(f[i]) for f in para_cuentas if i < len(f)]
        numeros = [n for n in numeros if n is not None]
        if len(numeros) >= max(1, len(para_cuentas) // 2):  # numerica
            lineas.append(
                f"  {columna}: suma {numero_lindo(sum(numeros))}, promedio "
                f"{numero_lindo(sum(numeros) / len(numeros))}, mínimo "
                f"{numero_lindo(min(numeros))}, máximo "
                f"{numero_lindo(max(numeros))} ({len(numeros)} valores)")
    lineas.append(f"Primeras {min(MAX_FILAS, len(datos))} filas:")
    lineas.append(" | ".join(encabezado))
    for fila in datos[:MAX_FILAS]:
        lineas.append(" | ".join("" if v is None else str(v) for v in fila))
    return "\n".join(lineas)


def consultar_planilla(nombre: str) -> str:
    """
    Busca una planilla del usuario (Excel o CSV) por su nombre y
    devuelve su contenido con totales, promedios, mínimos y máximos
    ya calculados, para responder preguntas sobre esos datos.
    Solo archivos Excel o CSV guardados en la compu. NO sirve para
    Notion, ni para el tracker de hábitos (Habit Quest): para eso usá
    ver_habitos o marcar_habitos.

    Args:
        nombre: Palabras del nombre del archivo, por ejemplo "gastos" o "ventas octubre"
    """
    ruta = buscar_archivo(nombre, {".xlsx", ".xlsm", ".csv"})
    if ruta is None:
        return no_encontrado(nombre, "Excel o CSV")
    print(f"  [archivo] {ruta}")

    partes = [f"Archivo {ruta.name}."]
    if ruta.suffix.lower() == ".csv":
        with open(ruta, newline="", encoding="utf-8-sig") as f:
            muestra = f.read(4096)
            f.seek(0)
            separador = ";" if muestra.count(";") > muestra.count(",") else ","
            partes.append(describir_tabla(ruta.stem,
                                          list(csv.reader(f, delimiter=separador))))
    else:
        # data_only=True: trae el RESULTADO de las formulas, no "=SUMA(...)"
        libro = load_workbook(ruta, read_only=True, data_only=True)
        for hoja in libro.worksheets[:3]:              # max 3 hojas
            filas = list(hoja.iter_rows(values_only=True))
            partes.append(describir_tabla(hoja.title, filas))
        libro.close()
    return "\n".join(partes)


HERRAMIENTAS_INFO = [buscar_en_google, resumir_pdf, consultar_planilla]


# ---------- PRUEBA ----------
# python informacion.py -> prueba las 3 sin pasar por el cerebro
if __name__ == "__main__":
    print(buscar_en_google("¿Cómo salió Talleres en su último partido?"))
    print(resumir_pdf(input("\nNombre de un PDF tuyo: ")))
    print(consultar_planilla(input("\nNombre de un Excel tuyo: ")))
