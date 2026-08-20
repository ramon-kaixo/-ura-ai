"""Tests de cobertura para motor/scanner/_state.py (gate 90%)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from motor.scanner._state import ScannerState, build_scanner_state


class TestScannerState:
    def test_dataclass_frozen(self) -> None:
        s = ScannerState(executor="e", config="c")
        assert s.executor == "e"
        assert s.config == "c"


class TestBuildScannerState:
    def test_con_config(self) -> None:
        cfg = MagicMock()
        with patch("motor.core.executor.SubprocessExecutor") as se:
            s = build_scanner_state(cfg)
        assert s.config is cfg
        assert s.executor is se.return_value

    def test_sin_config_carga_default(self) -> None:
        with patch("motor.core.config.UraConfig.load", return_value="cfg-default") as load, \
             patch("motor.core.executor.SubprocessExecutor"):
            s = build_scanner_state()
        load.assert_called_once()
        assert s.config == "cfg-default"
