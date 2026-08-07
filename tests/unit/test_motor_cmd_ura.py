"""Tests para motor/cli/cmd_ura.py — comandos migrados de ura.py."""

import json
import pytest

pytestmark = pytest.mark.slow

import subprocess
import urllib.error
from pathlib import Path
from unittest import mock


from motor.cli import cmd_ura
from motor.core.executor import ProcessResult


def _res(ok: bool = True, returncode: int = 0, stdout: str = "", stderr: str = "") -> ProcessResult:
    return ProcessResult(ok=ok, cmd=[], returncode=returncode, stdout=stdout, stderr=stderr)


class FakeExecutor:
    def __init__(self, script: list[ProcessResult] | None = None) -> None:
        self.results: list[ProcessResult] = list(script or [])
        self.calls: list[list[str]] = []

    def run(self, cmd, timeout: int = 30, cwd: str | None = None, env=None) -> ProcessResult:
        self.calls.append(list(cmd))
        if self.results:
            return self.results.pop(0)
        return _res()


@pytest.fixture(autouse=True)
def fake_exec(monkeypatch: pytest.MonkeyPatch) -> FakeExecutor:
    fe = FakeExecutor()
    monkeypatch.setattr(cmd_ura, "_executor", fe)
    return fe


def test_memory_path_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("URA_MEMORY_DB", raising=False)
    assert cmd_ura._memory_path() == Path.home() / ".ura" / "memory.db"


def test_memory_path_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("URA_MEMORY_DB", "/tmp/mem.db")
    assert cmd_ura._memory_path() == Path("/tmp/mem.db")


def test_run_ok() -> None:
    ok, out = cmd_ura._run(["x"], "desc")
    assert ok is True
    assert out == ""


def test_run_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cmd_ura, "_executor", FakeExecutor([_res(ok=False, stderr="boom")]))
    ok, err = cmd_ura._run(["x"], "desc")
    assert ok is False
    assert err == "boom"


class TestFinalize:
    def test_ok_con_mensaje(self, fake_exec: FakeExecutor) -> None:
        fake_exec.results = [_res(stdout="git diff"),
                             _res(stdout="staged_file.py"),
                             _res(stdout="pushed")]
        with mock.patch("motor.core.config_manager.validate_schema", return_value=[]):
            assert cmd_ura.cmd_finalize(None, ["-m", "msg"]) == 0
        msgs = [c[0] for c in fake_exec.calls]
        assert msgs[0] == "python3"

    def test_test_fail(self, fake_exec: FakeExecutor) -> None:
        fake_exec.results = [_res(ok=False, stderr="boom")]
        assert cmd_ura.cmd_finalize(None, []) == 1

    def test_compile_fail(self, fake_exec: FakeExecutor) -> None:
        fake_exec.results = [_res(), _res(ok=False, stderr="x")]
        assert cmd_ura.cmd_finalize(None, []) == 1

    def test_schema_errors(self, fake_exec: FakeExecutor) -> None:
        fake_exec.results = [_res(), _res(), _res(), _res()]
        with mock.patch("motor.core.config_manager.validate_schema", return_value=["err"]):
            assert cmd_ura.cmd_finalize(None, []) == 1

    def test_router_degradado(self, fake_exec: FakeExecutor) -> None:
        fake_exec.results = [_res(), _res(), _res(), _res(),
                             _res(stdout=""), _res(stdout="pushed")]
        with mock.patch("motor.core.config_manager.validate_schema", return_value=[]):
            assert cmd_ura.cmd_finalize(None, []) == 0

    def test_sin_staged_sin_mensaje(self, fake_exec: FakeExecutor) -> None:
        fake_exec.results = [_res(), _res(), _res(), _res(),
                             _res(stdout="a.py\nb.py\nc.py\nd.py"),
                             _res(stdout="ok"),
                             _res(stdout="pushed")]
        with mock.patch("motor.core.config_manager.validate_schema", return_value=[]):
            assert cmd_ura.cmd_finalize(None, []) == 0
        commit = [c for c in fake_exec.calls if c[:2] == ["git", "commit"]]
        assert len(commit) == 1
        assert commit[0][-1] == "Pipeline: a.py b.py c.py"

    def test_commit_fail(self, fake_exec: FakeExecutor) -> None:
        fake_exec.results = [_res(), _res(), _res(), _res(),
                             _res(stdout="a.py"), _res(),
                             _res(ok=False, stderr="x")]
        with mock.patch("motor.core.config_manager.validate_schema", return_value=[]):
            assert cmd_ura.cmd_finalize(None, []) == 1


class TestTest:
    def test_ok(self) -> None:
        with mock.patch("motor.core.config_manager.validate_schema", return_value=[]), \
                mock.patch("motor.core.config_manager.validate_config", return_value=[]):
            assert cmd_ura.cmd_test(None, []) == 0

    def test_errores(self) -> None:
        with mock.patch("motor.core.config_manager.validate_schema", return_value=["e"]), \
                mock.patch("motor.core.config_manager.validate_config", return_value=["w"]):
            assert cmd_ura.cmd_test(None, []) == 0


class TestSnapshot:
    def test_escribe_json(self, fake_exec: FakeExecutor, tmp_path: Path,
                          monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(cmd_ura, "ROOT", tmp_path)
        fake_exec.results = [_res(stdout="abc123"), _res(stdout="TODOS LOS TESTS PASARON"),
                             _res(stdout="main")]
        assert cmd_ura.cmd_snapshot(None, []) == 0
        snap_dir = tmp_path / "data" / "snapshots"
        snaps = list(snap_dir.glob("*.json"))
        assert snaps
        data = json.loads(snaps[-1].read_text())
        assert data["commit"] == "abc123"
        assert data["tests"] == "PASS"
        assert data["branch"] == "main"


class TestMaintenance:
    def test_dry_run(self, fake_exec: FakeExecutor) -> None:
        fake_exec.results = [_res(returncode=0)]
        assert cmd_ura.cmd_maintenance(None, ["--dry-run"]) == 0
        assert fake_exec.calls[0][0] == "python3"

    def test_ssh(self, fake_exec: FakeExecutor) -> None:
        fake_exec.results = [_res(returncode=0)]
        assert cmd_ura.cmd_maintenance(None, []) == 0
        assert fake_exec.calls[0][0] == "ssh"

    def test_d_short(self, fake_exec: FakeExecutor) -> None:
        fake_exec.results = [_res(returncode=0)]
        assert cmd_ura.cmd_maintenance(None, ["-d"]) == 0


def test_rotate(fake_exec: FakeExecutor) -> None:
    assert cmd_ura.cmd_rotate(None, []) == 0


def test_health(fake_exec: FakeExecutor) -> None:
    assert cmd_ura.cmd_health(None, []) == 0


def test_system(fake_exec: FakeExecutor, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("URA_MEMORY_DB", str(tmp_path / "m.db"))
    assert cmd_ura.cmd_system(None, []) == 0


def test_alerts(fake_exec: FakeExecutor) -> None:
    assert cmd_ura.cmd_alerts(None, []) == 0


class TestSnc:
    def test_sin_estado(self, fake_exec: FakeExecutor, tmp_path: Path,
                        monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(cmd_ura.Path, "home",
                            mock.Mock(return_value=tmp_path))
        assert cmd_ura.cmd_snc(None, []) == 0

    def test_con_estado(self, fake_exec: FakeExecutor, tmp_path: Path,
                        monkeypatch: pytest.MonkeyPatch) -> None:
        home = tmp_path / "home"
        (home / "URA" / "logs").mkdir(parents=True)
        (home / "URA" / "logs" / "snc_state.json").write_text(json.dumps({
            "timestamp": "2026-01-01T00:00:00+00:00",
            "status": "ok",
            "services": {"svc": {"ok": True}, "bad": {"ok": False, "repair_result": "reparado"}},
            "repair_attempts": {"a": 2},
        }))
        monkeypatch.setattr(cmd_ura.Path, "home", mock.Mock(return_value=home))
        assert cmd_ura.cmd_snc(None, []) == 0

    def test_estado_corrupto(self, fake_exec: FakeExecutor, tmp_path: Path,
                             monkeypatch: pytest.MonkeyPatch) -> None:
        home = tmp_path / "home"
        (home / "URA" / "logs").mkdir(parents=True)
        (home / "URA" / "logs" / "snc_state.json").write_text("no json")
        monkeypatch.setattr(cmd_ura.Path, "home", mock.Mock(return_value=home))
        assert cmd_ura.cmd_snc(None, []) == 0


class TestDoctor:
    def test_ok(self, fake_exec: FakeExecutor, tmp_path: Path,
                monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(cmd_ura.Path, "home", mock.Mock(return_value=tmp_path))
        with mock.patch("motor.core.config_manager.validate_schema", return_value=[]):
            assert cmd_ura.cmd_doctor(None, []) == 0

    def test_con_estado(self, fake_exec: FakeExecutor, tmp_path: Path,
                        monkeypatch: pytest.MonkeyPatch) -> None:
        home = tmp_path / "home"
        (home / "URA" / "logs").mkdir(parents=True)
        (home / "URA" / "logs" / "snc_state.json").write_text(json.dumps({"openclaw_active": True}))
        monkeypatch.setattr(cmd_ura.Path, "home", mock.Mock(return_value=home))
        fake_exec.results = [_res(stdout="TODOS LOS TESTS PASARON"),
                             _res(stdout="c1\nc2"),
                             _res(stdout="docker ps", returncode=0)]
        with mock.patch("motor.core.config_manager.validate_schema", return_value=["e"]):
            assert cmd_ura.cmd_doctor(None, []) == 0


def test_metrics(monkeypatch: pytest.MonkeyPatch) -> None:
    urlopen = mock.Mock(return_value=mock.Mock(
        __enter__=mock.Mock(return_value=mock.Mock(read=mock.Mock(return_value=b"model_selection 1"))),
        __exit__=mock.Mock(return_value=False)))
    monkeypatch.setattr(cmd_ura.urllib.request, "urlopen", urlopen)
    assert cmd_ura.cmd_metrics(None, []) == 0


def test_metrics_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_a, **_k):
        raise urllib.error.URLError("down")
    monkeypatch.setattr(cmd_ura.urllib.request, "urlopen", boom)
    assert cmd_ura.cmd_metrics(None, []) == 0


class TestDashboard:
    def test_sin_estado(self, fake_exec: FakeExecutor, tmp_path: Path,
                        monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(cmd_ura.Path, "home", mock.Mock(return_value=tmp_path))
        fake_exec.results = [_res(returncode=0, stdout="l1")]
        assert cmd_ura.cmd_dashboard(None, []) == 0

    def test_con_estado(self, fake_exec: FakeExecutor, tmp_path: Path,
                        monkeypatch: pytest.MonkeyPatch) -> None:
        home = tmp_path / "home"
        (home / "URA" / "logs").mkdir(parents=True)
        (home / "URA" / "logs" / "snc_state.json").write_text(json.dumps({
            "timestamp": "2026-01-01T00:00:00+00:00",
            "status": "ok",
            "services": {"s": {"ok": True}},
            "repair_attempts": {"a": 1},
        }))
        monkeypatch.setattr(cmd_ura.Path, "home", mock.Mock(return_value=home))
        fake_exec.results = [_res(returncode=0, stdout="l1")]
        assert cmd_ura.cmd_dashboard(None, []) == 0

    def test_estado_corrupto(self, fake_exec: FakeExecutor, tmp_path: Path,
                             monkeypatch: pytest.MonkeyPatch) -> None:
        home = tmp_path / "home"
        (home / "URA" / "logs").mkdir(parents=True)
        (home / "URA" / "logs" / "snc_state.json").write_text("xx")
        monkeypatch.setattr(cmd_ura.Path, "home", mock.Mock(return_value=home))
        assert cmd_ura.cmd_dashboard(None, []) == 0


class TestIndex:
    def test_ok(self, fake_exec: FakeExecutor) -> None:
        fake_exec.results = [_res(returncode=0, stdout='{"ok": true}')]
        assert cmd_ura.cmd_index(None, []) == 0

    def test_force(self, fake_exec: FakeExecutor) -> None:
        fake_exec.results = [_res(returncode=0, stdout="{}")]
        assert cmd_ura.cmd_index(None, ["--force"]) == 0
        assert "force=True" in fake_exec.calls[0][2]

    def test_ssh_fail(self, fake_exec: FakeExecutor) -> None:
        fake_exec.results = [_res(returncode=1, stderr="e")]
        assert cmd_ura.cmd_index(None, []) == 1

    def test_json_invalido(self, fake_exec: FakeExecutor) -> None:
        fake_exec.results = [_res(returncode=0, stdout="no json")]
        assert cmd_ura.cmd_index(None, []) == 1

    def test_error_en_stats(self, fake_exec: FakeExecutor) -> None:
        fake_exec.results = [_res(returncode=0, stdout='{"error": "x"}')]
        assert cmd_ura.cmd_index(None, []) == 1


class TestAsk:
    def test_sin_pregunta(self) -> None:
        assert cmd_ura.cmd_ask(None, []) == 1

    def test_ok(self, fake_exec: FakeExecutor) -> None:
        fake_exec.results = [_res(stdout="respuesta")]
        assert cmd_ura.cmd_ask(None, ["que", "es"]) == 0
        assert fake_exec.calls[0][0] == "ssh"
        assert "que es" in fake_exec.calls[0][2]

    def test_fallback_error(self, fake_exec: FakeExecutor) -> None:
        fake_exec.results = [_res(ok=False, returncode=0, stderr="x")]
        assert cmd_ura.cmd_ask(None, ["q"]) == 1

    def test_sin_stdout(self, fake_exec: FakeExecutor) -> None:
        fake_exec.results = [_res(ok=False, returncode=2)]
        assert cmd_ura.cmd_ask(None, ["q"]) == 2


class TestMemory:
    def test_solo_health(self, fake_exec: FakeExecutor, tmp_path: Path,
                         monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("URA_MEMORY_DB", str(tmp_path / "m.db"))
        assert cmd_ura.cmd_memory(None, None) == 0

    def test_search(self, fake_exec: FakeExecutor, tmp_path: Path,
                    monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("URA_MEMORY_DB", str(tmp_path / "m.db"))
        args = mock.Mock(raw=["search", "hola"])
        assert cmd_ura.cmd_memory(None, args) == 0

    def test_store(self, fake_exec: FakeExecutor, tmp_path: Path,
                   monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("URA_MEMORY_DB", str(tmp_path / "m.db"))
        args = mock.Mock(raw=["store", "texto"])
        assert cmd_ura.cmd_memory(None, args) == 0

    def test_web(self, fake_exec: FakeExecutor, tmp_path: Path,
                 monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("URA_MEMORY_DB", str(tmp_path / "m.db"))
        args = mock.Mock(raw=["web", "query"])
        with mock.patch("core.mochila.tools.web_search",
                        mock.AsyncMock(return_value={"results": [{"title": "t", "snippet": "s"}]})):
            assert cmd_ura.cmd_memory(None, args) == 0

    def test_web_fallback(self, fake_exec: FakeExecutor, tmp_path: Path,
                          monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("URA_MEMORY_DB", str(tmp_path / "m.db"))
        args = mock.Mock(raw=["web", "q"])
        with mock.patch("core.mochila.tools.web_search", mock.AsyncMock(side_effect=RuntimeError("x"))):
            assert cmd_ura.cmd_memory(None, args) == 0

    def test_backup(self, fake_exec: FakeExecutor, tmp_path: Path,
                    monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("URA_MEMORY_DB", str(tmp_path / "m.db"))
        monkeypatch.setenv("URA_BACKUP_DIR", str(tmp_path / "bk"))
        args = mock.Mock(raw=["backup"])
        assert cmd_ura.cmd_memory(None, args) == 0
        assert (tmp_path / "bk").exists()

    def test_restore_no_existe(self, fake_exec: FakeExecutor, tmp_path: Path,
                               monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("URA_MEMORY_DB", str(tmp_path / "m.db"))
        args = mock.Mock(raw=["restore", str(tmp_path / "no.db")])
        assert cmd_ura.cmd_memory(None, args) == 1

    def test_restore_ok(self, fake_exec: FakeExecutor, tmp_path: Path,
                        monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("URA_MEMORY_DB", str(tmp_path / "m.db"))
        monkeypatch.setenv("URA_BACKUP_DIR", str(tmp_path / "bk"))
        src = tmp_path / "src.db"
        src.write_text("data")
        args = mock.Mock(raw=["restore", str(src)])
        assert cmd_ura.cmd_memory(None, args) == 0

    def test_help(self, fake_exec: FakeExecutor, tmp_path: Path,
                  monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("URA_MEMORY_DB", str(tmp_path / "m.db"))
        args = mock.Mock(raw=["otro"])
        assert cmd_ura.cmd_memory(None, args) == 0


class TestSystemctl:
    def test_user_ok(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake_sp = mock.Mock(return_value=subprocess.CompletedProcess([], 0, stdout="x"))
        monkeypatch.setattr(subprocess, "run", fake_sp)
        assert cmd_ura._systemctl(["status", "x"]).returncode == 0

    def test_fallback_system(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def side_effect(cmd, **kwargs):
            if "--user" in cmd:
                return subprocess.CompletedProcess(cmd, 1, stderr="Could not connect")
            return subprocess.CompletedProcess(cmd, 0, stdout="y")
        monkeypatch.setattr(subprocess, "run", side_effect)
        assert cmd_ura._systemctl(["status"]).returncode == 0


class TestService:
    def test_no_disponible(self, monkeypatch: pytest.MonkeyPatch) -> None:
        r = subprocess.CompletedProcess([], 1, stdout="", stderr="")
        monkeypatch.setattr(cmd_ura, "_systemctl", mock.Mock(return_value=r))
        assert cmd_ura.cmd_service(None, None) == 1

    def test_list(self, monkeypatch: pytest.MonkeyPatch) -> None:
        r = subprocess.CompletedProcess([], 0, stdout="ura-x.service loaded active running")
        monkeypatch.setattr(cmd_ura, "_systemctl", mock.Mock(return_value=r))
        args = mock.Mock(raw=["list"])
        assert cmd_ura.cmd_service(None, args) == 0

    def test_accion(self, monkeypatch: pytest.MonkeyPatch) -> None:
        r = subprocess.CompletedProcess([], 0, stdout="ok")
        monkeypatch.setattr(cmd_ura, "_systemctl", mock.Mock(return_value=r))
        args = mock.Mock(raw=["start", "ura-x"])
        assert cmd_ura.cmd_service(None, args) == 0

    def test_accion_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        r = subprocess.CompletedProcess([], 1, stderr="failed")
        monkeypatch.setattr(cmd_ura, "_systemctl", mock.Mock(return_value=r))
        args = mock.Mock(raw=["stop", "ura-x"])
        assert cmd_ura.cmd_service(None, args) == 0

    def test_accion_sin_servicio(self, monkeypatch: pytest.MonkeyPatch) -> None:
        r = subprocess.CompletedProcess([], 0, stdout="x", stderr="")
        monkeypatch.setattr(cmd_ura, "_systemctl", mock.Mock(return_value=r))
        args = mock.Mock(raw=["start"])
        assert cmd_ura.cmd_service(None, args) == 0

    def test_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        r = subprocess.CompletedProcess([], 0, stdout="ura-a.service loaded active running")
        monkeypatch.setattr(cmd_ura, "_systemctl", mock.Mock(return_value=r))
        assert cmd_ura.cmd_service(None, None) == 0


class TestAudit:
    def test_ok_sin_fallos(self, monkeypatch: pytest.MonkeyPatch) -> None:
        data = {"version": "1", "files_scanned": 5,
                "blocks": {"A": []}, "block_headers": {}}
        fake_sp = mock.Mock(return_value=subprocess.CompletedProcess([], 0, stdout=json.dumps(data)))
        monkeypatch.setattr(subprocess, "run", fake_sp)
        assert cmd_ura.cmd_audit(None, []) == 0

    def test_con_fallos(self, monkeypatch: pytest.MonkeyPatch) -> None:
        data = {"version": "1", "files_scanned": 5,
                "blocks": {"A": [{"level": "FAIL", "type": "t", "file": "f", "line": 1}]}}
        fake_sp = mock.Mock(return_value=subprocess.CompletedProcess([], 0, stdout=json.dumps(data)))
        monkeypatch.setattr(subprocess, "run", fake_sp)
        assert cmd_ura.cmd_audit(None, []) == 1

    def test_fallo_script(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake_sp = mock.Mock(return_value=subprocess.CompletedProcess([], 1, stdout="", stderr="boom"))
        monkeypatch.setattr(subprocess, "run", fake_sp)
        assert cmd_ura.cmd_audit(None, []) == 1
