"""La calculadora evalúa con ast (nunca eval): cuentas exactas y nada de código arbitrario."""
import pytest

import herramientas


@pytest.mark.parametrize("cuenta, resultado", [
    ("17.5 * 23", "402.5"),
    ("2 ** 10", "1024"),
    ("raiz(144)", "12.0"),
])
def test_cuentas(cuenta, resultado):
    assert herramientas.calcular(cuenta) == f"{cuenta} = {resultado}"


def test_division_por_cero():
    assert herramientas.calcular("1 / 0") == "No se puede dividir por cero."


@pytest.mark.parametrize("malicioso", [
    "__import__('os').system('echo hacked')",
    "open('secreto.txt').read()",
    "().__class__.__bases__",
])
def test_no_ejecuta_codigo(malicioso):
    assert herramientas.calcular(malicioso).startswith("No pude calcular")
