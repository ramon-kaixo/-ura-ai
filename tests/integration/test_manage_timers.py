"""Tests para scripts/pro/manage_timers.py (Módulo 7)."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "scripts" / "pro"))

from manage_timers import (
    TIMERS,
    _frecuencia_on_calendar,
    generar_unidades,
)


class TestTimers:
    def test_8_timers_configurados(self) -> None:
        assert len(TIMERS) == 9

    def test_frecuencia_on_calendar(self) -> None:
        assert _frecuencia_on_calendar("daily") == "*-*-* 04:00:00"
        assert _frecuencia_on_calendar("weekly") == "*-*-* 05:00:00"
        assert _frecuencia_on_calendar("monthly") == "*-*-01 06:00:00"
        assert _frecuencia_on_calendar("6h") == "*:0/6"
        assert _frecuencia_on_calendar("desconocida") == "*-*-* 04:00:00"

    def test_generar_unidades(self, tmp_path: Path) -> None:

        with mock.patch("manage_timers.UNITS_DIR", tmp_path / "timers"):
            generados = generar_unidades(verbose=False)
        # 8 timers * 2 archivos (timer + service)
        assert len(generados) == 16
        timer_files = list((tmp_path / "timers").glob("*.timer"))
        service_files = list((tmp_path / "timers").glob("*.service"))
        assert len(timer_files) == 8
        assert len(service_files) == 8
        # Verificar contenido
        fix = (tmp_path / "timers" / "ura-fix.timer").read_text()
        assert "OnCalendar" in fix
        service = (tmp_path / "timers" / "ura-fix.service").read_text()
        assert "sanear_codigo.py" in service
        assert "Type=oneshot" in service


class TestFuncionesComando:
    def test_status(self) -> None:
        from manage_timers import status

        with mock.patch("subprocess.run", return_value=mock.Mock(stdout="active", stderr="")):
            assert status() == 0

    def test_install_sin_sudo(self) -> None:
        from manage_timers import install

        with mock.patch("manage_timers._run", return_value=1) as m_run:
            rc = install()
        assert rc == 1
        m_run.assert_called()

    def test_install_con_sudo(self, tmp_path: Path) -> None:
        from manage_timers import install

        with mock.patch("manage_timers.UNITS_DIR", tmp_path / "timers"):
            tmp_path.joinpath("timers").mkdir()
            with mock.patch("manage_timers._run", return_value=0):
                rc = install()
        assert rc == 0

    def test_start_stop(self) -> None:
        from manage_timers import start, stop

        with mock.patch("manage_timers._run", return_value=0):
            assert start() == 0
            assert stop() == 0

    def test_main_sin_args(self) -> None:
        from manage_timers import main

        with mock.patch("sys.argv", ["manage_timers.py"]):
            assert main() == 1

    def test_main_generate(self) -> None:
        from manage_timers import main

        with mock.patch("sys.argv", ["manage_timers.py", "generate"]), mock.patch("manage_timers.generar_unidades"):
            assert main() == 0
