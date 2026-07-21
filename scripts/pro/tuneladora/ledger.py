"""ExecutionLedger — registro inmutable de ejecuciones del pipeline.

Cada ejecución genera una entrada con:
  estado inicial, acciones, resultados, métricas, artefactos, estado final.

Permite responder:
  ¿Cuándo empezó a degradarse este plugin?
  ¿Qué ejecución introdujo este cambio?
  ¿Cuál fue la última ejecución que modificó este archivo?
"""

from __future__ import annotations

import json
import platform
import subprocess
import time
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path


class ExecutionLedger:
    """Registro único de ejecuciones.

    Almacena en .nervioso/ledger/ una entrada JSON por ejecución.
    El archivo es inmutable una vez escrito.
    """

    def __init__(self, nervioso: Path, pipeline: str) -> None:
        self._nervioso = nervioso
        self._pipeline = pipeline
        self._execution_id: str = uuid.uuid4().hex[:12]
        self._start = time.monotonic()
        self._entry: dict[str, Any] = self._create_entry()

    def _create_entry(self) -> dict[str, Any]:
        return {
            "execution_id": self._execution_id,
            "pipeline": self._pipeline,
            "engine_version": "2.3",
            "start_time": datetime.now(UTC).isoformat(),
            "end_time": "",
            "duration_ms": 0,
            "host": platform.node(),
            "python_version": platform.python_version(),
            "trigger": "manual",
            "git_commit_before": "",
            "git_commit_after": "",
            "snapshot_id": "",
            "phases": {},
            "phases_executed": [],
            "phases_skipped": [],
            "plugins_activated": [],
            "plugins_disabled": [],
            "changed_files": 0,
            "changed_lines": 0,
            "tests_passed": 0,
            "benchmarks": {},
            "promotion": False,
            "rollback": False,
            "warnings": [],
            "errors": [],
            "resources": {},
            "result": "unknown",
            "report_id": "",
            "goal": None,
            "decisions": [],
            "alternatives": [],
            "plan": None,
            "evaluation": None,
            "pattern_detections": [],
            "knowledge": [],
            "recommendations": [],
            "policies": [],
            "verifications": [],
        }

    def set_trigger(self, trigger: str) -> None:
        self._entry["trigger"] = trigger

    def phase_start(self, phase: str) -> None:
        self._entry["phases_executed"].append(phase)

    def phase_skip(self, phase: str) -> None:
        self._entry["phases_skipped"].append(phase)

    def plugin_done(self, name: str, duration_s: float, status: str = "ok") -> None:
        self._entry["plugins_activated"].append(name)
        self._entry.setdefault("plugin_durations", {})[name] = round(duration_s, 1)
        self._entry.setdefault("plugin_status", {})[name] = status

    def add_warning(self, msg: str) -> None:
        self._entry["warnings"].append(msg)

    def add_error(self, msg: str) -> None:
        self._entry["errors"].append(msg)

    def set_promotion(self, ok: bool) -> None:
        self._entry["promotion"] = ok

    def set_rollback(self, ok: bool) -> None:
        self._entry["rollback"] = ok

    def set_changes(self, files: int, lines: int) -> None:
        self._entry["changed_files"] = files
        self._entry["changed_lines"] = lines

    def set_result(self, result: str) -> None:
        self._entry["result"] = result

    def set_git_commit(self, before: str = "", after: str = "") -> None:
        try:
            if not before:
                before = subprocess.run(
                    ["git", "rev-parse", "HEAD"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=False,
                ).stdout.strip()
            self._entry["git_commit_before"] = before
            self._entry["git_commit_after"] = after or before
        except Exception:
            pass

    def set_goal(self, goal: dict) -> None:
        self._entry["goal"] = goal

    def add_decision(self, decision_type: str, payload: dict) -> None:
        self._entry.setdefault("decisions", []).append(
            {
                "type": decision_type,
                "timestamp": datetime.now(UTC).isoformat(),
                **payload,
            }
        )

    def add_alternative(self, strategy: str, reason_not_chosen: str) -> None:
        self._entry.setdefault("alternatives", []).append(
            {
                "strategy": strategy,
                "reason_not_chosen": reason_not_chosen,
            }
        )

    def set_plan(self, plan: dict) -> None:
        self._entry["plan"] = plan

    def set_evaluation(self, score: float, action: str, criteria: dict) -> None:
        self._entry["evaluation"] = {
            "score": score,
            "action": action,
            "criteria": criteria,
        }

    def set_snapshot_id(self, sid: str) -> None:
        self._entry["snapshot_id"] = sid

    def add_pattern(self, pattern: dict) -> None:
        self._entry.setdefault("pattern_detections", []).append(pattern)

    def add_knowledge(self, knowledge: dict) -> None:
        self._entry.setdefault("knowledge", []).append(knowledge)

    def add_recommendation(self, recommendation: dict) -> None:
        self._entry.setdefault("recommendations", []).append(recommendation)

    def add_policy(self, policy: dict) -> None:
        self._entry.setdefault("policies", []).append(policy)

    def add_verification(self, verification: dict) -> None:
        self._entry.setdefault("verifications", []).append(verification)

    def resource_sample(self) -> None:
        try:
            rc, out = subprocess.getstatusoutput("free -m")
            if rc == 0:
                for line in out.splitlines():
                    if "Mem:" in line:
                        parts = line.split()
                        self._entry["resources"]["ram_used_mb"] = int(parts[2])
            rc, out = subprocess.getstatusoutput("ps aux | grep -c 'python'")
            if rc == 0:
                self._entry["resources"]["python_processes"] = int(out.strip())
        except Exception:
            pass

    def save(self) -> Path:
        elapsed = time.monotonic() - self._start
        self._entry["end_time"] = datetime.now(UTC).isoformat()
        self._entry["duration_ms"] = int(elapsed * 1000)

        ledger_dir = self._nervioso / "ledger"
        ledger_dir.mkdir(parents=True, exist_ok=True)

        path = ledger_dir / f"{self._execution_id}.json"
        path.write_text(json.dumps(self._entry, indent=2, ensure_ascii=False))
        return path
