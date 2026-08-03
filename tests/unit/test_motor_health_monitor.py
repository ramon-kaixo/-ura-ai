"""Tests para motor/observability/prometheus_exporter.py y motor/health_monitor.py."""
from __future__ import annotations

from unittest import mock

import pytest


class FakeSnap:
    def __init__(self, value=0, labels=None, count=0, sum=0.0):
        self._value = value
        self._labels = labels or {}
        self._count = count
        self._sum = sum

    def snapshot(self):
        return {"value": self._value, "labels": self._labels, "count": self._count, "sum": self._sum}


class TestPrometheusExporter:
    def _counter(self, snapshots):
        c = mock.Mock()
        c._counters = {f"k{i}": s for i, s in enumerate(snapshots)}
        return c

    def _hist(self, snapshots):
        h = mock.Mock()
        h._histograms = {f"k{i}": s for i, s in enumerate(snapshots)}
        return h

    def test_counter_lines_con_labels(self) -> None:
        from motor.observability.prometheus_exporter import _counter_lines

        c = self._counter([FakeSnap(value=5, labels={"mode": "chat"})])
        lines = _counter_lines(c, "ura_test", "desc")
        assert lines[0] == "# HELP ura_test desc"
        assert lines[1] == "# TYPE ura_test counter"
        assert 'ura_test{mode="chat"} 5' in lines

    def test_counter_lines_sin_labels(self) -> None:
        from motor.observability.prometheus_exporter import _counter_lines

        c = self._counter([FakeSnap(value=3)])
        lines = _counter_lines(c, "ura_x", "d")
        assert "ura_x 3" in lines

    def test_histogram_lines(self) -> None:
        from motor.observability.prometheus_exporter import _histogram_lines

        h = self._hist([FakeSnap(labels={"mode": "chat"}, count=10, sum=5.5)])
        lines = _histogram_lines(h, "ura_lat", "d")
        assert 'ura_lat{mode="chat",}_count 10' in lines
        assert 'ura_lat{mode="chat",}_sum 5.5' in lines

    def test_histogram_sin_labels(self) -> None:
        from motor.observability.prometheus_exporter import _histogram_lines

        h = self._hist([FakeSnap(count=2, sum=1.0)])
        lines = _histogram_lines(h, "ura_lat", "d")
        assert "ura_lat_count 2" in lines
        assert "ura_lat_sum 1.0" in lines

    def test_export_metrics(self, monkeypatch) -> None:
        import motor.observability.prometheus_exporter as pe

        monkeypatch.setattr(pe, "requests_total", self._counter([FakeSnap(value=1)]))
        monkeypatch.setattr(pe, "request_latency", self._hist([FakeSnap(count=1, sum=0.5)]))
        monkeypatch.setattr(pe, "tokens_total", self._counter([FakeSnap(value=10)]))
        monkeypatch.setattr(pe, "errors_total", self._counter([FakeSnap(value=0)]))
        out = pe.export_metrics()
        assert "# URA metrics" in out
        assert "ura_requests_total" in out
        assert "ura_request_latency_seconds" in out
        assert "ura_tokens_total" in out
        assert "ura_errors_total" in out


class TestHealthMonitor:
    @pytest.fixture(autouse=True)
    def reset_prev(self, monkeypatch):
        import motor.health_monitor as hm

        monkeypatch.setattr(hm, "_PREVIOUS", {})
        monkeypatch.setattr(hm, "_last_backup", 0)
        yield

    def _health(self, statuses: dict) -> dict:
        return {"global": "ok", "components": {k: {"status": v} for k, v in statuses.items()}}

    def test_fetch_health_ok(self, monkeypatch) -> None:
        import motor.health_monitor as hm

        resp = mock.Mock()
        resp.read.return_value = b'{"global": "ok"}'
        resp.__enter__ = mock.Mock(return_value=resp)
        resp.__exit__ = mock.Mock(return_value=False)
        monkeypatch.setattr("urllib.request.urlopen", mock.Mock(return_value=resp))
        out = hm._fetch_health()
        assert out == {"global": "ok"}

    def test_fetch_health_error(self, monkeypatch) -> None:
        import motor.health_monitor as hm

        monkeypatch.setattr("urllib.request.urlopen", mock.Mock(side_effect=OSError("net")))
        assert hm._fetch_health() is None

    def test_check_sin_health(self, monkeypatch) -> None:
        import motor.health_monitor as hm

        monkeypatch.setattr(hm, "_fetch_health", mock.Mock(return_value=None))
        r = hm.check_and_alert()
        assert r == {"status": "error", "detail": "No se pudo obtener health"}

    def test_check_nuevo_degradado(self, monkeypatch) -> None:
        import motor.health_monitor as hm

        monkeypatch.setattr(hm, "_fetch_health", mock.Mock(return_value=self._health({"ollama": "degraded"})))
        alert = mock.Mock(return_value=True)
        monkeypatch.setattr(hm, "_send_alert", alert)
        r = hm.check_and_alert()
        assert "ollama" in r["new_degraded"]
        alert.assert_called_once()
        assert "degraded" in alert.call_args.args[0]

    def test_check_critical(self, monkeypatch) -> None:
        import motor.health_monitor as hm

        monkeypatch.setattr(hm, "_fetch_health", mock.Mock(return_value=self._health({"api": "unhealthy"})))
        alert = mock.Mock()
        monkeypatch.setattr(hm, "_send_alert", alert)
        hm.check_and_alert()
        assert alert.call_args.args[1] == "critical"

    def test_check_recuperacion(self, monkeypatch) -> None:
        import motor.health_monitor as hm

        hm._PREVIOUS = {"ollama": "degraded"}
        monkeypatch.setattr(hm, "_fetch_health", mock.Mock(return_value=self._health({"ollama": "healthy"})))
        alert = mock.Mock()
        monkeypatch.setattr(hm, "_send_alert", alert)
        r = hm.check_and_alert()
        assert "ollama" in r["recovered"]
        assert alert.call_args.args[1] == "info"

    def test_check_sin_cambios(self, monkeypatch) -> None:
        import motor.health_monitor as hm

        hm._PREVIOUS = {"ollama": "healthy"}
        monkeypatch.setattr(hm, "_fetch_health", mock.Mock(return_value=self._health({"ollama": "healthy"})))
        r = hm.check_and_alert()
        assert r["new_degraded"] == []
        assert r["recovered"] == []

    def test_send_alert_ok(self, monkeypatch) -> None:
        import motor.health_monitor as hm

        notify = mock.Mock(return_value=True)
        monkeypatch.setattr("core.notifier.notify", notify)
        assert hm._send_alert("msg") is True
        notify.assert_called_once_with("msg", level="warning")

    def test_send_alert_fallback(self, monkeypatch) -> None:
        import motor.health_monitor as hm

        monkeypatch.setattr("core.notifier.notify", mock.Mock(side_effect=ImportError("no")))
        assert hm._send_alert("msg") is False

    def test_backup_memory_dentro_intervalo(self, monkeypatch) -> None:
        import motor.health_monitor as hm

        monkeypatch.setattr(hm, "_last_backup", 9999999999)
        monkeypatch.setattr(hm, "BACKUP_INTERVAL", 3600)
        copy = mock.Mock()
        monkeypatch.setattr("motor.health_monitor.copy2", copy)
        hm._backup_memory()
        copy.assert_not_called()

    def test_backup_memory_ok(self, monkeypatch, tmp_path) -> None:
        import motor.health_monitor as hm

        db = tmp_path / "memory.db"
        db.write_bytes(b"data")
        backups = tmp_path / "backups"
        monkeypatch.setattr(hm, "MEMORY_DB", str(db))
        monkeypatch.setattr(hm, "BACKUP_DIR", backups)
        monkeypatch.setattr(hm, "BACKUP_INTERVAL", 0)
        hm._backup_memory()
        assert len(list(backups.glob("memory_*.db"))) == 1

    def test_backup_memory_sin_db(self, monkeypatch, tmp_path) -> None:
        import motor.health_monitor as hm

        monkeypatch.setattr(hm, "MEMORY_DB", str(tmp_path / "nope.db"))
        monkeypatch.setattr(hm, "BACKUP_INTERVAL", 0)
        hm._backup_memory()  # no debe lanzar

    def test_main_backup(self, monkeypatch) -> None:
        import motor.health_monitor as hm

        monkeypatch.setattr("sys.argv", ["hm.py", "--backup"])
        backup = mock.Mock()
        monkeypatch.setattr(hm, "_backup_memory", backup)
        hm.main()
        backup.assert_called_once()

    def test_main_una_ejecucion(self, monkeypatch) -> None:
        import motor.health_monitor as hm

        monkeypatch.setattr("sys.argv", ["hm.py"])
        monkeypatch.setattr(hm, "check_and_alert", mock.Mock(return_value={"status": "ok"}))
        monkeypatch.setattr("builtins.print", mock.Mock())
        hm.main()
