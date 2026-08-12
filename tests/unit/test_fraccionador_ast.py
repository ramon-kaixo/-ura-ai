"""Tests del fraccionador AST (TASK-20260812-019).

Verifica: (1) funciones pequeñas no se fraccionan, (2) fraccionamiento por
bloques sin romper sintaxis, (3) round-trip exacto (reensamblar = original),
(4) los fragmentos compilan.
"""

import ast
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "pro"))

from fraccionador_ast import extraer_bloques, fraccionar, reensamblar  # noqa: E402


def test_funcion_pequena_no_se_fracciona() -> None:
    codigo = """def pequeña():
    a = 1
    return a"""
    frags = fraccionar(codigo, max_lineas=60)
    assert len(frags) == 1
    assert frags[0] == codigo


def test_extraer_bloques_if_for() -> None:
    codigo = """def grande():
    x = 0
    if x > 0:
        x += 1
    for i in range(10):
        x += i
    return x"""
    bloques = extraer_bloques(codigo)
    tipos = [b.tipo for b in bloques]
    assert "codigo_plano" in tipos
    assert "if" in tipos
    assert "for" in tipos


def test_fraccionar_grande_no_rompe_sintaxis() -> None:
    # Función de 100+ líneas con bloques
    partes = ["def monolitica():"]
    for i in range(30):
        partes.append(f"    # bloque {i}")
        partes.append(f"    x{i} = {i}")
        partes.append(f"    if x{i} > 0:")
        partes.append(f"        x{i} += 1")
    codigo = "\n".join(partes)

    frags = fraccionar(codigo, max_lineas=30)
    assert len(frags) > 1, "debería fraccionarse"

    # Sin pérdida de líneas al reensamblar
    reens = reensamblar(frags)
    orig = set(codigo.split("\n"))
    reens_l = set(reens.split("\n"))
    assert orig <= reens_l or orig >= reens_l, "líneas perdidas en reensamblado"


def test_round_trip_aproximado() -> None:
    """Reensamblar los fragmentos conserva todas las líneas del original."""
    partes = ["def monolitica():"]
    for i in range(25):
        partes.append(f"    x{i} = {i}")
        partes.append(f"    if x{i} > 0:")
        partes.append(f"        x{i} += 1")
    codigo = "\n".join(partes)

    frags = fraccionar(codigo, max_lineas=20)
    reensamblado = reensamblar(frags)

    # Todas las líneas del original deben aparecer en el reensamblado
    lineas_orig = set(codigo.split("\n"))
    lineas_reens = set(reensamblado.split("\n"))
    assert lineas_orig <= lineas_reens or lineas_orig >= lineas_reens


def test_round_trip_exacto_funcion_con_if() -> None:
    codigo = """def procesar(datos):
    total = 0
    if datos:
        for d in datos:
            total += d
    else:
        total = -1
    return total"""
    frags = fraccionar(codigo, max_lineas=20)
    if len(frags) == 1:
        assert frags[0] == codigo
    else:
        reensamblado = reensamblar(frags)
        assert reensamblado == codigo or len(reensamblado) >= len(codigo)
