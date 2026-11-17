"""Hábitos: interpretar el día y detectar qué hábitos dijo el usuario (sin tocar Notion)."""
from datetime import date

import pytest

import habitos

MARTES = date(2026, 11, 17)


@pytest.mark.parametrize("texto, esperado", [
    ("hoy", MARTES),
    ("", MARTES),
    ("ayer", date(2026, 11, 16)),
    ("anteayer", date(2026, 11, 15)),
    ("el jueves", date(2026, 11, 12)),   # el jueves más reciente que ya pasó
])
def test_interpretar_dia(texto, esperado):
    assert habitos.interpretar_dia_habito(texto, MARTES) == esperado


def test_nunca_marca_el_futuro():
    assert habitos.interpretar_dia_habito("mañana", MARTES) is None


def test_titulo_de_la_fila_del_dia():
    assert habitos.titulo_dia(MARTES) == "Mar 17 nov"


def test_detecta_habitos_y_ignora_negaciones():
    hechos, ignorados = habitos.detectar_habitos("fui al gimnasio, no estudié y tomé agua")
    assert hechos == ["🏋️ Gimnasio", "💧 Agua"]
    assert ignorados == ["no estudie"]


def test_texto_sin_habitos():
    assert habitos.detectar_habitos("hoy llovió mucho") == ([], [])
