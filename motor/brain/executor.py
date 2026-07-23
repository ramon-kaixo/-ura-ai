"""Ejecutor que conecta cerebro con tuneladora real.

Problema 1 resuelto: PipelineEngine(self) acepta config=None, pipeline=''.
Problema 2 resuelto: anade URA_ROOT a sys.path si no esta.
Problema 3 resuelto: convierte params a lista de strings para subprocess.
Mejora 1: status refleja returncode del script ejecutado.
Mejora 2: _proposal_to_args maneja bool, list, None, str, int/float.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

log = logging.getLogger("ura.brain.executor")

_URA_ROOT = Path(__file__).resolve().parents[2]
if str(_URA_ROOT) not in sys.path:
    sys.path.insert(0, str(_URA_ROOT))


class ProposalExecutor:
    """Ejecuta propuestas del cerebro usando PipelineEngine real."""

    def __init__(self) -> None:
        self._engine: Any = None

    def _get_engine(self) -> Any:
        if self._engine is None:
            try:
                from scripts.pro.tuneladora.engine import PipelineEngine

                self._engine = PipelineEngine()
            except ImportError as e:
                log.error("Cannot load PipelineEngine: %s", e)
                self._engine = None
        return self._engine

    @staticmethod
    def to_tuneladora_task(proposal: dict[str, Any]) -> dict[str, Any]:
        task_types = {
            "refactor": "code_quality",
            "split": "refactor",
            "test": "testing",
            "doc": "documentation",
        }
        return {
            "plugin": task_types.get(proposal.get("type", ""), "generic"),
            "target": proposal.get("target", ""),
            "params": proposal,
            "priority": proposal.get("priority", "low"),
        }

    @staticmethod
    def _proposal_to_args(proposal: dict[str, Any]) -> list[str]:
        """Convierte params de propuesta a lista de strings para subprocess.

        Maneja tipos: str, int, float, bool, list, None.
        """
        args: list[str] = []
        target = proposal.get("target", "")
        if target:
            args.append(f"--target={target}")
        priority = proposal.get("priority", "")
        if priority:
            args.append(f"--priority={priority}")
        for k, v in proposal.items():
            if k in ("type", "target", "priority"):
                continue
            if v is None:
                continue
            if isinstance(v, bool):
                if v:
                    args.append(f"--{k}")
            elif isinstance(v, list):
                for item in v:
                    args.append(f"--{k}={item}")
            elif isinstance(v, str) or isinstance(v, (int, float)):
                args.append(f"--{k}={v}")
        return args

    def execute(self, proposal: dict[str, Any]) -> dict[str, Any]:
        """Ejecuta propuesta via tuneladora real.

        Mejora 1: status refleja returncode del script (0=success, !=0=failed).
        """
        engine = self._get_engine()
        if engine is None:
            return {"error": "PipelineEngine not available"}

        task = self.to_tuneladora_task(proposal)
        args_list = self._proposal_to_args(proposal)

        try:
            result = engine.run_script(script=task["plugin"], args=args_list, timeout=300)
            script_ok = result.returncode == 0
            return {
                "status": "success" if script_ok else "failed",
                "returncode": result.returncode,
                "task": task,
                "result": {
                    "returncode": result.returncode,
                    "stdout": (result.stdout or "")[:1000],
                    "stderr": (result.stderr or "")[:500],
                },
            }
        except Exception as e:
            log.error("Execution failed: %s", e)
            return {"status": "error", "task": task, "error": str(e)}
