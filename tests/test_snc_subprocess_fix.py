"""Tests para verificar que las 5 rutas de subprocess reparadas en monitor/snc.py
funcionan correctamente: Popen, PKILL, ps aux, pgrep, ps -p.

snc.py tiene efectos secundario en import (mkdir ~/.ura/run). Parcheamos Path.mkdir
antes de importar para evitar OSError en entornos read-only.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

# snc.py usa import local del directorio monitor/
import sys

_monitor_dir = str(Path(__file__).resolve().parent.parent / "monitor")
if _monitor_dir not in sys.path:
    sys.path.insert(0, _monitor_dir)

# Parcheamos Path.mkdir y Path.chmod antes de importar snc (efectos secundario en módulo)
_original_mkdir = Path.mkdir
_original_chmod = Path.chmod
Path.mkdir = lambda self, **kw: None
Path.chmod = lambda self, *a: None

from monitor.snc import (
    check_bucle_cpu,
    check_opencode_colgado,
)

# Restauramos
Path.mkdir = _original_mkdir
Path.chmod = _original_chmod


class TestCheckBucleCpu:
    """Ejercita la llamada subprocess.run(['ps', 'aux', ...]) línea 415."""

    def test_returns_list_with_mocked_ps(self):
        fake_ps = (
            "USER         PID %CPU %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND\n"
            "root        1234 95.0  1.0 12345 6789 pts/0    R+   10:00   1:23 python3\n"
        )
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.stdout = fake_ps
            mock_run.return_value.returncode = 0
            result = check_bucle_cpu(umbral=50.0)
            assert len(result) == 1
            assert result[0][0] == 1234

    def test_empty_when_no_matching_processes(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.stdout = "USER PID %CPU COMM\n"
            mock_run.return_value.returncode = 0
            result = check_bucle_cpu(umbral=50.0)
            assert result == []


class TestCheckOpencodeColgado:
    """Ejercita llamadas subprocess.run(['pgrep', ...]) línea 449
    y subprocess.run(['ps', '-p', ...]) línea 459."""

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
                if "pgrep" in str(args_list):
                    result.stdout = "1234\n"
                elif "ps" in str(args_list):
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
                if "pgrep" in str(args_list):
                    result.stdout = "1234\n"
                elif "ps" in str(args_list):
                    result.stdout = "5.0\n"
                return result

            mock_run.side_effect = side_effect
            result = check_opencode_colgado()
            assert result is None
