"""Tests para URA Transporter (6 modos de operación)."""

import os
import subprocess
import tempfile
import json
import pytest

TRANSPORTER = os.path.join(os.path.dirname(__file__), "..", "scripts", "ura_transporter.py")


def setup_inventory():
    """Crea un inventario temporal de prueba"""
    data = {"agents": [{"id": "test_agent", "type": "test", "path": "/tmp/test_agent.py"}]}
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    json.dump(data, f)
    f.close()
    # Crear archivo dummy
    with open("/tmp/test_agent.py", "w") as f2:
        f2.write("# test agent")
    return f.name


@pytest.fixture(autouse=True)
def mock_inventory_env():
    inv_path = setup_inventory()
    os.environ["REPO_ROOT"] = "/tmp"
    yield
    os.unlink(inv_path)
    if os.path.exists("/tmp/test_agent.py"):
        os.unlink("/tmp/test_agent.py")


def test_transporter_sintaxis():
    r = subprocess.run(["python3", "-m", "py_compile", TRANSPORTER], capture_output=True, text=True)
    assert r.returncode == 0, f"Error sintaxis: {r.stderr}"


def test_transporter_list():
    r = subprocess.run(["python3", TRANSPORTER, "--list"], capture_output=True, text=True)
    assert r.returncode == 0
    assert "Elementos" in r.stdout


def test_transporter_find_existente():
    r = subprocess.run(
        ["python3", TRANSPORTER, "--find", "test_agent"], capture_output=True, text=True
    )
    assert r.returncode == 0
    assert "test_agent" in r.stdout


def test_transporter_find_inexistente():
    r = subprocess.run(
        ["python3", TRANSPORTER, "--find", "no_existe"], capture_output=True, text=True
    )
    assert r.returncode == 0
    assert "Sin resultados" in r.stdout


def test_transporter_copy_sin_destino():
    r = subprocess.run(
        ["python3", TRANSPORTER, "--copy", "test_agent"], capture_output=True, text=True
    )
    assert r.returncode != 0


def test_transporter_sin_comandos():
    r = subprocess.run(["python3", TRANSPORTER], capture_output=True, text=True)
    assert r.returncode != 0  # Sin args = error esperado
    assert "Especifica" in r.stdout or "--list" in r.stdout or "Uso" in r.stdout
