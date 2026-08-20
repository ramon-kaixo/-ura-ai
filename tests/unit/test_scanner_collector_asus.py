"""Tests de cobertura para motor/scanner/collector_asus.py (gate 85%, meta 100)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from motor.scanner import collector_asus


class FakeResult:
    def __init__(self, ok: bool = True, stdout: str = "") -> None:
        self.ok = ok
        self.stdout = stdout


class TestEscaneoAsus:
    @patch("motor.scanner.collector_asus._executor")
    def test_sin_host_salta(self, executor: MagicMock) -> None:
        config = MagicMock()
        config.asus_host = ""
        r = collector_asus.escanear_asus(config)
        assert r == {"ollama": False, "qdrant": False, "whisper": False, "temp_gpu": 0}
        executor.run.assert_not_called()

    @patch("motor.scanner.collector_asus._executor")
    def test_todos_ok(self, executor: MagicMock) -> None:
        executor.run.return_value = FakeResult(ok=True)
        config = MagicMock()
        config.asus_host = "10.0.0.1"
        with patch.object(collector_asus, "_check_temp", return_value=52.3) as ct:
            r = collector_asus.escanear_asus(config)
        assert r["ollama"] and r["qdrant"] and r["whisper"]
        assert r["temp_gpu"] == 52.3
        ct.assert_called_once()

    @patch("motor.scanner.collector_asus._executor")
    def test_excepcion_en_check(self, executor: MagicMock) -> None:
        executor.run.side_effect = RuntimeError("no curl")
        config = MagicMock()
        config.asus_host = "10.0.0.1"
        r = collector_asus.escanear_asus(config)
        assert not r["ollama"] and not r["qdrant"] and not r["whisper"]
        assert r["temp_gpu"] == 0

    @patch("motor.scanner.collector_asus._executor")
    def test_temp_con_error(self, executor: MagicMock) -> None:
        executor.run.return_value = FakeResult(ok=True, stdout="")
        config = MagicMock()
        config.asus_host = "10.0.0.1"
        r = collector_asus.escanear_asus(config)
        assert r["temp_gpu"] == 0


class TestChecks:
    @patch("motor.scanner.collector_asus._executor")
    def test_check_ollama_ok(self, executor: MagicMock) -> None:
        executor.run.return_value = FakeResult(ok=True)
        assert collector_asus._check_ollama("host") is True
        cmd = executor.run.call_args[0][0]
        assert any(f":{collector_asus.PUERTO_OLLAMA}" in c for c in cmd)

    @patch("motor.scanner.collector_asus._executor")
    def test_check_qdrant_ok(self, executor: MagicMock) -> None:
        executor.run.return_value = FakeResult(ok=True)
        assert collector_asus._check_qdrant("host") is True

    @patch("motor.scanner.collector_asus._executor")
    def test_check_whisper_falla(self, executor: MagicMock) -> None:
        executor.run.return_value = FakeResult(ok=False)
        assert collector_asus._check_whisper("host") is False

    @patch("motor.scanner.collector_asus._executor")
    def test_check_temp_lee_stdout(self, executor: MagicMock) -> None:
        executor.run.return_value = FakeResult(ok=True, stdout="52300\n")
        with patch.object(collector_asus, "get_secret", return_value="root"):
            temp = collector_asus._check_temp("host")
        assert temp == 52.3

    @patch("motor.scanner.collector_asus._executor")
    def test_check_temp_con_ssh_user(self, executor: MagicMock) -> None:
        executor.run.return_value = FakeResult(ok=True, stdout="41000\n")
        with patch.object(collector_asus, "get_secret", return_value="ramon"):
            collector_asus._check_temp("10.0.0.1")
        target = executor.run.call_args[0][0]
        assert "ramon@10.0.0.1" in target

    @patch("motor.scanner.collector_asus._executor")
    def test_check_temp_error_returns_cero(self, executor: MagicMock) -> None:
        executor.run.side_effect = RuntimeError("ssh failed")
        assert collector_asus._check_temp("host") == 0
