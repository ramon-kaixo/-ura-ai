"""Unit tests para commit_msg_validator.py — conventional commits."""

from __future__ import annotations

import pytest

from scripts.pro.commit_msg_validator import validate


class TestValidMessages:
    @pytest.mark.parametrize(
        "msg",
        [
            "feat: nueva funcionalidad",
            "fix(cli): corregido bug de stdout",
            "test(qdrant): día 2 con 33 tests",
            "docs: actualizada documentación",
            "refactor(motor): extraído executor",
            "chore: limpieza general",
            "perf(fusion): timeline cache o(1)",
            "build: actualizar dependencias",
            "ci: añadir nightly pipeline",
            "style: reformatear archivos",
            "revert: revertir cambio anterior",
            "fix!: breaking change",
            "FIX(core): case insensitive tipo",
            "feat(scope-con-123): con guiones y números",
        ],
    )
    def test_accepts_conventional(self, msg: str) -> None:
        ok, _reason = validate(msg)
        assert ok

    def test_accepts_body(self) -> None:
        ok, _reason = validate("fix(cli): primera línea válida\n\ncuerpo con detalles\nsegunda línea")
        assert ok

class TestInvalidMessages:
    @pytest.mark.parametrize(
        "msg,substr",
        [
            ("", "vacío"),
            ("wip", "placeholder"),
            ("tmp", "placeholder"),
            ("update", "placeholder"),
            ("merge branch x", "placeholder"),
            ("feat", "formato"),
            ("feat:", "formato"),
            ("feat: corto", "formato"),
            ("foo(bar): descripción cualquiera", "formato"),
            ("  ", "vacío"),
            ("fix(cli): " + "x" * 200, "larga"),
        ],
    )
    def test_rejects_invalid(self, msg: str, substr: str) -> None:
        ok, reason = validate(msg)
        assert not ok
        assert substr in reason

    def test_rejects_consecutive_blank_lines(self) -> None:
        ok, _reason = validate("fix(cli): válida\n\n\ncuerpo")
        assert not ok

    def test_allows_single_blank_separator(self) -> None:
        ok, _reason = validate("fix(cli): descripción válida\n\ncuerpo")
        assert ok


class TestMutationSensitivity:
    def test_mutation_forbidden_regex_removed(self) -> None:
        """Si se elimina la regla FORBIDDEN_RE, 'wip' debe pasar — este test
        falla si eso ocurre (mutation testing)."""
        ok, _reason = validate("wip")
        assert not ok

    def test_mutation_conventional_regex_removed(self) -> None:
        """Si se elimina CONVENTIONAL_RE, 'foo: bar baz' pasaría."""
        ok, _reason = validate("foo: bar baz qux")
        assert not ok

    def test_mutation_length_check_removed(self) -> None:
        """Si se elimina el check de longitud, mensajes >100 chars pasarían."""
        ok, _reason = validate("fix: " + "x" * 200)
        assert not ok
