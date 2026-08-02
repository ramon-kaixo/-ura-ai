"""Tests para core/agents/ejecutor.py — AgenteEjecutor."""
from __future__ import annotations

from unittest import mock

from core.agents.ejecutor import AgenteEjecutor


class TestAgenteEjecutor:
    def test_modelo_constante(self) -> None:
        assert AgenteEjecutor.MODELO is not None

    def test_ejecutar_ok(self, monkeypatch) -> None:
        proc = mock.Mock()
        proc.communicate.return_value = ("linea\n✅ OK\n✅ OK\n❌ Error\n", None)
        proc.poll.return_value = 0
        popen = mock.Mock(return_value=proc)
        monkeypatch.setattr("core.agents.ejecutor.subprocess.Popen", popen)
        monkeypatch.setattr("core.agents.ejecutor.os.environ", {"PATH": "/usr/bin"})
        monkeypatch.setattr("core.config_manager.get_ollama_url", mock.Mock(return_value="http://x:11434"))

        agente = AgenteEjecutor()
        r = agente.ejecutar(workers=1, timeout=30)
        assert r["ok"] == 2
        assert r["err"] == 1
        assert len(r["workers"]) == 1
        assert r["workers"][0]["ok"] == 2
        # env de worker
        env = popen.call_args.kwargs["env"]
        assert env["REFACTOR_WORKER_ID"] == "0"
        assert env["REFACTOR_WORKER_TOTAL"] == "1"
        assert env["MIN_LINES"] == "80"
        assert "OLLAMA_URL" in env

    def test_ejecutar_timeout(self, monkeypatch) -> None:
        proc = mock.Mock()
        proc.communicate.side_effect = __import__("subprocess").TimeoutExpired("cmd", 30)
        proc.poll.return_value = None
        monkeypatch.setattr("core.agents.ejecutor.subprocess.Popen", mock.Mock(return_value=proc))
        monkeypatch.setattr("core.agents.ejecutor.os.environ", {"PATH": "/usr/bin"})
        monkeypatch.setattr("core.config_manager.get_ollama_url", mock.Mock(return_value="http://x"))

        agente = AgenteEjecutor()
        r = agente.ejecutar(workers=1, timeout=5)
        assert r["workers"][0]["timeout"] is True
        assert r["workers"][0]["err"] == 1
        proc.kill.assert_called()

    def test_ejecutar_terminate_error(self, monkeypatch) -> None:
        proc = mock.Mock()
        proc.communicate.return_value = ("", None)
        proc.poll.return_value = None  # sigue vivo
        proc.terminate.side_effect = OSError("no puedo")
        proc.wait.side_effect = OSError("no espera")
        proc.kill.return_value = None
        monkeypatch.setattr("core.agents.ejecutor.subprocess.Popen", mock.Mock(return_value=proc))
        monkeypatch.setattr("core.agents.ejecutor.os.environ", {"PATH": "/usr/bin"})
        monkeypatch.setattr("core.config_manager.get_ollama_url", mock.Mock(return_value="http://x"))

        agente = AgenteEjecutor()
        r = agente.ejecutar(workers=1, timeout=30)
        assert r["ok"] == 0
        proc.kill.assert_called()

    def test_ejecutar_multi_worker(self, monkeypatch) -> None:
        procs = []
        for i in range(2):
            p = mock.Mock()
            p.communicate.return_value = (f"✅ OK {i}", None)
            p.poll.return_value = 0
            procs.append(p)
        monkeypatch.setattr("core.agents.ejecutor.subprocess.Popen", mock.Mock(side_effect=procs))
        monkeypatch.setattr("core.agents.ejecutor.os.environ", {"PATH": "/usr/bin"})
        monkeypatch.setattr("core.config_manager.get_ollama_url", mock.Mock(return_value="http://x"))

        agente = AgenteEjecutor()
        r = agente.ejecutar(workers=2, timeout=30)
        assert r["ok"] == 2
        assert len(r["workers"]) == 2
        assert r["workers"][0]["id"] == 1
        assert r["workers"][1]["id"] == 2
