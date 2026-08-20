"""Tests de cobertura para motor/scanner/collector_hw_asus.py (gate 85%, meta 100)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from motor.scanner import collector_hw_asus


class FakeResult:
    def __init__(self, ok: bool = True, stdout: str = "") -> None:
        self.ok = ok
        self.stdout = stdout


class TestEscaneoHwAsus:
    @patch("motor.scanner.collector_hw_asus._executor")
    def test_temp_gpu_parametrizado(self, executor: MagicMock) -> None:
        with patch.object(collector_hw_asus, "_smart_ok", return_value=True) as sm, \
             patch.object(collector_hw_asus, "_thermal_zones", return_value={"zone0": 45.0}):
            r = collector_hw_asus.escanear_hw_asus(temp_gpu=33.3)
        assert r["ok"] is True
        assert r["tipo"] == "fisico"
        assert r["temp_gpu"] == 33.3
        assert r["thermal_zones"] == {"zone0": 45.0}
        sm.assert_called_once()

    @patch("motor.scanner.collector_hw_asus._executor")
    def test_temp_gpu_auto(self, executor: MagicMock) -> None:
        with patch.object(collector_hw_asus, "_temp_gpu_orin", return_value=500.0) as tg, \
             patch.object(collector_hw_asus, "_smart_ok", return_value=True), \
             patch.object(collector_hw_asus, "_thermal_zones", return_value={}):
            r = collector_hw_asus.escanear_hw_asus()
        assert r["temp_gpu"] == 500.0
        tg.assert_called_once()


class TestFunciones:
    @patch("motor.scanner.collector_hw_asus._executor")
    def test_smart_ok_passed(self, executor: MagicMock) -> None:
        executor.run.return_value = FakeResult(ok=True, stdout="SMART overall-health self-assessment test result: PASSED")
        assert collector_hw_asus._smart_ok() is True

    @patch("motor.scanner.collector_hw_asus._executor")
    def test_smart_no_passed(self, executor: MagicMock) -> None:
        executor.run.return_value = FakeResult(ok=True, stdout="FAILED")
        assert collector_hw_asus._smart_ok() is False

    @patch("motor.scanner.collector_hw_asus._executor")
    def test_smart_error_default_true(self, executor: MagicMock) -> None:
        executor.run.side_effect = RuntimeError("no smartctl")
        assert collector_hw_asus._smart_ok() is True

    @patch("motor.scanner.collector_hw_asus._executor.run")
    def test_smart_usa_sudo(self, exec_run: MagicMock) -> None:
        exec_run.return_value = FakeResult(ok=True, stdout="PASSED")
        collector_hw_asus._smart_ok("/dev/sda")
        assert exec_run.call_args[0][0][0] == "sudo"

    @patch("motor.scanner.collector_hw_asus.glob.glob")
    def test_thermal_zones_lee(self, mock_glob: MagicMock) -> None:
        mock_glob.return_value = ["/sys/class/thermal/thermal_zone0/temp"]
        with patch("builtins.open", __builtins__ if False else None) as _:
            pass  # se testea abajo con open real en tmp
        # reemplazamos open por un objeto que devuelve "45000"
        import io
        fake = io.StringIO("45000\n")
        with patch("builtins.open", return_value=fake):
            zonas = collector_hw_asus._thermal_zones()
        assert zonas == {"thermal_zone0": 45.0}

    @patch("motor.scanner.collector_hw_asus.glob.glob")
    def test_thermal_zones_error(self, mock_glob: MagicMock) -> None:
        mock_glob.return_value = ["/ruta/inexistente/zona0/temp"]
        with patch("builtins.open", side_effect=OSError("no existe")):
            zonas = collector_hw_asus._thermal_zones()
        assert zonas == {}

    @patch("motor.scanner.collector_hw_asus._executor")
    def test_temp_gpu_orin_encuentra(self, executor: MagicMock) -> None:
        executor.run.return_value = FakeResult(ok=True, stdout="GPU@450mW AVG 10")
        assert collector_hw_asus._temp_gpu_orin() == 450

    @patch("motor.scanner.collector_hw_asus._executor")
    def test_temp_gpu_orin_no_match(self, executor: MagicMock) -> None:
        executor.run.return_value = FakeResult(ok=True, stdout="sin datos GPU")
        assert collector_hw_asus._temp_gpu_orin() == 0.0

    @patch("motor.scanner.collector_hw_asus._executor")
    def test_temp_gpu_orin_error(self, executor: MagicMock) -> None:
        executor.run.side_effect = RuntimeError("no tegrastats")
        assert collector_hw_asus._temp_gpu_orin() == 0.0
