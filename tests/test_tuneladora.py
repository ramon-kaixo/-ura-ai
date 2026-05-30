"""Tests para la Tuneladora — orquestación de 7 rodillos."""

import subprocess
import os

TUNELADORA = os.path.expanduser("~/bin/auto_cleanup.sh")


def test_tuneladora_existe():
    assert os.path.exists(TUNELADORA), "Tuneladora debe existir"


def test_tuneladora_ejecutable():
    assert os.access(TUNELADORA, os.X_OK), "Tuneladora debe ser ejecutable"


def test_tuneladora_sintaxis():
    r = subprocess.run(["bash", "-n", TUNELADORA], capture_output=True, text=True)
    assert r.returncode == 0, f"Error sintaxis: {r.stderr}"


def test_tuneladora_tiene_7_rodillos():
    with open(TUNELADORA) as f:
        c = f.read()
    rodillos = [l for l in c.split("\n") if "RODILLO" in l]
    assert len(rodillos) >= 7, f"Debe tener 7 rodillos, tiene {len(rodillos)}"


def test_tuneladora_tiene_quarantine():
    with open(TUNELADORA) as f:
        c = f.read()
    assert "quarantine_files" in c, "Debe tener función de cuarentena"


def test_tuneladora_tiene_trigger_seguridad():
    with open(TUNELADORA) as f:
        c = f.read()
    assert "trigger_security_sandbox" in c, "Debe tener trigger de seguridad"


def test_tuneladora_sin_shell_true():
    """Verifica que no hay shell=True en subprocess"""
    with open(TUNELADORA) as f:
        for i, line in enumerate(f, 1):
            assert "shell=True" not in line, f"shell=True detectado en línea {i}"
