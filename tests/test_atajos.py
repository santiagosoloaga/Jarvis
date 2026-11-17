"""Atajos: reconocer pedidos comunes sin Gemini y NO atrapar lo que no entienden."""
from datetime import datetime

import pytest

import atajos


@pytest.mark.parametrize("entrada, esperado", [
    ("¡Abrí Spotify, por favor!", "abri spotify"),
    ("Jarvis, ¿qué hora es?", "que hora es"),
    ("  Gracias   che  ", ""),
])
def test_limpiar_normaliza_texto(entrada, esperado):
    assert atajos.limpiar(entrada) == esperado


def test_hora_hablada_en_palabras():
    assert atajos.hora_hablada(datetime(2026, 1, 1, 15, 5)) == "las tres y cinco de la tarde"


@pytest.mark.parametrize("frase", ["¿Qué hora es?", "Subí el volumen", "¿Qué hice hoy?"])
def test_frases_comunes_son_atajos(frase):
    texto = atajos.limpiar(frase)
    assert any(r(texto) is not None for r in atajos.RECONOCEDORES)


@pytest.mark.parametrize("frase", ["hola cómo andás", "contame un chiste", "¿quién ganó el mundial?"])
def test_lo_que_no_encaja_va_a_gemini(frase):
    """Ante la duda devuelve None para que lo resuelva el modelo."""
    assert atajos.responder_rapido(frase) is None


def test_atajos_se_pueden_apagar(monkeypatch):
    monkeypatch.setattr(atajos, "ATAJOS_ACTIVOS", False)
    assert atajos.responder_rapido("¿qué hora es?") is None
