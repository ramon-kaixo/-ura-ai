#!/usr/bin/env python3
"""Tests unitarios para los buzos del Enjambre."""

import json
import os
import subprocess

BUZOS_DIR = os.path.join(os.path.dirname(__file__), "..", "buzos")
MALETA = os.path.join(BUZOS_DIR, "maleta.json")


def test_maleta_json():
    with open(MALETA) as f:
        d = json.load(f)
    assert "academico" in d


def test_buzos_existen():
    for b in ["buzo_modelos.sh", "buzo_academico.sh", "buzo_practicas.sh", "buzo_descargas.sh"]:
        assert os.path.exists(os.path.join(BUZOS_DIR, b)), f"Falta {b}"


def test_buzo_academico_syntax():
    assert (
        subprocess.run(["bash", "-n", os.path.join(BUZOS_DIR, "buzo_academico.sh")]).returncode == 0
    )


def test_buzo_modelos_syntax():
    assert (
        subprocess.run(["bash", "-n", os.path.join(BUZOS_DIR, "buzo_modelos.sh")]).returncode == 0
    )


def test_bibliotecario_syntax():
    assert (
        subprocess.run(
            ["bash", "-n", os.path.join(os.path.dirname(__file__), "..", "bibliotecario.sh")]
        ).returncode
        == 0
    )


def test_python_syntax():
    for f in ["scripts/certify.py", "agents/registry_api.py"]:
        assert subprocess.run(["python3", "-m", "py_compile", f]).returncode == 0, f"Error en {f}"


if __name__ == "__main__":
    test_maleta_json()
    test_buzos_existen()
    test_buzo_academico_syntax()
    test_buzo_modelos_syntax()
    test_bibliotecario_syntax()
    test_python_syntax()
    print("✅ Todos los tests de buzos pasaron")
