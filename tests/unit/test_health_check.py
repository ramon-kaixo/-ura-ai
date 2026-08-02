"""Tests para monitor/health_check.py — Fase 4 (B2).

Todo el I/O externo (ssh, urllib, disco) se simula con monkeypatch.
"""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING, Self

if TYPE_CHECKING:
    import pytest

import monitor.health_check as hc


class _FakeResult:
    def __init__(self, stdout: str = "", returncode: int = 0) -> None:
        self.stdout = stdout
        self.returncode = returncode


class TestSshRun:
    def test_success_returns_stdout(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(subprocess, "run", lambda *a, **k: _FakeResult("  hola  ", 0))
        assert hc.ssh_run("df -h") == "hola"

    def test_nonzero_returns_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(subprocess, "run", lambda *a, **k: _FakeResult("salida", 1))
        assert hc.ssh_run("df -h") == ""

    def test_exception_returns_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def boom(*a: object, **k: object) -> None:
            raise subprocess.TimeoutExpired("ssh", 5)

        monkeypatch.setattr(subprocess, "run", boom)
        assert hc.ssh_run("df -h") == ""


class TestMeasureSshLatency:
    def test_returns_ms(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(subprocess, "run", lambda *a, **k: _FakeResult("ok", 0))
        assert hc.measure_ssh_latency() >= 0

    def test_exception_returns_minus_one(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def boom(*a: object, **k: object) -> None:
            raise OSError("no ssh")

        monkeypatch.setattr(subprocess, "run", boom)
        assert hc.measure_ssh_latency() == -1


class _FakeUrlOpen:
    def __init__(self, exc: Exception | None = None) -> None:
        self.exc = exc

    def __call__(self, *a: object, **k: object) -> _FakeUrlOpen:
        if self.exc is not None:
            raise self.exc
        return self

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_a: object) -> None:
        return None


class TestMeasureHttpLatency:
    def test_returns_ms(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(hc.urllib.request, "urlopen", _FakeUrlOpen())
        assert hc.measure_http_latency() >= 0

    def test_exception_returns_minus_one(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(hc.urllib.request, "urlopen", _FakeUrlOpen(OSError("conn refused")))
        assert hc.measure_http_latency() == -1


class TestCheckDisk:
    def test_no_output_alerts(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(hc, "ssh_run", lambda cmd: "")
        alerts, stats = hc.check_disk()
        assert "No se pudo obtener uso de disco" in alerts
        assert stats == {}

    def test_parses_and_alerts_thresholds(self, monkeypatch: pytest.MonkeyPatch) -> None:
        output = "Filesystem Size Used Avail Use% Mounted on\n/dev/sda1 100G 95G 5G 95% /\n/dev/sdb1 200G 100G 100G 50% /home\nbasura"
        monkeypatch.setattr(hc, "ssh_run", lambda cmd: output)
        alerts, stats = hc.check_disk()
        assert stats["/"]["pct"] == 95
        assert stats["/home"]["pct"] == 50
        assert len(alerts) == 2
        assert any("95% usado" in a for a in alerts)
        assert any("solo 5.0GB libres" in a for a in alerts)

    def test_avail_not_g_skipped(self, monkeypatch: pytest.MonkeyPatch) -> None:
        output = "Filesystem Size Used Avail Use% Mounted on\n/dev/x 10G 5G 50M 50% /"
        monkeypatch.setattr(hc, "ssh_run", lambda cmd: output)
        alerts, stats = hc.check_disk()
        assert stats["/"]["pct"] == 50
        assert alerts == []

    def test_bad_pct_skipped(self, monkeypatch: pytest.MonkeyPatch) -> None:
        output = "Filesystem Size Used Avail Use% Mounted on\n/dev/x 10G 5G 1G abc /"
        monkeypatch.setattr(hc, "ssh_run", lambda cmd: output)
        _alerts, stats = hc.check_disk()
        assert stats == {}


class TestCheckRam:
    def test_no_output(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(hc, "ssh_run", lambda cmd: "")
        assert hc.check_ram() == ([], {})

    def test_low_mem_alert_in_gb(self, monkeypatch: pytest.MonkeyPatch) -> None:
        output = "Mem: 32Gi 28Gi 3Gi 1Gi 1Gi 2Gi\nSwap: 8Gi 0Gi 8Gi"
        monkeypatch.setattr(hc, "ssh_run", lambda cmd: output)
        alerts, stats = hc.check_ram()
        assert stats["Mem"]["avail"] == "3Gi"
        assert any("RAM baja" in a for a in alerts)

    def test_low_mem_alert_in_mb_converted(self, monkeypatch: pytest.MonkeyPatch) -> None:
        output = "Mem: 32Gi 28Gi 512Mi 1Gi 1Gi 2Gi"
        monkeypatch.setattr(hc, "ssh_run", lambda cmd: output)
        alerts, _stats = hc.check_ram()
        assert any("RAM baja" in a for a in alerts)

    def test_high_mem_no_alert(self, monkeypatch: pytest.MonkeyPatch) -> None:
        output = "Mem: 32Gi 4Gi 28Gi 1Gi 1Gi 2Gi"
        monkeypatch.setattr(hc, "ssh_run", lambda cmd: output)
        alerts, _stats = hc.check_ram()
        assert alerts == []


class TestCheckLoad:
    def test_no_output(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(hc, "ssh_run", lambda cmd: "")
        assert hc.check_load() == ([], {})

    def test_high_load_alert(self, monkeypatch: pytest.MonkeyPatch) -> None:
        output = "12:00:00 up 10 days, load average: 9.5, 8.0, 5.0"
        monkeypatch.setattr(hc, "ssh_run", lambda cmd: output)
        alerts, stats = hc.check_load()
        assert stats["load"] == [9.5, 8.0, 5.0]
        assert any("CPU load alta" in a for a in alerts)

    def test_normal_load(self, monkeypatch: pytest.MonkeyPatch) -> None:
        output = "12:00:00 up 10 days, load average: 1.0, 0.8, 0.5"
        monkeypatch.setattr(hc, "ssh_run", lambda cmd: output)
        alerts, _stats = hc.check_load()
        assert alerts == []


class TestCheckOllamaModels:
    def test_no_output(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(hc, "ssh_run", lambda cmd: "")
        assert hc.check_ollama_models() == []

    def test_parses_models(self, monkeypatch: pytest.MonkeyPatch) -> None:
        output = "NAME ID SIZE PROCESSOR UNTIL\nqwen3:32b xyz 20GB 100% CPU 5m"
        monkeypatch.setattr(hc, "ssh_run", lambda cmd: output)
        models = hc.check_ollama_models()
        assert models == [{"model": "qwen3:32b", "size": "20GB"}]


class TestMain:
    def test_returns_zero_without_alert_file(self, monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
        monkeypatch.setattr(hc, "ALERT_FILE", tmp_path / "alerts.log")
        monkeypatch.setattr(hc, "ssh_run", lambda cmd: "salida normal")
        monkeypatch.setattr(hc, "measure_ssh_latency", lambda: 5.0)
        monkeypatch.setattr(hc, "measure_http_latency", lambda: 5.0)
        assert hc.main() == 0

    def test_writes_alert_file_on_problems(self, monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
        alert_file = tmp_path / "alerts.log"
        monkeypatch.setattr(hc, "ALERT_FILE", alert_file)
        monkeypatch.setattr(hc, "ssh_run", lambda cmd: "")
        monkeypatch.setattr(hc, "measure_ssh_latency", lambda: 5.0)
        monkeypatch.setattr(hc, "measure_http_latency", lambda: 5.0)
        hc.main()
        assert alert_file.exists()
        content = alert_file.read_text()
        assert "No se pudo obtener uso de disco" in content
