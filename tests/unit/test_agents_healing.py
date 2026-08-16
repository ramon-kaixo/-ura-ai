"""Tests for core/agents/healing.py."""

from unittest.mock import patch

import pytest

from motor.core.agents.healing import SelfHealingLoop


class TestSelfHealingLoop:
    @pytest.fixture
    def loop(self):
        with patch("motor.core.agents.healing.AgenteOrquestador") as mock_orq, \
             patch("motor.core.agents.healing.AgenteEjecutor") as mock_ej, \
             patch("motor.core.agents.healing.AgenteReparador") as mock_rep, \
             patch("motor.core.agents.healing.Telemetria") as mock_tel:
            mock_orq.return_value.decidir.return_value = ("REFACTORIZAR", "tests fallando")
            mock_ej.return_value.ejecutar.return_value = {"ok": True}
            mock_rep.return_value.reparar.return_value = (True, "info", "arreglado")
            mock_tel.return_value.reporte_completo.return_value = {"ram_libre_mb": 1000}
            mock_tel.return_value.f821_count.return_value = 0
            mock_tel.return_value.hardware.return_value = {"ram_libre_mb": 1000}
            yield SelfHealingLoop(), mock_orq, mock_ej, mock_rep, mock_tel

    def test_init(self, loop):
        sl, _, _, _, _ = loop
        assert sl._fallos_consecutivos == 0

    @patch("motor.core.agents.healing.Conciencia")
    @patch("motor.core.agents.healing.subprocess.run")
    def test_ejecutar_refactorizar(self, mock_subprocess, mock_conciencia, loop):
        sl, mock_orq, mock_ej, _, _mock_tel = loop
        mock_orq.return_value.decidir.return_value = ("REFACTORIZAR", "tests fallando")

        reporte = sl.ejecutar()

        assert reporte["accion"] == "REFACTORIZAR"
        assert reporte["refactor"] == {"ok": True}
        mock_ej.return_value.ejecutar.assert_called_once_with(workers=4)
        mock_conciencia.actualizar_proceso.assert_any_call("ejecutor", "activo")
        mock_conciencia.actualizar_proceso.assert_any_call("ejecutor", "idle")

    @patch("motor.core.agents.healing.Conciencia")
    @patch("motor.core.agents.healing.subprocess.run")
    def test_ejecutar_reparar(self, mock_subprocess, mock_conciencia, loop):
        sl, mock_orq, _, mock_rep, _ = loop
        mock_orq.return_value.decidir.return_value = ("REPARAR", "f821 detectado")
        mock_subprocess.return_value.stdout = '[{"filename": "test.py"}]'
        mock_subprocess.return_value.returncode = 0

        reporte = sl.ejecutar()

        assert reporte["accion"] == "REPARAR"
        pasos = [p for p in reporte["pasos"] if p.get("paso") == "reparar"]
        assert len(pasos) > 0
        mock_rep.return_value.reparar.assert_called()

    @patch("motor.core.agents.healing.Conciencia")
    @patch("motor.core.agents.healing.time.sleep", return_value=None)
    @patch("motor.core.agents.healing.subprocess.run")
    def test_ejecutar_pausar(self, mock_subprocess, mock_sleep, mock_conciencia, loop):
        sl, mock_orq, _, _, _ = loop
        mock_orq.return_value.decidir.return_value = ("PAUSAR", "RAM saturada")

        reporte = sl.ejecutar()

        assert reporte["accion"] == "PAUSAR"
        mock_sleep.assert_called_once_with(30)

    @patch("motor.core.agents.healing.Conciencia")
    @patch("motor.core.agents.healing.subprocess.run")
    @pytest.mark.slow
    def test_timeout(self, mock_subprocess, mock_conciencia, loop):
        sl, mock_orq, _, _, _ = loop
        mock_orq.return_value.decidir.return_value = ("PAUSAR", "RAM saturada")

        with patch("motor.core.agents.healing.time.monotonic", side_effect=[0, 9999]):
            reporte = sl.ejecutar()

        assert reporte["resultado"] == "TIMEOUT"
        assert sl._fallos_consecutivos == 1

    @patch("motor.core.agents.healing.Conciencia")
    @patch("motor.core.agents.healing.subprocess.run")
    def test_fallos_consecutivos_reset(self, mock_subprocess, mock_conciencia, loop):
        sl, mock_orq, _, _, _ = loop
        mock_orq.return_value.decidir.return_value = ("REFACTORIZAR", "ok")

        sl._fallos_consecutivos = 5
        sl.ejecutar()

        assert sl._fallos_consecutivos == 0

    @patch("motor.core.agents.healing.Conciencia")
    @patch("motor.core.agents.healing.subprocess.run")
    def test_escanear_f821_filtra_venv(self, mock_subprocess, mock_conciencia, loop):
        sl, _, _, _, _ = loop
        mock_subprocess.return_value.stdout = (
            '[{"filename": "src/a.py"}, {"filename": "/home/x/.venv/lib/b.py"}, {"filename": "src/c.py"}]'
        )
        files = sl._escanear_f821()
        assert files == {"src/a.py", "src/c.py"}
        assert all("/.venv/" not in f for f in files)

    @patch("motor.core.agents.healing.Conciencia")
    @patch("motor.core.agents.healing.subprocess.run")
    def test_escanear_f821_json_vacio(self, mock_subprocess, mock_conciencia, loop):
        sl, _, _, _, _ = loop
        mock_subprocess.return_value.stdout = "[]"
        assert sl._escanear_f821() == set()

    @patch("motor.core.agents.healing.Conciencia")
    @patch("motor.core.agents.healing.subprocess.run")
    def test_cerrar_reporte_detalle(self, mock_subprocess, mock_conciencia, loop):
        sl, mock_orq, _, _, mock_tel = loop
        mock_orq.return_value.decidir.return_value = ("REFACTORIZAR", "ok")
        mock_tel.return_value.f821_count.return_value = 3
        mock_tel.return_value.hardware.return_value = {"ram_libre_mb": 777}

        reporte = sl.ejecutar()

        assert reporte["f821_final"] == 3
        assert reporte["ram_final_mb"] == 777
        assert "tiempo_total_s" in reporte
        assert reporte["timestamp"]

    @patch("motor.core.agents.healing.Conciencia")
    @patch("motor.core.agents.healing.subprocess.run")
    def test_cerrar_reporte_rollback_suma_fallo(self, mock_subprocess, mock_conciencia, loop):
        sl, mock_orq, _, _, _ = loop
        mock_orq.return_value.decidir.return_value = ("REFACTORIZAR", "ok")
        sl._fallos_consecutivos = 2
        sl._cerrar_reporte({"resultado": "ROLLBACK"}, 0.0, 0)
        assert sl._fallos_consecutivos == 3
