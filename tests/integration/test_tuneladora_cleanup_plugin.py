"""Tests para scripts/pro/tuneladora/plugins/cleanup.py (CleanupPlugin)."""

from __future__ import annotations

import shutil
import sqlite3
import time
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

from scripts.pro.tuneladora.plugins.cleanup import CleanupPlugin


@pytest.fixture
def engine() -> mock.Mock:
    e = mock.Mock()
    e.log = mock.Mock()
    return e


@pytest.fixture
def plugin(engine: mock.Mock) -> CleanupPlugin:
    return CleanupPlugin(engine)


class TestCleanupLogs:
    def test_dir_no_existe(self, plugin: CleanupPlugin, monkeypatch) -> None:
        monkeypatch.setattr(Path, "home", lambda: Path("/no/existe"))
        assert plugin.cleanup_logs() == {"removed": 0, "reason": "log_dir_not_found"}

    def test_elimina_viejos(self, plugin: CleanupPlugin, tmp_path: Path, monkeypatch) -> None:
        logs = tmp_path / "URA" / "ura_ia_1972" / "motor" / "observability" / "logs"
        logs.mkdir(parents=True)
        viejo = logs / "viejo.log"
        nuevo = logs / "nuevo.log"
        viejo.write_text("x")
        nuevo.write_text("x")
        viejo_ts = time.time() - 40 * 86400
        nuevo_ts = time.time() - 1000
        import os

        os.utime(viejo, (viejo_ts, viejo_ts))
        os.utime(nuevo, (nuevo_ts, nuevo_ts))
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        result = plugin.cleanup_logs(days=30)
        assert result["removed"] == 1
        assert not viejo.exists()
        assert nuevo.exists()

    def test_error_eliminando_silencioso(self, plugin: CleanupPlugin, tmp_path: Path, monkeypatch) -> None:
        logs = tmp_path / "URA" / "ura_ia_1972" / "motor" / "observability" / "logs"
        logs.mkdir(parents=True)
        f = logs / "viejo.log"
        f.write_text("x")
        import os

        os.utime(f, (time.time() - 40 * 86400, time.time() - 40 * 86400))
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        monkeypatch.setattr(Path, "unlink", mock.Mock(side_effect=OSError("perm")))
        result = plugin.cleanup_logs(days=30)
        assert result["removed"] == 0
        plugin.engine.log.warning.assert_called()


class TestCleanupEmbeddings:
    def test_dir_no_existe(self, plugin: CleanupPlugin, monkeypatch) -> None:
        monkeypatch.setattr(Path, "home", lambda: Path("/no/existe"))
        assert plugin.cleanup_embeddings() == {"removed": 0, "reason": "embeddings_dir_not_found"}

    def test_elimina_huerfanos(self, plugin: CleanupPlugin, tmp_path: Path, monkeypatch) -> None:
        emb = tmp_path / "URA" / "ura_ia_1972" / "knowledge" / "embeddings"
        docs = tmp_path / "URA" / "ura_ia_1972" / "knowledge" / "documents"
        emb.mkdir(parents=True)
        docs.mkdir(parents=True)
        (emb / "huerfano.json").write_text("x")
        (emb / "con_doc.json").write_text("x")
        (docs / "con_doc.json").write_text("x")
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        result = plugin.cleanup_embeddings()
        assert result["removed"] == 1
        assert not (emb / "huerfano.json").exists()
        assert (emb / "con_doc.json").exists()


class TestVacuumSqlite:
    def test_base_no_existe(self, plugin: CleanupPlugin, monkeypatch) -> None:
        monkeypatch.setattr(Path, "exists", mock.Mock(return_value=False))
        with mock.patch("sqlite3.connect") as m_conn:
            result = plugin.vacuum_sqlite()
        assert result["results"][0]["status"] == "skipped"
        m_conn.assert_not_called()

    def test_vacuum_ok(self, plugin: CleanupPlugin, tmp_path: Path, monkeypatch) -> None:
        db = tmp_path / "knowledge.db"
        db.write_text("sqlite")
        conn = mock.Mock()
        monkeypatch.setattr("sqlite3.connect", mock.Mock(return_value=conn))
        with mock.patch("pathlib.Path.exists", return_value=True):
            result = plugin.vacuum_sqlite()
        assert result["results"][0]["status"] == "ok"
        conn.execute.assert_called_with("VACUUM")

    def test_vacuum_error(self, plugin: CleanupPlugin, monkeypatch) -> None:
        monkeypatch.setattr("sqlite3.connect", mock.Mock(side_effect=sqlite3.OperationalError("locked")))
        monkeypatch.setattr(Path, "exists", mock.Mock(return_value=True))
        result = plugin.vacuum_sqlite()
        assert result["results"][0]["status"] == "error"


class TestCheckDisk:
    def test_ok(self, plugin: CleanupPlugin, monkeypatch) -> None:
        monkeypatch.setattr(
            shutil,
            "disk_usage",
            lambda p: SimpleNamespace(total=1000, used=500, free=500),
        )
        result = plugin.check_disk(threshold=90.0)
        assert result["status"] == "ok"
        assert result["percent"] == 50.0

    def test_warning(self, plugin: CleanupPlugin, monkeypatch) -> None:
        monkeypatch.setattr(
            shutil,
            "disk_usage",
            lambda p: SimpleNamespace(total=1000, used=950, free=50),
        )
        result = plugin.check_disk(threshold=90.0)
        assert result["status"] == "warning"
        plugin.engine.log.warning.assert_called()

    def test_error(self, plugin: CleanupPlugin, monkeypatch) -> None:
        monkeypatch.setattr(shutil, "disk_usage", mock.Mock(side_effect=OSError("x")))
        result = plugin.check_disk()
        assert result["status"] == "error"
        assert result["percent"] == -1


class TestDetectDuplicates:
    def test_ok(self, plugin: CleanupPlugin, tmp_path: Path, monkeypatch) -> None:
        f = tmp_path / "a.py"
        f.write_text("def foo():\n    x = 1\n    y = 2\n    z = 3\n    return x\n")
        monkeypatch.setattr("pathlib.Path.rglob", lambda self, pat: [f])
        result = plugin.detect_duplicates()
        assert "groups" in result
        assert "total_funcs" in result

    def test_syntax_error_ignorado(self, plugin: CleanupPlugin, tmp_path: Path, monkeypatch) -> None:
        f = tmp_path / "b.py"
        f.write_text("def roto(:\n")
        monkeypatch.setattr("pathlib.Path.rglob", lambda self, pat: [f])
        result = plugin.detect_duplicates()  # no debe lanzar
        assert "groups" in result


class TestTechDebt:
    def test_cuenta_todos(self, plugin: CleanupPlugin, tmp_path: Path, monkeypatch) -> None:
        f = tmp_path / "m.py"
        f.write_text("# TODO: x\n# FIXME: y\n# TODO: z\n")
        monkeypatch.setattr("pathlib.Path.rglob", lambda self, pat: [f])
        result = plugin.tech_debt_report()
        assert result == {"todos": 2, "fixmes": 1}


class TestForense:
    def test_sin_dir(self, plugin: CleanupPlugin) -> None:
        assert plugin.forense_aislamientos() == {"total": 0, "limpiados": 0, "activos": 0}

    def test_limpia_proceso_muerto(self, plugin: CleanupPlugin, monkeypatch) -> None:
        pid_dir = mock.Mock()
        pid_dir.name = "99999"
        pid_dir.is_dir.return_value = True
        pid_dir.stat.return_value = mock.Mock(st_mtime=time.time() - 999999)
        nombre = mock.Mock()
        nombre.exists.return_value = False
        pid_dir.__truediv__ = mock.Mock(return_value=nombre)
        real_exists = Path.exists
        real_iterdir = Path.iterdir

        def fake_exists(self) -> bool:
            if str(self) == "/tmp/ura_aislados":
                return True
            if str(self).startswith("/proc/"):
                return False
            return real_exists(self)

        def fake_iterdir(self):
            if str(self) == "/tmp/ura_aislados":
                return iter([pid_dir])
            return real_iterdir(self)

        monkeypatch.setattr(Path, "exists", fake_exists)
        monkeypatch.setattr(Path, "iterdir", fake_iterdir)
        with mock.patch("shutil.rmtree") as m_rm:
            result = plugin.forense_aislamientos()
        assert result["limpiados"] == 1
        m_rm.assert_called_once()


class TestScripts:
    def test_watermark(self, plugin: CleanupPlugin) -> None:
        plugin.engine.run_script.return_value = SimpleNamespace(returncode=0)
        assert plugin.watermark() == {"ok": True}
        plugin.engine.run_script.assert_called_once()

    def test_pareto(self, plugin: CleanupPlugin) -> None:
        plugin.engine.run_script.return_value = SimpleNamespace(returncode=1)
        assert plugin.pareto() == {"ok": False}

    def test_auto_mejora(self, plugin: CleanupPlugin) -> None:
        plugin.engine.run_script.return_value = SimpleNamespace(returncode=0)
        assert plugin.auto_mejora() == {"ok": True}

    def test_conciencia(self, plugin: CleanupPlugin) -> None:
        plugin.engine.run_script.return_value = SimpleNamespace(returncode=0)
        assert plugin.conciencia() == {"ok": True}


class TestGit:
    def test_commit_ok(self, plugin: CleanupPlugin) -> None:
        plugin.engine.run_git.return_value = SimpleNamespace(returncode=0)
        result = plugin.git_commit("msg")
        assert result["ok"] is True
        assert plugin.engine.run_git.call_args_list[1].args[0] == ["commit", "-m", "msg"]

    def test_commit_default_message(self, plugin: CleanupPlugin) -> None:
        plugin.engine.run_git.return_value = SimpleNamespace(returncode=0)
        plugin.git_commit()
        args = plugin.engine.run_git.call_args_list[1].args[0]
        assert args[0] == "commit"
        assert "mantenimiento:" in args[2]

    def test_rollback(self, plugin: CleanupPlugin) -> None:
        plugin.git_rollback()
        plugin.engine.run_git.assert_called_with(["checkout", "."])


class TestAuditoria:
    def test_quick_con_json(self, plugin: CleanupPlugin) -> None:
        plugin.engine.run_script.return_value = SimpleNamespace(
            returncode=0, stdout='{"score": 80, "bloqueante": false}'
        )
        result = plugin.auditoria()
        assert result["score"] == 80
        assert result["bloqueante"] is False

    def test_profundo(self, plugin: CleanupPlugin) -> None:
        plugin.engine.run_script.return_value = SimpleNamespace(returncode=0, stdout="")
        plugin.auditoria(profundo=True)
        assert "--full" in plugin.engine.run_script.call_args[1]["args"]

    def test_json_invalido(self, plugin: CleanupPlugin) -> None:
        plugin.engine.run_script.return_value = SimpleNamespace(returncode=0, stdout="no-json")
        result = plugin.auditoria()
        assert result["score"] == 0

    def test_bloqueante_loguea(self, plugin: CleanupPlugin) -> None:
        plugin.engine.run_script.return_value = SimpleNamespace(
            returncode=0, stdout='{"score": 30, "bloqueante": true}'
        )
        plugin.auditoria()
        plugin.engine.log.warning.assert_called()
