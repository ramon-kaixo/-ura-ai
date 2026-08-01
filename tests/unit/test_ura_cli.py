"""Tests para ura.py — entry point CLI."""

import sys
from unittest.mock import patch


class TestUraCli:
    def test_main_no_args_returns_zero(self):
        with patch.object(sys, "argv", ["ura.py"]):
            import ura

            result = ura.main()
            assert result == 0

    def test_main_help_flag_returns_zero(self):
        with patch.object(sys, "argv", ["ura.py", "--help"]):
            import importlib

            ura = importlib.import_module("ura")
            result = ura.main()
            assert result == 0

    def test_main_status_remapped_to_dashboard(self):
        with patch.object(sys, "argv", ["ura.py", "status"]):
            with patch("ura._motor_main") as mock_main:
                import importlib

                ura = importlib.import_module("ura")
                ura.main()
                assert sys.argv[1] == "dashboard"
                mock_main.assert_called_once()

    def test_main_finalize_calls_motor_main(self):
        with patch.object(sys, "argv", ["ura.py", "finalize", "-m", "test"]):
            with patch("ura._motor_main") as mock_main:
                import importlib

                ura = importlib.import_module("ura")
                ura.main()
                mock_main.assert_called_once()
