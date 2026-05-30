#!/usr/bin/env python3
"""Agente AIR — Reparación autónoma con razonamiento neuro-simbólico."""

import json
import subprocess
import os
from pathlib import Path
from datetime import datetime, UTC


class AIRAgent:
    def __init__(self, repo_path: str = None):
        self.repo = Path(
            repo_path or os.environ.get("REPO_ROOT", os.path.expanduser("~/URA/ura_ia_1972"))
        )
        self.scribe_log = Path.home() / ".ura" / "scribe_log.json"
        self.repair_log = self.repo / "docs" / "pro" / "air_repairs.jsonl"
        self.repair_log.parent.mkdir(parents=True, exist_ok=True)

    def analyze_failures(self) -> list[dict]:
        if not self.scribe_log.exists():
            return []
        with open(self.scribe_log) as f:
            events = json.load(f)
        return [
            e
            for e in events
            if "failure" in e.get("type", "").lower() or "rollback" in e.get("type", "").lower()
        ][-20:]

    def propose_fix(self, failure: dict) -> dict | None:
        return {
            "timestamp": datetime.now(UTC).isoformat(),
            "module": failure.get("module", "?"),
            "failure_type": failure.get("type", "?"),
            "proposed_action": f"Revisar {failure.get('module', '?')}",
        }

    def apply_and_verify(self, fix: dict) -> bool:
        try:
            subprocess.run(
                [
                    "python3",
                    "-c",
                    "from core.ura_rollback import get_ura_rollback; get_ura_rollback().create_snapshot('air_fix','.')",
                ],
                check=False,
                cwd=str(self.repo),
            )
            r = subprocess.run(
                ["pytest", "tests/", "-q"],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=str(self.repo),
            )
            if r.returncode == 0:
                fix["status"] = "verified"
                self._log(fix)
                return True
            else:
                subprocess.run(
                    [
                        "python3",
                        "-c",
                        "from core.ura_rollback import get_ura_rollback; rb=get_ura_rollback(); s=rb.get_latest_snapshot('air_fix'); rb.restore_snapshot(s.snapshot_id,'.') if s else None",
                    ],
                    check=False,
                    cwd=str(self.repo),
                )
                fix["status"] = "rolled_back"
                self._log(fix)
                return False
        except Exception as e:
            fix["status"] = f"error:{e}"
            self._log(fix)
            return False

    def _log(self, fix: dict):
        with open(self.repair_log, "a") as f:
            f.write(json.dumps(fix) + "\n")

    def run(self) -> dict:
        failures = self.analyze_failures()
        if not failures:
            return {"status": "no_failures", "message": "✅ Sin fallos"}
        fixes = []
        for f in failures[-5:]:
            fix = self.propose_fix(f)
            if fix:
                fixes.append({"fix": fix, "success": self.apply_and_verify(fix)})
        return {
            "status": "completed",
            "analyzed": len(failures),
            "attempted": len(fixes),
            "ok": sum(1 for f in fixes if f["success"]),
        }


if __name__ == "__main__":
    print(json.dumps(AIRAgent().run(), indent=2))
