"""Tests de cobertura para knowledge/engine/errors.py."""

from __future__ import annotations

from knowledge.engine.errors import (
    _ALL_CODES,
    KE001,
    KE204,
    KE207,
    ErrorCode,
    Severity,
    _register,
    all_codes,
    lookup,
)


def test_severity_enum() -> None:
    assert Severity.ERROR.value == "ERROR"
    assert Severity.WARN.value == "WARN"
    assert Severity.DEPRECATED.value == "DEPRECATED"
    assert Severity.INFO.value == "INFO"
    assert str(Severity.INFO) == "INFO"


def test_errorcode_dataclass() -> None:
    assert KE001.code == "KE001"
    assert KE001.severity == Severity.ERROR
    assert KE001.title == "Missing title"
    assert "frontmatter" in KE001.description
    assert KE204.severity == Severity.DEPRECATED
    assert KE207.severity == Severity.INFO


def test_registro_automatico() -> None:
    assert len(all_codes()) >= 20
    codes = {c.code for c in all_codes()}
    assert {"KE001", "KE010", "KE109", "KE201", "KE210"} <= codes


def test_lookup() -> None:
    assert lookup("KE001") is KE001
    assert lookup("KE999") is None


def test_all_codes_ordenados() -> None:
    codes = all_codes()
    assert codes == sorted(codes, key=lambda c: c.code)


def test_register_manual() -> None:
    _previo = dict(_ALL_CODES)
    try:
        nuevo = ErrorCode("KE999", Severity.INFO, "Test", "Código de prueba")
        _register(nuevo)
        assert lookup("KE999") is nuevo
    finally:
        _ALL_CODES.clear()
        _ALL_CODES.update(_previo)
