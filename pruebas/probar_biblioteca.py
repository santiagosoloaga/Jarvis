# probar_biblioteca.py - Busca en la biblioteca de voces de Google una voz
# con acento argentino. Uso (desde la carpeta del proyecto):  python pruebas/probar_biblioteca.py
# Prueba varios filtros y versiones de la API, e imprime lo que encuentre.

import sys
from pathlib import Path

# Este script vive en pruebas/: agregamos la carpeta de arriba para poder
# importar voz_nube.py y compañía.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import os

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()
clave = os.environ.get("GEMINI_API_KEY")


def mostrar(voz):
    campos = {}
    for nombre in ("name", "voice_name", "display_name", "accent", "gender",
                   "language_code", "language_codes", "contexts", "description"):
        valor = getattr(voz, nombre, None)
        if valor not in (None, "", []):
            campos[nombre] = valor
    print("   ", campos or str(voz)[:200])


def lista(respuesta):
    voces = getattr(respuesta, "voices", None)
    if voces is None:
        try:
            voces = list(respuesta)
        except TypeError:
            voces = []
    # Si "list" devolvió campos sueltos (tuplas) en vez de voces, no hay voces
    return [v for v in voces if not isinstance(v, tuple)]


intentos = []
for version in (None, "v1beta", "v1alpha"):
    opciones = types.HttpOptions(api_version=version) if version else None
    cliente = genai.Client(api_key=clave, http_options=opciones)
    intentos += [
        (f"sin filtros (api={version})", cliente, {"page_size": 100}),
        (f"es-AR (api={version})", cliente, {"language_code": ["es-AR"], "page_size": 100}),
        (f"accent Argentine (api={version})", cliente,
         {"accent": ["Argentine", "Argentinian", "Argentinean", "Rioplatense"]}),
    ]

for nombre, cliente, filtros in intentos:
    try:
        voces = lista(cliente.voices.list(**filtros))
        print(f"{nombre}: {len(voces)} voces")
        for voz in voces[:12]:
            mostrar(voz)
    except Exception as error:
        print(f"{nombre}: FALLA {str(error)[:160]}")
