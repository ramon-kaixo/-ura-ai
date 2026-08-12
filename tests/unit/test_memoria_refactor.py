"""Tests de memoria_refactor.py (TASK-20260812-023) — cobertura 100%."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "pro"))

from memoria_refactor import (
    cargar_memoria,
    consultar_funcion,
    guardar_memoria,
    registrar_intento,
    resumen,
)


@pytest.fixture()
def root(tmp_path: Path) -> Path:
    return tmp_path


def test_cargar_memoria_vacia(root: Path) -> None:
    m = cargar_memoria(root)
    assert m["funciones"] == {}
    assert m["metricas"]["intentos"] == 0


def test_cargar_memoria_corrupta(root: Path) -> None:
    (root / ".nervioso").mkdir(exist_ok=True)
    (root / ".nervioso" / "refactor_memoria.json").write_text("{json invalido")
    m = cargar_memoria(root)
    assert m["funciones"] == {}


def test_guardar_y_recargar(root: Path) -> None:
    m = cargar_memoria(root)
    m["funciones"]["test"] = {"intentos": [], "estado": "pendiente"}
    guardar_memoria(root, m)
    m2 = cargar_memoria(root)
    assert "test" in m2["funciones"]


def test_registrar_primer_intento(root: Path) -> None:
    m = registrar_intento(root, "archivo.py:func", "modelo1", "exito", "ok")
    f = m["funciones"]["archivo.py:func"]
    assert len(f["intentos"]) == 1
    assert f["intentos"][0]["modelo"] == "modelo1"
    assert f["estado"] == "completada"
    assert m["metricas"]["exitos"] == 1


def test_registrar_rechazo_estado_pendiente(root: Path) -> None:
    registrar_intento(root, "a.py:f", "m1", "rechazo", "razon")
    f = consultar_funcion(root, "a.py:f")
    assert f["estado"] == "pendiente"
    assert f["intentos"][0]["motivo"] == "razon"


def test_dos_rechazos_necesita_otro_modelo(root: Path) -> None:
    registrar_intento(root, "b.py:f", "m1", "rechazo", "r1")
    registrar_intento(root, "b.py:f", "m1", "rechazo", "r2")
    f = consultar_funcion(root, "b.py:f")
    assert f["estado"] == "necesita_otro_modelo"


def test_exito_tras_rechazos_completa(root: Path) -> None:
    registrar_intento(root, "c.py:f", "m1", "rechazo", "r1")
    registrar_intento(root, "c.py:f", "m2", "exito", "ok")
    f = consultar_funcion(root, "c.py:f")
    assert f["estado"] == "completada"


def test_consultar_sin_historial(root: Path) -> None:
    f = consultar_funcion(root, "noexiste.py:x")
    assert f["estado"] == "sin_intentar"
    assert f["intentos"] == []


def test_resumen_metricas(root: Path) -> None:
    registrar_intento(root, "d.py:f", "m1", "exito", "ok")
    registrar_intento(root, "d.py:f", "m1", "rechazo", "no")
    r = resumen(root)
    assert r["intentos"] == 2
    assert r["exitos"] == 1
    assert r["rechazos"] == 1


def test_registrar_intento_rechazo(tmp_path: Path) -> None:
    """resultado='rechazo' -> incrementa rechazos (87->90)."""
    from memoria_refactor import registrar_intento

    memoria = registrar_intento(tmp_path, "a.py:f", "m", "rechazo")
    assert memoria["metricas"]["rechazos"] == 1
    assert memoria["metricas"]["exitos"] == 0
    assert memoria["metricas"]["intentos"] == 1
    assert memoria["funciones"]["a.py:f"]["estado"] == "pendiente"


def test_registrar_intento_error(tmp_path: Path) -> None:
    """resultado='error' -> no incrementa exito ni rechazo (87->90)."""
    from memoria_refactor import registrar_intento

    memoria = registrar_intento(tmp_path, "a.py:f", "m", "error")
    assert memoria["metricas"]["exitos"] == 0
    assert memoria["metricas"]["rechazos"] == 0
    assert memoria["metricas"]["intentos"] == 1
