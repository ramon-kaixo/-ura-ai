"""Tests de idempotencia: verifica que ejecutar comandos multiples veces produce el mismo resultado.

GX10: verifica servicios y git.
Anywhere: verifica que git status es estable.
"""

from __future__ import annotations

import pytest

from tests.infra.conftest import run_cmd


@pytest.mark.anywhere
class TestGitIdempotency:
    """Verifica que git status es estable entre ejecuciones."""

    def test_git_status_twice_same_result(self) -> None:
        _, out1, _ = run_cmd("git status --short", timeout=15)
        _, out2, _ = run_cmd("git status --short", timeout=15)
        assert out1 == out2, "git status cambia entre ejecuciones consecutivas"

    def test_git_diff_twice_same_result(self) -> None:
        _, out1, _ = run_cmd("git diff --stat", timeout=15)
        _, out2, _ = run_cmd("git diff --stat", timeout=15)
        assert out1 == out2, "git diff cambia entre ejecuciones consecutivas"


@pytest.mark.gx10
class TestServiceIdempotency:
    """Verifica que servicios estables no cambian entre lecturas."""

    @pytest.mark.parametrize(
        "service",
        [
            "opencode.service",
            "ollama.service",
        ],
    )
    def test_service_status_stable(self, service: str) -> None:
        _, out1, _ = run_cmd(f"systemctl is-active {service}")
        _, out2, _ = run_cmd(f"systemctl is-active {service}")
        assert out1 == out2, f"Estado de {service} cambia: {out1} != {out2}"
