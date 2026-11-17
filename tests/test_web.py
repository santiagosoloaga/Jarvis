"""Servidor web del celular: clave obligatoria, chat y protección de rutas."""
import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

import web_jarvis

CLAVE = "clave-de-prueba"


@pytest.fixture
def servidor(monkeypatch):
    monkeypatch.setattr(web_jarvis, "CLAVE", CLAVE)
    monkeypatch.setattr(web_jarvis.time, "sleep", lambda s: None)   # sin la demora anti fuerza bruta
    monkeypatch.setattr(web_jarvis, "responder", lambda texto: (f"eco: {texto}", None))
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), web_jarvis.Manejador)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


def pedir(base, ruta, datos=None, clave=CLAVE):
    pedido = urllib.request.Request(base + ruta, data=datos, headers={"X-Clave": clave})
    try:
        with urllib.request.urlopen(pedido) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as error:
        return error.code, b""


def test_la_pagina_carga_sin_clave(servidor):
    estado, cuerpo = pedir(servidor, "/", clave="")
    assert estado == 200 and b"JARVIS" in cuerpo


def test_chat_con_clave_correcta(servidor):
    estado, cuerpo = pedir(servidor, "/chat", json.dumps({"texto": "hola"}).encode())
    assert estado == 200
    assert json.loads(cuerpo)["respuesta"] == "eco: hola"


def test_chat_con_clave_incorrecta_es_401(servidor):
    estado, _ = pedir(servidor, "/chat", b'{"texto": "hola"}', clave="mala")
    assert estado == 401


def test_mensaje_vacio_es_400(servidor):
    estado, _ = pedir(servidor, "/chat", b'{"texto": "  "}')
    assert estado == 400


def test_captura_no_permite_salir_de_la_carpeta(servidor):
    estado, _ = pedir(servidor, f"/captura?n=../../etc/passwd&k={CLAVE}")
    assert estado == 404
