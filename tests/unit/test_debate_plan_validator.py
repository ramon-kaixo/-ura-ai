"""Tests para core/debate/plan_validator.py."""
from __future__ import annotations

import json
import subprocess
from types import SimpleNamespace
from unittest import mock

import pytest

import core.debate.plan_validator as pv


class TestGetServiceStatus:
    def test_ok_con_pid(self, monkeypatch) -> None:
        res = SimpleNamespace(stdout="active", stderr="")
        pid = SimpleNamespace(stdout="MainPID=123\n", stderr="")
        monkeypatch.setattr(pv.subprocess, "run", mock.Mock(side_effect=[res, pid]))
        out = pv.get_service_status("ura-mochila.service")
        assert out == {"name": "ura-mochila.service", "active": "active", "pid": 123}

    def test_pid_no_numerico(self, monkeypatch) -> None:
        res = SimpleNamespace(stdout="inactive", stderr="")
        pid = SimpleNamespace(stdout="MainPID=abc\n", stderr="")
        monkeypatch.setattr(pv.subprocess, "run", mock.Mock(side_effect=[res, pid]))
        out = pv.get_service_status("x.service")
        assert out["pid"] is None

    def test_error_timeout(self, monkeypatch) -> None:
        monkeypatch.setattr(pv.subprocess, "run", mock.Mock(side_effect=subprocess.TimeoutExpired("cmd", 5)))
        out = pv.get_service_status("x.service")
        assert out["active"] == "unknown"
        assert "error" in out

    def test_error_file_not_found(self, monkeypatch) -> None:
        monkeypatch.setattr(pv.subprocess, "run", mock.Mock(side_effect=FileNotFoundError("no systemctl")))
        out = pv.get_service_status("x.service")
        assert out["active"] == "unknown"


class TestGetVram:
    def test_ok(self, monkeypatch) -> None:
        res = SimpleNamespace(returncode=0, stdout="8192, 2048, 6144")
        monkeypatch.setattr(pv.subprocess, "run", mock.Mock(return_value=res))
        out = pv.get_vram()
        assert out == {"total_mb": 8192, "used_mb": 2048, "free_mb": 6144, "used_pct": 25.0}

    def test_returncode_error(self, monkeypatch) -> None:
        res = SimpleNamespace(returncode=1, stdout="")
        monkeypatch.setattr(pv.subprocess, "run", mock.Mock(return_value=res))
        assert pv.get_vram() is None

    def test_formato_invalido(self, monkeypatch) -> None:
        res = SimpleNamespace(returncode=0, stdout="solo un campo")
        monkeypatch.setattr(pv.subprocess, "run", mock.Mock(return_value=res))
        assert pv.get_vram() is None

    def test_excepcion(self, monkeypatch) -> None:
        monkeypatch.setattr(pv.subprocess, "run", mock.Mock(side_effect=ValueError("bad")))
        assert pv.get_vram() is None

    def test_total_cero(self, monkeypatch) -> None:
        res = SimpleNamespace(returncode=0, stdout="0, 0, 0")
        monkeypatch.setattr(pv.subprocess, "run", mock.Mock(return_value=res))
        out = pv.get_vram()
        assert out["used_pct"] == 0


class TestLoadStateFile:
    def test_no_existe(self, tmp_path) -> None:
        assert pv.load_state_file(str(tmp_path / "nope.json")) is None

    def test_ok(self, tmp_path) -> None:
        f = tmp_path / "s.json"
        f.write_text('{"mode": "NORMAL"}')
        assert pv.load_state_file(str(f)) == {"mode": "NORMAL"}

    def test_corrupto(self, tmp_path) -> None:
        f = tmp_path / "s.json"
        f.write_text("not json")
        assert pv.load_state_file(str(f)) is None

    def test_error_os(self, tmp_path) -> None:
        with mock.patch("builtins.open", side_effect=OSError("ro")):
            assert pv.load_state_file(str(tmp_path / "s.json")) is None


class TestCollectContext:
    def test_completo(self, monkeypatch, tmp_path) -> None:
        monkeypatch.setattr(pv, "get_service_status", mock.Mock(return_value={"name": "s", "active": "active", "pid": 1}))
        monkeypatch.setattr(pv, "get_vram", mock.Mock(return_value={"total_mb": 1, "used_mb": 1, "free_mb": 1, "used_pct": 1}))
        hetzner = tmp_path / "hetzner.json"
        hetzner.write_text('{"estado": "ok"}')
        snc = tmp_path / "snc.json"
        snc.write_text('{"mode": "SNC"}')
        monkeypatch.setattr(pv, "STATE_FILES", {"hetzner": str(hetzner), "snc": str(snc)})
        ctx = pv.collect_context()
        assert len(ctx["services"]) == 4
        assert ctx["hetzner"] == {"estado": "ok"}
        assert ctx["snc_mode"] == "SNC"

    def test_vram_no_disponible(self, monkeypatch) -> None:
        monkeypatch.setattr(pv, "get_vram", mock.Mock(return_value=None))
        ctx = pv.collect_context()
        assert ctx["vram"] == {"error": "nvidia-smi no disponible"}

    def test_sin_state_files(self, monkeypatch, tmp_path) -> None:
        monkeypatch.setattr(pv, "STATE_FILES", {"hetzner": str(tmp_path / "h"), "snc": str(tmp_path / "s")})
        ctx = pv.collect_context()
        assert "hetzner" not in ctx
        assert "snc_mode" not in ctx


class TestFormatContext:
    def test_servicios_y_vram(self) -> None:
        ctx = {
            "services": [{"name": "s1", "active": "active", "pid": 5}, {"name": "s2", "active": "inactive", "pid": None}],
            "vram": {"total_mb": 8, "used_mb": 2, "free_mb": 6, "used_pct": 25.0},
        }
        txt = pv.format_context_for_prompt(ctx)
        assert "s1: active (PID 5)" in txt
        assert "s2: inactive" in txt
        assert "Total: 8 MB" in txt
        assert "Usado: 2 MB (25.0%)" in txt

    def test_vram_error(self) -> None:
        txt = pv.format_context_for_prompt({"services": [], "vram": {"error": "no disponible"}})
        assert "no disponible" in txt

    def test_hetzner_y_snc(self) -> None:
        ctx = {"services": [], "vram": {}, "hetzner": {"a": 1}, "snc_mode": "SNC"}
        txt = pv.format_context_for_prompt(ctx)
        assert "ALEMANIA" in txt
        assert "MODO SNC: SNC" in txt
        assert "Timestamp" in txt


class TestMain:
    def test_sin_argumentos_logea_contexto(self, monkeypatch) -> None:
        monkeypatch.setattr(pv.sys, "argv", ["plan_validator.py"])
        monkeypatch.setattr(pv, "collect_context", mock.Mock(return_value={"a": 1}))
        logger = mock.Mock()
        monkeypatch.setattr(pv, "logger", logger)
        pv.main()
        logger.info.assert_called_once()

    def test_debate_consensus(self, monkeypatch) -> None:
        monkeypatch.setattr(pv.sys, "argv", ["plan_validator.py", "--debate"])
        monkeypatch.setattr(pv.sys, "stdin", SimpleNamespace(read=lambda: '{"plan": "x"}'))
        monkeypatch.setattr(pv, "collect_context", mock.Mock(return_value={"c": 1}))
        monkeypatch.setattr(pv.sys, "exit", mock.Mock())

        class FakeLock:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        debate = mock.AsyncMock(return_value={"verdict": "CONSENSUS"})
        monkeypatch.setattr("core.debate.lockfile.DebateLock", FakeLock)
        monkeypatch.setattr("core.debate.debate_engine.run_debate", debate)
        pv.main()
        pv.sys.exit.assert_called_once_with(0)

    def test_debate_human_arbitration(self, monkeypatch) -> None:
        monkeypatch.setattr(pv.sys, "argv", ["plan_validator.py", "--debate"])
        monkeypatch.setattr(pv.sys, "stdin", SimpleNamespace(read=lambda: '{"plan": "x"}'))
        monkeypatch.setattr(pv, "collect_context", mock.Mock(return_value={}))
        monkeypatch.setattr(pv.sys, "exit", mock.Mock())

        class FakeLock:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        debate = mock.AsyncMock(return_value={"verdict": "HUMAN_ARBITRATION"})
        monkeypatch.setattr("core.debate.lockfile.DebateLock", FakeLock)
        monkeypatch.setattr("core.debate.debate_engine.run_debate", debate)
        pv.main()
        pv.sys.exit.assert_called_once_with(2)

    def test_debate_rechazo(self, monkeypatch) -> None:
        monkeypatch.setattr(pv.sys, "argv", ["plan_validator.py", "--debate"])
        monkeypatch.setattr(pv.sys, "stdin", SimpleNamespace(read=lambda: '{"plan": "x"}'))
        monkeypatch.setattr(pv, "collect_context", mock.Mock(return_value={}))
        monkeypatch.setattr(pv.sys, "exit", mock.Mock())

        class FakeLock:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        debate = mock.AsyncMock(return_value={"verdict": "REJECTED"})
        monkeypatch.setattr("core.debate.lockfile.DebateLock", FakeLock)
        monkeypatch.setattr("core.debate.debate_engine.run_debate", debate)
        pv.main()
        pv.sys.exit.assert_called_once_with(1)
