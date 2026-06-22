"""Tests para detección de anomalías en SNC (monitor/snc.py)."""

import signal
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# snc.py usa `from error_logger import ErrorLogger` (import implícito del mismo dir)
_monitor_dir = str(Path(__file__).resolve().parent.parent / "monitor")
if _monitor_dir not in sys.path:
    sys.path.insert(0, _monitor_dir)

from monitor.snc import (
    _BUCLE_TIMEOUT,
    _CPU_DETECTION_ENABLED,
    _aislar_bucle,
    _check_umbrales,
    _limpiar_zombies,
    _pending_sigcont,
    _sigcont_seguro,
    check_bucle_cpu,
    check_opencode_colgado,
    check_zombies,
)


class TestCheckZombies:
    def test_returns_empty_when_no_zombies(self, tmp_path):
        result = check_zombies()
        assert isinstance(result, list)

    def test_detects_zombie(self, tmp_path):
        fake_proc = tmp_path / "12345"
        fake_proc.mkdir()
        (fake_proc / "status").write_text("Name:\tzombie_proc\nState:\tZ (zombie)\n")
        with patch("monitor.snc.Path", return_value=tmp_path):
            with patch("monitor.snc.Path.iterdir", return_value=[fake_proc]):
                zombies = check_zombies()
                assert 12345 in zombies

    def test_skips_non_digit(self, tmp_path):
        fake = tmp_path / "abc"
        fake.mkdir()
        with patch("monitor.snc.Path", return_value=tmp_path):
            with patch("monitor.snc.Path.iterdir", return_value=[fake]):
                zombies = check_zombies()
                assert zombies == []


class TestLimpiarZombies:
    def test_kills_zombie(self):
        killed = []

        def fake_kill(pid, sig):
            killed.append((pid, sig))

        with patch("monitor.snc.check_zombies", return_value=[99999]):
            with patch("monitor.snc.os.kill", side_effect=fake_kill):
                _limpiar_zombies()
                assert (99999, signal.SIGKILL) in killed


class TestCheckBucleCpu:
    def test_returns_list(self):
        result = check_bucle_cpu(umbral=999.0)
        assert isinstance(result, list)

    def test_filters_by_threshold(self):
        fake_ps = (
            "USER         PID %CPU %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND\n"
            "root        1234 95.0  1.0 12345 6789 pts/0    R+   10:00   1:23 python3\n"
            "root        5678 10.0  1.0 12345 6789 pts/1    S+   10:00   0:05 python3\n"
        )
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.stdout = fake_ps
            mock_run.return_value.returncode = 0
            result = check_bucle_cpu(umbral=80.0)
            assert len(result) == 1
            assert result[0][0] == 1234

    def test_empty_when_no_process(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.stdout = "USER PID %CPU COMM\n"
            mock_run.return_value.returncode = 0
            result = check_bucle_cpu(umbral=50.0)
            assert result == []


class TestAislarBucle:
    def setup_method(self):
        _pending_sigcont.clear()

    def test_skips_if_pid_zero(self):
        with patch("monitor.snc.os.kill") as mock_kill:
            _aislar_bucle(0, "opencode", 95.0)
            mock_kill.assert_not_called()

    def test_skips_if_pid_negative(self):
        with patch("monitor.snc.os.kill") as mock_kill:
            _aislar_bucle(-1, "test", 50.0)
            mock_kill.assert_not_called()

    def test_skips_if_already_pending(self):
        _pending_sigcont[42] = "python3"
        with patch("monitor.snc.os.kill") as mock_kill:
            _aislar_bucle(42, "python3", 95.0)
            mock_kill.assert_not_called()

    def test_sends_sigstop_and_schedules_timer(self):
        _pending_sigcont.clear()
        with patch("monitor.snc.os.kill") as mock_kill, patch("monitor.snc.threading.Timer") as mock_timer:
            with patch("monitor.snc.Path.mkdir"):
                with patch("monitor.snc.Path.write_text"):
                    _aislar_bucle(42, "python3", 95.0)
                    mock_kill.assert_called_once_with(42, signal.SIGSTOP)
                    mock_timer.assert_called_once_with(
                        _BUCLE_TIMEOUT,
                        _sigcont_seguro,
                        args=[42, "python3"],
                    )

    def test_adds_to_pending(self):
        _pending_sigcont.clear()
        with patch("monitor.snc.os.kill"), patch("monitor.snc.threading.Timer"):
            with patch("monitor.snc.Path.mkdir"):
                with patch("monitor.snc.Path.write_text"):
                    _aislar_bucle(42, "python3", 95.0)
                    assert _pending_sigcont[42] == "python3"


class TestSigcontSeguro:
    def setup_method(self):
        _pending_sigcont.clear()

    def test_sigcont_if_stopped_and_same_name(self, tmp_path):
        _pending_sigcont[42] = "python3"
        fake_status = tmp_path / "status"
        fake_status.write_text("Name:\tpython3\nState:\tT (stopped)\n")
        with patch("pathlib.Path.exists", return_value=True):
            with patch("pathlib.Path.read_text", return_value=fake_status.read_text()):
                with patch("os.kill") as mock_kill:
                    _sigcont_seguro(42, "python3")
                    mock_kill.assert_called_once_with(42, signal.SIGCONT)
                    assert 42 not in _pending_sigcont

    def test_skips_if_pid_gone(self):
        _pending_sigcont[42] = "python3"
        with patch("pathlib.Path.exists", return_value=False), patch("os.kill") as mock_kill:
            _sigcont_seguro(42, "python3")
            mock_kill.assert_not_called()
            assert 42 not in _pending_sigcont

    def test_skips_if_process_recycled(self, tmp_path):
        _pending_sigcont[42] = "python3"
        fake_status = tmp_path / "status"
        fake_status.write_text("Name:\tpython2\nState:\tT (stopped)\n")
        with patch("pathlib.Path.exists", return_value=True):
            with patch("pathlib.Path.read_text", return_value=fake_status.read_text()):
                with patch("os.kill") as mock_kill:
                    _sigcont_seguro(42, "python3")
                    mock_kill.assert_not_called()
                    assert 42 not in _pending_sigcont

    def test_skips_if_not_stopped(self, tmp_path):
        _pending_sigcont[42] = "python3"
        fake_status = tmp_path / "status"
        fake_status.write_text("Name:\tpython3\nState:\tS (sleeping)\n")
        with patch("pathlib.Path.exists", return_value=True):
            with patch("pathlib.Path.read_text", return_value=fake_status.read_text()):
                with patch("os.kill") as mock_kill:
                    _sigcont_seguro(42, "python3")
                    mock_kill.assert_not_called()
                    assert 42 not in _pending_sigcont


class TestCheckOpenCodeColgado:
    def test_returns_none_when_not_running(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.stdout = ""
            result = check_opencode_colgado()
            assert result is None

    def test_returns_pid_when_cpu_high(self):
        with patch("subprocess.run") as mock_run:

            def side_effect(*args, **kwargs):
                result = MagicMock()
                args_list = args[0]
                if "pgrep" in args_list:
                    result.stdout = "1234\n"
                elif "ps" in args_list:
                    result.stdout = "95.0\n"
                return result

            mock_run.side_effect = side_effect
            result = check_opencode_colgado()
            assert result == 1234

    def test_returns_none_when_cpu_low(self):
        with patch("subprocess.run") as mock_run:

            def side_effect(*args, **kwargs):
                result = MagicMock()
                args_list = args[0]
                if "pgrep" in args_list:
                    result.stdout = "1234\n"
                elif "ps" in args_list:
                    result.stdout = "5.0\n"
                return result

            mock_run.side_effect = side_effect
            result = check_opencode_colgado()
            assert result is None


class TestCheckUmbrales:
    def test_false_when_all_ok(self):
        state = {
            "services": {
                "ollama": {"ok": True},
                "ura-openclaw": {"ok": True},
                "qdrant": {"ok": True},
                "model-router": {"ok": True},
                "tailscaled": {"ok": True},
            },
        }
        assert _check_umbrales(state) is False

    def test_true_when_2_criticos_fallan(self):
        state = {
            "services": {
                "ollama": {"ok": False},
                "ura-openclaw": {"ok": False},
                "qdrant": {"ok": True},
                "model-router": {"ok": True},
                "tailscaled": {"ok": True},
                "some-other": {"ok": True},
            },
        }
        assert _check_umbrales(state) is True

    def test_true_when_4_totales_fallan(self):
        state = {
            "services": {
                "ollama": {"ok": True},
                "ura-openclaw": {"ok": True},
                "qdrant": {"ok": True},
                "model-router": {"ok": True},
                "tailscaled": {"ok": True},
                "s1": {"ok": False},
                "s2": {"ok": False},
                "s3": {"ok": False},
                "s4": {"ok": False},
            },
        }
        assert _check_umbrales(state) is True

    def test_false_when_1_critico_and_2_totales(self):
        state = {
            "services": {
                "ollama": {"ok": False},
                "ura-openclaw": {"ok": True},
                "qdrant": {"ok": True},
                "model-router": {"ok": True},
                "tailscaled": {"ok": True},
                "s1": {"ok": False},
                "s2": {"ok": False},
            },
        }
        assert _check_umbrales(state) is False


class TestCPUSDetectionDisabled:
    def test_flag_is_false(self):
        assert _CPU_DETECTION_ENABLED is False
