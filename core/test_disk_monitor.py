"""Tests for core/disk_monitor.py — disk space monitoring."""

from unittest.mock import MagicMock, patch


class TestMonitorear:
    """monitorear() — returns disk usage with status."""

    def test_returns_dict_with_expected_keys(self):
        from core.disk_monitor import monitorear

        result = monitorear()
        assert isinstance(result, dict)
        for key in ("ok", "gb_libres", "gb_totales", "estado"):
            assert key in result, f"Missing key: {key}"

    def test_ok_is_bool(self):
        from core.disk_monitor import monitorear

        result = monitorear()
        assert isinstance(result["ok"], bool)

    def test_gb_are_floats(self):
        from core.disk_monitor import monitorear

        result = monitorear()
        assert isinstance(result["gb_libres"], float)
        assert isinstance(result["gb_totales"], float)

    def test_estado_is_valid(self):
        from core.disk_monitor import monitorear

        result = monitorear()
        assert result["estado"] in ("ok", "warning", "critical", "error")

    @patch("core.disk_monitor.psutil.disk_usage")
    def test_ok_when_free_above_5gb(self, mock_usage: MagicMock):
        usage = MagicMock()
        usage.total = 500 * (1024**3)  # 500 GB
        usage.free = 100 * (1024**3)  # 100 GB free
        mock_usage.return_value = usage

        from core.disk_monitor import monitorear

        result = monitorear()
        assert result["ok"] is True
        assert result["estado"] == "ok"
        assert result["gb_libres"] > 5

    @patch("core.disk_monitor.psutil.disk_usage")
    def test_warning_when_free_between_1_and_5gb(self, mock_usage: MagicMock):
        usage = MagicMock()
        usage.total = 500 * (1024**3)
        usage.free = 3 * (1024**3)  # 3 GB free
        mock_usage.return_value = usage

        from core.disk_monitor import monitorear

        result = monitorear()
        assert result["estado"] == "warning"

    @patch("core.disk_monitor.psutil.disk_usage")
    def test_critical_when_free_below_1gb(self, mock_usage: MagicMock):
        usage = MagicMock()
        usage.total = 500 * (1024**3)
        usage.free = 0.5 * (1024**3)  # 0.5 GB free
        mock_usage.return_value = usage

        from core.disk_monitor import monitorear

        result = monitorear()
        assert result["estado"] == "critical"

    @patch("core.disk_monitor.psutil.disk_usage")
    def test_error_when_psutil_fails(self, mock_usage: MagicMock):
        mock_usage.side_effect = OSError("disk unavailable")

        from core.disk_monitor import monitorear

        result = monitorear()
        assert result["ok"] is False
        assert result["estado"] == "error"
