"""Tests para scripts/pro/tuneladora/ledger.py (ExecutionLedger + SQLite)."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from scripts.pro.tuneladora.ledger import (
    ExecutionLedger,
    cleanup_history,
    get_history,
    save_execution,
)


@pytest.fixture
def ledger(tmp_path: Path) -> ExecutionLedger:
    return ExecutionLedger(tmp_path, "mejora")


class TestExecutionLedger:
    def test_init_crea_entry(self, ledger: ExecutionLedger) -> None:
        assert ledger._entry["pipeline"] == "mejora"
        assert ledger._entry["result"] == "unknown"
        assert ledger._entry["trigger"] == "manual"
        assert len(ledger._execution_id) == 12

    def test_setters_basicos(self, ledger: ExecutionLedger) -> None:
        ledger.set_trigger("gate")
        ledger.phase_start("static")
        ledger.phase_skip("commit")
        ledger.plugin_done("ruff", 1.5, "ok")
        ledger.add_warning("w1")
        ledger.add_error("e1")
        ledger.set_promotion(True)
        ledger.set_rollback(False)
        ledger.set_changes(3, 120)
        ledger.set_result("completed")
        ledger.set_snapshot_id("snap-1")

        e = ledger._entry
        assert e["trigger"] == "gate"
        assert "static" in e["phases_executed"]
        assert "commit" in e["phases_skipped"]
        assert e["plugin_durations"]["ruff"] == 1.5
        assert e["plugin_status"]["ruff"] == "ok"
        assert e["warnings"] == ["w1"]
        assert e["errors"] == ["e1"]
        assert e["promotion"] is True
        assert e["rollback"] is False
        assert e["changed_files"] == 3
        assert e["changed_lines"] == 120
        assert e["result"] == "completed"
        assert e["snapshot_id"] == "snap-1"

    def test_set_git_commit_manual(self, ledger: ExecutionLedger) -> None:
        ledger.set_git_commit(before="abc123", after="def456")
        assert ledger._entry["git_commit_before"] == "abc123"
        assert ledger._entry["git_commit_after"] == "def456"

    def test_set_git_commit_auto(self, ledger: ExecutionLedger, monkeypatch) -> None:
        monkeypatch.setattr(
            "scripts.pro.tuneladora.ledger.subprocess.run",
            lambda *a, **k: type("R", (), {"stdout": "abc123\n"})(),
        )
        ledger.set_git_commit()
        assert ledger._entry["git_commit_before"] == "abc123"

    def test_set_git_commit_error_silencioso(self, ledger: ExecutionLedger, monkeypatch) -> None:
        monkeypatch.setattr(
            "scripts.pro.tuneladora.ledger.subprocess.run",
            lambda *a, **k: (_ for _ in ()).throw(OSError("no git")),
        )
        ledger.set_git_commit()  # no debe lanzar

    def test_goal_decision_alternativa(self, ledger: ExecutionLedger) -> None:
        ledger.set_goal({"objetivo": "x"})
        ledger.add_decision("elegir_plugin", {"plugin": "ruff"})
        ledger.add_alternative("ruff", "el mas rapido")
        assert ledger._entry["goal"] == {"objetivo": "x"}
        assert ledger._entry["decisions"][0]["type"] == "elegir_plugin"
        assert ledger._entry["alternatives"][0]["strategy"] == "ruff"

    def test_plan_evaluacion(self, ledger: ExecutionLedger) -> None:
        ledger.set_plan({"fases": ["a"]})
        ledger.set_evaluation(0.9, "promote", {"cobertura": 90})
        assert ledger._entry["plan"] == {"fases": ["a"]}
        assert ledger._entry["evaluation"]["score"] == 0.9

    def test_patterns_conocimiento(self, ledger: ExecutionLedger) -> None:
        ledger.add_pattern({"tipo": "hotspot"})
        ledger.add_knowledge({"clave": "valor"})
        ledger.add_recommendation({"accion": "x"})
        ledger.add_policy({"regla": "r"})
        ledger.add_verification({"check": "c"})
        assert len(ledger._entry["pattern_detections"]) == 1
        assert len(ledger._entry["knowledge"]) == 1
        assert len(ledger._entry["recommendations"]) == 1
        assert len(ledger._entry["policies"]) == 1
        assert len(ledger._entry["verifications"]) == 1

    def test_save_escribe_json(self, ledger: ExecutionLedger, tmp_path: Path) -> None:
        ledger.set_result("completed")
        path = ledger.save()
        assert path.exists()
        data = json.loads(path.read_text())
        assert data["result"] == "completed"
        assert data["duration_ms"] >= 0
        assert data["end_time"]

    def test_resource_sample(self, ledger: ExecutionLedger, monkeypatch) -> None:
        fake_free = type("R", (), {"returncode": 0, "stdout": "Mem: 100 512 300 20\n"})()

        def fake_run(cmd, **kwargs):
            if cmd[0] == "free":
                return fake_free
            return type("R", (), {"returncode": 0, "stdout": "5\n"})()

        monkeypatch.setattr("scripts.pro.tuneladora.ledger.subprocess.run", fake_run)
        ledger.resource_sample()
        assert ledger._entry["resources"]["ram_used_mb"] == 512
        assert ledger._entry["resources"]["python_processes"] == 5


class TestSqlite:
    def _entry(self) -> dict:
        return {
            "execution_id": "e1",
            "pipeline": "mejora",
            "result": "completed",
            "duration_ms": 100,
            "errors": ["err1", "err2"],
        }

    def test_save_y_get_history(self, tmp_path: Path) -> None:
        save_execution(self._entry(), tmp_path)
        rows = get_history(tmp_path)
        assert len(rows) == 1
        assert rows[0]["pipeline"] == "mejora"
        assert rows[0]["status"] == "completed"

    def test_get_history_filtro_pipeline(self, tmp_path: Path) -> None:
        save_execution(self._entry(), tmp_path)
        e2 = dict(self._entry(), execution_id="e2", pipeline="otra")
        save_execution(e2, tmp_path)
        rows = get_history(tmp_path, pipeline="mejora")
        assert len(rows) == 1
        assert rows[0]["execution_id"] == "e1"

    def test_cleanup_history(self, tmp_path: Path) -> None:
        save_execution(self._entry(), tmp_path)
        deleted = cleanup_history(tmp_path, days=90)
        assert deleted == 0  # recien creado, no vence
        conn = sqlite3.connect(tmp_path / "tuneladora.db")
        conn.execute("UPDATE executions SET created_at = datetime('now', '-200 days')")
        conn.commit()
        conn.close()
        deleted = cleanup_history(tmp_path, days=90)
        assert deleted == 1

    def test_save_error_silencioso(self, tmp_path: Path) -> None:
        save_execution({"execution_id": "x"}, tmp_path / "no" / "existe")  # no lanza
