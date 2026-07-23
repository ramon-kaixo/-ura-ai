"""ARQ Check Plugin — verificación arquitectónica automatizada.

Se ejecuta al final de la fase post. Si hay FAIL en ARQ, la promoción
se bloquea hasta que se corrijan las violaciones.

Integración con PromotionPolicy:
  engine.promotion.record("arq_architectura", ok, detail)
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from scripts.pro.tuneladora.engine import PipelineEngine

URA_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent


class ARQCheckPlugin:
    """Plugin que ejecuta el ARQ Auditor y registra el resultado."""

    def __init__(self, engine: PipelineEngine) -> None:
        self.engine = engine

    def check(self) -> dict[str, Any]:
        """Ejecuta arq_auditor.py --json y retorna resultados."""
        try:
            r = subprocess.run(
                [sys.executable, str(URA_ROOT / "scripts/pro/arq_auditor.py"), "--json"],
                capture_output=True,
                text=True,
                timeout=120,
                cwd=str(URA_ROOT),
                check=False,
            )
        except subprocess.TimeoutExpired:
            return {"status": "error", "detail": "ARQ Auditor timeout (120s)", "ok": False}

        if r.returncode != 0 and not r.stdout:
            return {"status": "error", "detail": r.stderr[:200], "ok": False}

        try:
            data = json.loads(r.stdout)
        except json.JSONDecodeError:
            return {"status": "error", "detail": "ARQ output no es JSON", "ok": False}

        blocks = data.get("blocks", {})
        total_fail = sum(1 for block_list in blocks.values() for f in block_list if f.get("level") in ("FAIL", "P0"))
        total_warn = sum(
            1 for block_list in blocks.values() for f in block_list if f.get("level") in ("WARNING", "MEDIUM")
        )

        ok = total_fail == 0
        detail = f"{total_fail} FAIL, {total_warn} WARN" if not ok else "0 FAIL"
        self.engine.promotion.record("arq_architectura", ok, detail)

        return {
            "status": "ok" if ok else "fail",
            "ok": ok,
            "total_fail": total_fail,
            "total_warn": total_warn,
            "detail": detail,
        }
