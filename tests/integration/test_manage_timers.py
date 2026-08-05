"""Tests para scripts/pro/manage_timers.py (Módulo 7)."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "scripts" / "pro"))

from manage_timers import (  # noqa: E402
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
        assert _frecuencia_on_calendar("6h") == "*-*-* *:00/6:00:00"
        assert _frecuencia_on_calendar("desconocida") == "*-*-* 04:00:00"

    def test_generar_unidades(self, tmp_path: Path) -> None:
        from manage_timers import UNITS_DIR

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
