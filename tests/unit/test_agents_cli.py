"""Tests para core/agents/cli.py — entry point multi-agente."""
from __future__ import annotations

from unittest import mock

import pytest


class TestAgentsCli:
    def test_modo_ciclo(self, monkeypatch) -> None:
        from core.agents import cli

        loop = mock.Mock()
        monkeypatch.setattr("core.agents.cli.SelfHealingLoop", mock.Mock(return_value=loop))
        monkeypatch.setattr("sys.argv", ["agents_cli.py", "--modo", "ciclo"])
        cli.main()
        loop.ejecutar.assert_called_once()

    def test_modo_ciclo_json(self, monkeypatch) -> None:
        from core.agents import cli

        loop = mock.Mock()
        monkeypatch.setattr("core.agents.cli.SelfHealingLoop", mock.Mock(return_value=loop))
        monkeypatch.setattr("sys.argv", ["agents_cli.py", "--modo", "ciclo", "--json"])
        cli.main()
        loop.ejecutar.assert_called_once()

    def test_modo_orquestar(self, monkeypatch) -> None:
        from core.agents import cli

        tele = mock.Mock()
        tele.reporte_completo.return_value = {"hardware": {"ram_pct": 50}}
        monkeypatch.setattr("core.agents.cli.Telemetria", mock.Mock(return_value=tele))
        monkeypatch.setattr("core.agents.cli.Conciencia", mock.Mock(leer=lambda: {}))
        orq = mock.Mock()
        orq.decidir.return_value = ("ESPERAR", "estable")
        monkeypatch.setattr("core.agents.cli.AgenteOrquestador", mock.Mock(return_value=orq))
        monkeypatch.setattr("sys.argv", ["agents_cli.py", "--modo", "orquestar"])
        cli.main()
        orq.decidir.assert_called_once()

    def test_modo_reparar_ok(self, monkeypatch) -> None:
        from core.agents import cli

        loop = mock.Mock()
        monkeypatch.setattr("core.agents.cli.SelfHealingLoop", mock.Mock(return_value=loop))
        reparador = mock.Mock()
        reparador.reparar.return_value = (True, 1, "ok")
        monkeypatch.setattr("core.agents.cli.AgenteReparador", mock.Mock(return_value=reparador))
        exit_codes = []

        def _exit(code):
            exit_codes.append(code)
            raise SystemExit(code)

        monkeypatch.setattr("core.agents.cli.sys.exit", _exit)
        monkeypatch.setattr("sys.argv", ["agents_cli.py", "--modo", "reparar", "--archivo", "x.py"])
        with pytest.raises(SystemExit) as e:
            cli.main()
        assert e.value.code == 0

    def test_modo_reparar_falla(self, monkeypatch) -> None:
        from core.agents import cli

        loop = mock.Mock()
        monkeypatch.setattr("core.agents.cli.SelfHealingLoop", mock.Mock(return_value=loop))
        reparador = mock.Mock()
        reparador.reparar.return_value = (False, 2, "no")
        monkeypatch.setattr("core.agents.cli.AgenteReparador", mock.Mock(return_value=reparador))
        def _exit(code):
            raise SystemExit(code)

        monkeypatch.setattr("core.agents.cli.sys.exit", _exit)
        monkeypatch.setattr("sys.argv", ["agents_cli.py", "--modo", "reparar", "--archivo", "x.py"])
        with pytest.raises(SystemExit) as e:
            cli.main()
        assert e.value.code == 1

    def test_modo_reparar_json(self, monkeypatch) -> None:
        from core.agents import cli

        loop = mock.Mock()
        monkeypatch.setattr("core.agents.cli.SelfHealingLoop", mock.Mock(return_value=loop))
        reparador = mock.Mock()
        reparador.reparar.return_value = (True, 3, "ok")
        monkeypatch.setattr("core.agents.cli.AgenteReparador", mock.Mock(return_value=reparador))
        def _exit(code):
            raise SystemExit(code)

        monkeypatch.setattr("core.agents.cli.sys.exit", _exit)
        monkeypatch.setattr("sys.argv", ["agents_cli.py", "--modo", "reparar", "--archivo", "x.py", "--json"])
        with pytest.raises(SystemExit) as e:
            cli.main()
        assert e.value.code == 0
