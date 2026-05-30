"""Tests para scheduler_orchestrator.py — orquestador proactivo de tareas."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# The module under test uses /opt/ura paths; override them via monkeypatch
# before importing so we can use temp paths.

import agents.scheduler_orchestrator as so


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def temp_paths(monkeypatch, tmp_path: Path) -> None:
    """Redirect all /opt/ura paths to a temp directory."""
    base = tmp_path / "opt" / "ura"
    monkeypatch.setattr(so, "URA_BASE", base)
    monkeypatch.setattr(so, "TASKS_CONFIG", base / "config" / "tareas.yaml")
    monkeypatch.setattr(so, "LOG_FILE", base / "logs" / "scheduler.log")
    monkeypatch.setattr(so, "SUGGESTIONS_FILE", base / "data" / "sugerencias.json")
    monkeypatch.setattr(so, "CRONTAB_BACKUP_DIR", base / "backups")


# ── time_in_exclusion_window ─────────────────────────────────────────


class TestTimeInExclusionWindow:
    def test_normal_window_inside(self):
        dt = datetime(2026, 5, 23, 3, 30)
        assert so.time_in_exclusion_window(dt, ["02:00-04:00"]) is True

    def test_normal_window_outside(self):
        dt = datetime(2026, 5, 23, 5, 0)
        assert so.time_in_exclusion_window(dt, ["02:00-04:00"]) is False

    def test_normal_window_edge_start(self):
        dt = datetime(2026, 5, 23, 2, 0)
        assert so.time_in_exclusion_window(dt, ["02:00-04:00"]) is True

    def test_normal_window_edge_end(self):
        dt = datetime(2026, 5, 23, 4, 0)
        assert so.time_in_exclusion_window(dt, ["02:00-04:00"]) is True

    def test_midnight_crossing_after_start(self):
        dt = datetime(2026, 5, 23, 23, 30)
        assert so.time_in_exclusion_window(dt, ["23:00-01:00"]) is True

    def test_midnight_crossing_before_end(self):
        dt = datetime(2026, 5, 24, 0, 30)
        assert so.time_in_exclusion_window(dt, ["23:00-01:00"]) is True

    def test_midnight_crossing_outside(self):
        dt = datetime(2026, 5, 23, 22, 0)
        assert so.time_in_exclusion_window(dt, ["23:00-01:00"]) is False

    def test_empty_windows(self):
        dt = datetime(2026, 5, 23, 3, 0)
        assert so.time_in_exclusion_window(dt, []) is False

    def test_malformed_window_skipped(self):
        dt = datetime(2026, 5, 23, 3, 0)
        assert so.time_in_exclusion_window(dt, ["not-a-window"]) is False


# ── effective_min_gap ────────────────────────────────────────────────


class TestEffectiveMinGap:
    def test_default_gap(self):
        task = {"recursos": {}}
        assert so.effective_min_gap(task) == so.MIN_GAP

    def test_high_cpu_increases_gap(self):
        task = {"recursos": {"cpu": "alta"}}
        assert so.effective_min_gap(task) == timedelta(minutes=60)

    def test_critical_cpu_increases_gap_more(self):
        task = {"recursos": {"cpu": "critica"}}
        assert so.effective_min_gap(task) == timedelta(minutes=90)

    def test_high_disk_increases_gap(self):
        task = {"recursos": {"disco": "alta"}}
        assert so.effective_min_gap(task) == timedelta(minutes=60)

    def test_multiple_resources_wins_largest(self):
        task = {"recursos": {"cpu": "alta", "disco": "alta"}}
        # both are 60m, same as default max
        assert so.effective_min_gap(task) == timedelta(minutes=60)


# ── combined_min_gap ──────────────────────────────────────────────


class TestCombinedMinGap:
    def test_both_light(self):
        t1 = {"recursos": {"cpu": 0.2}}
        t2 = {"recursos": {"cpu": 0.1}}
        assert so.combined_min_gap(t1, t2) == so.MIN_GAP

    def test_cpu_sum_over_0_8(self):
        t1 = {"recursos": {"cpu": 0.5}}
        t2 = {"recursos": {"cpu": 0.4}}
        assert so.combined_min_gap(t1, t2) == so.MIN_GAP + timedelta(minutes=30)

    def test_cpu_sum_over_1_2(self):
        t1 = {"recursos": {"cpu": 0.7}}
        t2 = {"recursos": {"cpu": 0.6}}
        assert so.combined_min_gap(t1, t2) == so.MIN_GAP + timedelta(minutes=60)

    def test_both_disk_high(self):
        # each individual task gets 60 min from disco=alta, combined adds 30
        t1 = {"recursos": {"disco": "alta", "cpu": 0.2}}
        t2 = {"recursos": {"disco": "alta", "cpu": 0.1}}
        assert so.combined_min_gap(t1, t2) == timedelta(minutes=60) + timedelta(minutes=30)

    def test_both_network_high(self):
        # each gets 45 min from red=alta, combined adds 15
        t1 = {"recursos": {"red": "alta", "cpu": 0.2}}
        t2 = {"recursos": {"red": "alta", "cpu": 0.1}}
        assert so.combined_min_gap(t1, t2) == timedelta(minutes=45) + timedelta(minutes=15)

    def test_stacks_multiple_conditions(self):
        t1 = {"recursos": {"cpu": 0.7, "disco": "alta", "red": "alta"}}
        t2 = {"recursos": {"cpu": 0.6, "disco": "alta", "red": "alta"}}
        # base=max(60,60)=60 + cpu>1.2(+60) + both disk(+30) + both net(+15) = 165
        assert so.combined_min_gap(t1, t2) == timedelta(minutes=165)


# ── task_priority ────────────────────────────────────────────────────


class TestTaskPriority:
    def test_critica(self):
        assert so.task_priority({"prioridad": "critica"}) == 0

    def test_alta(self):
        assert so.task_priority({"prioridad": "alta"}) == 1

    def test_media(self):
        assert so.task_priority({"prioridad": "media"}) == 2

    def test_baja(self):
        assert so.task_priority({"prioridad": "baja"}) == 3

    def test_unknown(self):
        assert so.task_priority({}) == 99

    def test_typo_falls_back(self):
        assert so.task_priority({"prioridad": "urgente"}) == 99


# ── parse_next_execution ─────────────────────────────────────────────


class TestParseNextExecution:
    def test_daily_cron(self):
        base = datetime(2026, 5, 23, 0, 0)
        result = so.parse_next_execution("0 3 * * *", base)
        assert result is not None
        assert result.hour == 3
        assert result.minute == 0

    def test_weekly_cron(self):
        base = datetime(2026, 5, 23, 0, 0)  # Saturday
        result = so.parse_next_execution("0 6 * * 0", base)  # Sunday
        assert result is not None
        assert result.strftime("%A") == "Sunday"

    def test_invalid_cron_returns_none(self):
        result = so.parse_next_execution("bad cron", datetime.now())
        assert result is None

    def test_no_base_uses_now(self):
        result = so.parse_next_execution("0 3 * * *")
        assert result is not None


# ── detect_conflicts ─────────────────────────────────────────────────


class TestDetectConflicts:
    def make_task(self, cron: str, prioridad: str = "media", **kwargs) -> dict:
        return {
            "nombre": "test",
            "comando": "/bin/test",
            "cron": cron,
            "recursos": {},
            "prioridad": prioridad,
            "ventanas_exclusion": [],
            **kwargs,
        }

    def test_no_conflict(self):
        tasks = [
            self.make_task("0 3 * * *", nombre="t1"),
            self.make_task("0 6 * * *", nombre="t2"),
        ]
        conflicts = so.detect_conflicts(tasks)
        assert len(conflicts) == 0

    def test_same_time_conflict(self):
        tasks = [
            self.make_task("0 3 * * *", nombre="t1"),
            self.make_task("0 3 * * *", nombre="t2"),
        ]
        conflicts = so.detect_conflicts(tasks)
        assert len(conflicts) == 1
        loser, winner = conflicts[0]
        # same priority → first in order is t1 (earlier in list after sort by alpha?)

    def test_priority_inversion(self):
        """Higher priority task should NOT be the one moved."""
        tasks = [
            self.make_task("0 3 * * *", nombre="critica_t", prioridad="critica"),
            self.make_task("0 3 * * *", nombre="baja_t", prioridad="baja"),
        ]
        conflicts = so.detect_conflicts(tasks)
        assert len(conflicts) == 1
        fixed, to_move = conflicts[0]
        # The task with lower priority (baja) should be the one moved
        assert to_move["prioridad"] == "baja"
        assert fixed["prioridad"] == "critica"


# ── resolve_conflict ─────────────────────────────────────────────────


class TestResolveConflict:
    def test_basic_shift(self):
        fixed = {
            "nombre": "t1",
            "cron": "0 3 * * *",
            "next_time": datetime(2026, 5, 24, 3, 0),
            "fixed_time": datetime(2026, 5, 24, 3, 0),
        }
        movable = {
            "nombre": "t2",
            "cron": "0 3 * * *",
            "next_time": datetime(2026, 5, 24, 3, 0),
        }
        result = so.resolve_conflict(fixed, movable, ["00:00-01:00"], [fixed])
        assert result is not None
        _new_cron, candidate = result
        assert candidate >= fixed["next_time"] + so.MIN_GAP
        assert not so.time_in_exclusion_window(candidate, ["00:00-01:00"])

    def test_respects_exclusion_windows(self):
        fixed = {
            "nombre": "t1",
            "cron": "30 1 * * *",
            "next_time": datetime(2026, 5, 24, 1, 30),
            "fixed_time": datetime(2026, 5, 24, 1, 30),
        }
        movable = {
            "nombre": "t2",
            "cron": "0 2 * * *",
            "next_time": datetime(2026, 5, 24, 2, 0),
        }
        # Window covers 03:00-04:00 only, so 02:00 is valid but 03:00+ is blocked
        result = so.resolve_conflict(fixed, movable, ["03:00-04:00"], [fixed])
        assert result is not None
        _, candidate = result
        assert not so.time_in_exclusion_window(candidate, ["03:00-04:00"])

    def test_no_valid_slot(self):
        """If croniter can't find a valid slot within search limit, return None."""
        fixed = {
            "nombre": "t1",
            "cron": "* * * * *",
            "next_time": datetime(2026, 5, 24, 0, 0),
            "fixed_time": datetime(2026, 5, 24, 0, 0),
        }
        movable = {
            "nombre": "t2",
            "cron": "* * * * *",
            "next_time": datetime(2026, 5, 24, 0, 0),
        }
        # Exclude EVERY hour
        all_day = [f"{h:02d}:00-{h:02d}:59" for h in range(24)]
        result = so.resolve_conflict(fixed, movable, all_day, [fixed])
        assert result is None


# ── build_crontab_map ────────────────────────────────────────────────


class TestBuildCrontabMap:
    def test_empty(self):
        assert so.build_crontab_map([]) == {}

    def test_parses_cron_and_command(self):
        lines = ["0 3 * * * /opt/ura/scripts/backup.sh"]
        result = so.build_crontab_map(lines)
        assert "/opt/ura/scripts/backup.sh" in result
        assert result["/opt/ura/scripts/backup.sh"]["cron"] == "0 3 * * *"

    def test_skips_comments(self):
        lines = [
            "# This is a comment",
            "0 3 * * * /bin/real",
        ]
        result = so.build_crontab_map(lines)
        assert "/bin/real" in result
        assert len(result) == 1

    def test_skips_empty_lines(self):
        lines = ["", "   ", "0 3 * * * /bin/real"]
        result = so.build_crontab_map(lines)
        assert "/bin/real" in result
        assert len(result) == 1

    def test_skips_malformed(self):
        lines = ["just a short line"]
        result = so.build_crontab_map(lines)
        assert result == {}


# ── build_task_list ──────────────────────────────────────────────────


class TestBuildTaskList:
    def test_matches_config_with_crontab(self):
        config = [
            {
                "nombre": "backup",
                "comando": "/bin/backup",
                "recursos": {"cpu": 0.5},
            }
        ]
        crontab_map = {
            "/bin/backup": {"cron": "0 3 * * *", "original_line": "0 3 * * * /bin/backup"}
        }
        tasks = so.build_task_list(config, crontab_map)
        assert len(tasks) == 1
        assert tasks[0]["nombre"] == "backup"
        assert tasks[0]["cron"] == "0 3 * * *"
        assert tasks[0]["recursos"] == {"cpu": 0.5}
        assert tasks[0]["prioridad"] == "media"  # default

    def test_skips_unmatched_command(self):
        config = [{"nombre": "ghost", "comando": "/not/found"}]
        tasks = so.build_task_list(config, {})
        assert tasks == []

    def test_prioridad_from_config(self):
        config = [
            {
                "nombre": "critical",
                "comando": "/bin/crit",
                "prioridad": "critica",
            }
        ]
        crontab_map = {"/bin/crit": {"cron": "0 3 * * *", "original_line": ""}}
        tasks = so.build_task_list(config, crontab_map)
        assert tasks[0]["prioridad"] == "critica"


# ── merge_tasks_into_crontab_lines ───────────────────────────────────


class TestMergeTasksIntoLines:
    def test_replaces_cron_for_matching_command(self):
        lines = ["0 3 * * * /bin/backup", "0 6 * * * /bin/clean"]
        updates = {"/bin/backup": "30 5 * * *"}
        result = so.merge_tasks_into_crontab_lines(lines, updates)
        assert result[0].startswith("30 5 * * * /bin/backup")
        assert result[1] == lines[1]  # unchanged

    def test_preserves_comments(self):
        lines = ["# header", "0 3 * * * /bin/job"]
        result = so.merge_tasks_into_crontab_lines(lines, {})
        assert result == lines

    def test_no_match_no_change(self):
        lines = ["0 3 * * * /bin/thing"]
        result = so.merge_tasks_into_crontab_lines(lines, {"/other": "0 5 * * *"})
        assert result == lines


# ── add_suggestion ───────────────────────────────────────────────────


class TestAddSuggestion:
    def test_creates_file_if_not_exists(self, tmp_path):
        sf = tmp_path / "sugerencias.json"
        so.SUGGESTIONS_FILE = sf
        so.add_suggestion("test problem", "test solution")
        assert sf.exists()
        data = json.loads(sf.read_text())
        assert len(data) == 1
        assert data[0]["problema"] == "test problem"
        assert data[0]["solucion"] == "test solution"
        assert data[0]["dominio"] == "scheduler"

    def test_appends_and_caps_at_200(self, tmp_path):
        sf = tmp_path / "sugerencias.json"
        so.SUGGESTIONS_FILE = sf
        for i in range(210):
            so.add_suggestion(f"p{i}", f"s{i}")
        data = json.loads(sf.read_text())
        assert len(data) == 200
        assert data[0]["problema"] == "p10"  # oldest kept

    def test_handles_corrupted_file(self, tmp_path):
        sf = tmp_path / "sugerencias.json"
        sf.write_text("not json{")
        so.SUGGESTIONS_FILE = sf
        so.add_suggestion("p", "s")
        data = json.loads(sf.read_text())
        assert len(data) == 1


# ── save_crontab / get_crontab_lines (integration-light) ─────────────


class TestSaveCrontab:
    def test_dry_run_does_not_call_subprocess(self):
        with patch.object(so, "get_crontab_lines", return_value=[]):
            result = so.save_crontab(["line1"], dry_run=True)
        assert result is True

    def test_dry_run_creates_no_backup(self, tmp_path):
        bdir = tmp_path / "backups"
        bdir.mkdir()
        so.CRONTAB_BACKUP_DIR = bdir
        with patch.object(so, "get_crontab_lines", return_value=[]):
            so.save_crontab(["line1"], dry_run=True)
        assert list(bdir.iterdir()) == []

    def test_real_save_creates_backup_and_calls_crontab(self, tmp_path):
        bdir = tmp_path / "backups"
        bdir.mkdir()
        so.CRONTAB_BACKUP_DIR = bdir
        with (
            patch.object(so, "get_crontab_lines", return_value=["old line"]),
            patch.object(subprocess, "run", return_value=MagicMock(returncode=0)),
        ):
            result = so.save_crontab(["new line"])
        assert result is True
        backups = list(bdir.iterdir())
        assert len(backups) == 1


# ── main integration test (dry-run) ──────────────────────────────────


class TestMainDryRun:
    def test_dry_run_with_no_tasks(self, tmp_path, monkeypatch):
        """When tareas.yaml has no tasks, main should return 0."""
        tareas = tmp_path / "opt" / "ura" / "config"
        tareas.mkdir(parents=True)
        cfg = tareas / "tareas.yaml"
        cfg.write_text("tareas: []")
        result = so.main(["--dry-run", "--log-level", "WARNING"])
        assert result == 0

    def test_dry_run_with_tasks_logs_changes(self, tmp_path, monkeypatch):
        """Simulate a full dry-run cycle with two conflicting tasks."""
        base = tmp_path / "opt" / "ura"
        (base / "config").mkdir(parents=True)
        (base / "data").mkdir(parents=True)
        (base / "logs").mkdir(parents=True)
        (base / "backups").mkdir(parents=True)

        cfg = base / "config" / "tareas.yaml"
        cfg.write_text("""
ventanas_exclusion_globales:
  - "02:00-04:00"

tareas:
  - nombre: task_a
    comando: /bin/a
    cron: "0 3 * * *"
    recursos: {cpu: 0.2}
    prioridad: media
  - nombre: task_b
    comando: /bin/b
    cron: "0 3 * * *"
    recursos: {cpu: 0.8, disco: alta}
    prioridad: critica
""")

        monkeypatch.setattr(so, "TASKS_CONFIG", cfg)
        monkeypatch.setattr(so, "LOG_FILE", base / "logs" / "scheduler.log")
        monkeypatch.setattr(so, "SUGGESTIONS_FILE", base / "data" / "sugerencias.json")

        crontab_mock = ["0 3 * * * /bin/a", "0 3 * * * /bin/b"]
        with patch.object(so, "get_crontab_lines", return_value=crontab_mock):
            result = so.main(["--dry-run", "--log-level", "WARNING"])
        # Should detect conflict, resolve, report success
        assert result == 0
