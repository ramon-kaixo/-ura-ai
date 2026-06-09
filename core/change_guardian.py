#!/usr/bin/env python3
"""
URA Change Guardian — Guardián de cambios con rollback automático
Solo revierte archivos que YA existían y fueron modificados.
NUNCA borra archivos nuevos — solo deshace modificaciones.
"""

import json
import logging
import subprocess
import sys
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

ROOT = Path(__file__).parent.parent
PATTERNS_FILE = ROOT / "logs" / "failure_patterns.json"
PATTERNS_FILE.parent.mkdir(exist_ok=True)


def _git(*args) -> tuple[bool, str]:
    result = subprocess.run(["git", *args], capture_output=True, text=True, cwd=ROOT)
    return result.returncode == 0, result.stdout.strip() or result.stderr.strip()


def _get_modified_tracked_files() -> list[str]:
    """Solo archivos YA en git que fueron modificados — nunca archivos nuevos."""
    _, out = _git("diff", "--name-only")
    return [f for f in out.splitlines() if f.strip()]


def _load_patterns() -> list[dict]:
    if PATTERNS_FILE.exists():
        try:
            return json.loads(PATTERNS_FILE.read_text())
        except Exception:
            return []
    return []


def _save_pattern(change_type: str, files: list[str], error_summary: str, diff: str):
    patterns = _load_patterns()
    patterns.append(
        {
            "fecha": datetime.now().isoformat(),
            "tipo_cambio": change_type,
            "archivos": files,
            "error": error_summary[:500],
            "diff_head": diff[:2000],
        }
    )
    PATTERNS_FILE.write_text(json.dumps(patterns, indent=2, ensure_ascii=False))
    logger.warning("Patrón de fallo registrado: %s en %s", change_type, files)


class ChangeGuardian:
    """
    Uso:
        with ChangeGuardian("descripción del cambio") as g:
            # modificar archivos existentes
            ...
        # Si los tests fallan, revierte SOLO los archivos modificados
    """

    def __init__(self, description: str, test_timeout: int = 360):
        self.description = description
        self.test_timeout = test_timeout
        self._modified_before: list[str] = []

    def __enter__(self) -> "ChangeGuardian":
        self._modified_before = _get_modified_tracked_files()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        if exc_type is not None:
            logger.error("Excepción durante '%s': %s", self.description, exc_val)
            self._rollback(reason=f"excepción: {exc_val}")
            return False

        passed, error = self._run_tests()
        if passed:
            logger.info("✅ Cambio '%s' validado — tests OK", self.description)
        else:
            self._rollback(reason=error)
        return False

    def _run_tests(self) -> tuple[bool, str]:
        try:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pytest",
                    str(ROOT / "tests"),
                    "--tb=line",
                    "-q",
                    "--no-header",
                    "-x",
                ],
                capture_output=True,
                text=True,
                timeout=self.test_timeout,
                cwd=ROOT,
            )
            output = result.stdout + result.stderr
            passed = result.returncode == 0
            summary = [l for l in output.splitlines() if l.strip()][-3:]
            return passed, "\n".join(summary)
        except subprocess.TimeoutExpired:
            return False, f"Tests superaron {self.test_timeout}s"
        except Exception as e:
            return False, str(e)

    def _rollback(self, reason: str):
        logger.warning("❌ Revirtiendo '%s' — %s", self.description, reason[:200])
        _, diff = _git("diff")

        # Solo revertir archivos tracked modificados — NUNCA borrar archivos nuevos
        modified_now = _get_modified_tracked_files()
        if modified_now:
            _git("checkout", "--", *modified_now)
            logger.info("Revertidos: %s", modified_now)

        _save_pattern(self.description, modified_now, reason, diff)
        logger.info("Rollback completado. Archivos nuevos preservados.")


def validate_and_clean(description: str = "cambio manual") -> bool:
    """
    Ejecuta tests ahora. Si fallan, revierte SOLO archivos modificados.
    Devuelve True si OK, False si revirtió.
    """
    guardian = ChangeGuardian(description)
    passed, error = guardian._run_tests()
    if not passed:
        _, diff = _git("diff")
        modified = _get_modified_tracked_files()
        _save_pattern(description, modified, error, diff)
        if modified:
            _git("checkout", "--", *modified)
        logger.warning("validate_and_clean: revertidos %s", modified)
        return False
    return True


def get_failure_patterns() -> list[dict]:
    return _load_patterns()


def get_failure_summary() -> str:
    patterns = _load_patterns()
    if not patterns:
        return "Sin fallos registrados"
    lines = [f"- [{p['fecha'][:10]}] {p['tipo_cambio']}: {p['error'][:80]}" for p in patterns[-10:]]
    return "\n".join(lines)
