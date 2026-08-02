"""Tests for core/agents/cli.py."""

from unittest.mock import MagicMock, patch

import pytest

from core.agents.cli import main


class TestMain:
    @patch("core.agents.cli.SelfHealingLoop")
    def test_modo_ciclo(self, mock_loop_cls, monkeypatch):
        mock_loop = MagicMock()
        mock_loop_cls.return_value = mock_loop
        monkeypatch.setattr("sys.argv", ["cli.py"])
        main()
        mock_loop.ejecutar.assert_called_once()

    @patch("core.agents.cli.SelfHealingLoop")
    def test_modo_ciclo_json(self, mock_loop_cls, monkeypatch):
        mock_loop = MagicMock()
        mock_loop_cls.return_value = mock_loop
        monkeypatch.setattr("sys.argv", ["cli.py", "--modo", "ciclo", "--json"])
        main()
        mock_loop.ejecutar.assert_called_once()

    @patch("core.agents.cli.AgenteReparador")
    @patch("core.agents.cli.SelfHealingLoop")
    def test_modo_reparar(self, mock_loop_cls, mock_rep_cls, monkeypatch):
        mock_rep = MagicMock()
        mock_rep.reparar.return_value = (True, 1, "ok")
        mock_rep_cls.return_value = mock_rep
        monkeypatch.setattr("sys.argv", ["cli.py", "--modo", "reparar", "--archivo", "/tmp/test.py"])
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 0
        mock_rep.reparar.assert_called_once_with("/tmp/test.py", [])

    @patch("core.agents.cli.AgenteReparador")
    @patch("core.agents.cli.SelfHealingLoop")
    def test_modo_reparar_falla(self, mock_loop_cls, mock_rep_cls, monkeypatch):
        mock_rep = MagicMock()
        mock_rep.reparar.return_value = (False, 0, "fail")
        mock_rep_cls.return_value = mock_rep
        monkeypatch.setattr("sys.argv", ["cli.py", "--modo", "reparar", "--archivo", "/tmp/test.py"])
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 1

    @patch("core.agents.cli.AgenteOrquestador")
    @patch("core.agents.cli.Conciencia")
    @patch("core.agents.cli.Telemetria")
    @patch("core.agents.cli.SelfHealingLoop")
    def test_modo_orquestar(self, mock_loop, mock_tel_cls, mock_conc, mock_orq_cls, monkeypatch):
        mock_tel = MagicMock()
        mock_tel.reporte_completo.return_value = {"ram": 1000}
        mock_tel_cls.return_value = mock_tel
        mock_conc.leer.return_value = {"estado": "ok"}
        mock_orq = MagicMock()
        mock_orq.decidir.return_value = ("ESPERAR", "todo ok")
        mock_orq_cls.return_value = mock_orq
        monkeypatch.setattr("sys.argv", ["cli.py", "--modo", "orquestar"])
        main()
        mock_orq.decidir.assert_called_once()
