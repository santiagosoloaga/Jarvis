"""Calendario: las fechas y horas las calcula Python, nunca el modelo."""
from datetime import date

import pytest

import calendario

MARTES = date(2026, 11, 17)


@pytest.mark.parametrize("texto, esperado", [
    ("hoy", date(2026, 11, 17)),
    ("mañana", date(2026, 11, 18)),
    ("pasado mañana", date(2026, 11, 19)),
    ("viernes", date(2026, 11, 20)),
    ("martes", date(2026, 11, 24)),          # mismo día = la semana que viene
    ("19/11", date(2026, 11, 19)),
    ("19 de noviembre", date(2026, 11, 19)),
    ("2027-01-05", date(2027, 1, 5)),
    ("10/11", date(2027, 11, 10)),           # sin año y ya pasó: el año que viene
])
def test_interpretar_dia(texto, esperado):
    assert calendario.interpretar_dia(texto, MARTES) == esperado


def test_fecha_imposible_da_none():
    assert calendario.interpretar_dia("31/02/2026", MARTES) is None


@pytest.mark.parametrize("texto, esperado", [
    ("15:30", (15, 30)),
    ("3 de la tarde", (15, 0)),
    ("10hs", (10, 0)),
    ("10 y media", (10, 30)),
    ("", None),
])
def test_interpretar_hora(texto, esperado):
    assert calendario.interpretar_hora(texto) == esperado


def test_hora_inexistente_falla():
    with pytest.raises(ValueError):
        calendario.interpretar_hora("25:00")
