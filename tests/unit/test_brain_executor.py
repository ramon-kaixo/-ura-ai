"""Tests for motor/brain/executor.py (ProposalExecutor)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from motor.brain.executor import ProposalExecutor


class TestToTuneladoraTask:
    def test_mapping_tipos(self) -> None:
        casos = [
            ({"type": "refactor"}, "code_quality"),
            ({"type": "split"}, "refactor"),
            ({"type": "test"}, "testing"),
            ({"type": "doc"}, "documentation"),
            ({"type": "otro"}, "generic"),
        ]
        for proposal, plugin in casos:
            r = ProposalExecutor.to_tuneladora_task(proposal)
            assert r["plugin"] == plugin

    def test_campos_default(self) -> None:
        r = ProposalExecutor.to_tuneladora_task({"type": "refactor", "target": "a.py", "priority": "high"})
        assert r["target"] == "a.py"
        assert r["priority"] == "high"
        assert r["params"] == {"type": "refactor", "target": "a.py", "priority": "high"}


class TestProposalToArgs:
    def test_maneja_tipos(self) -> None:
        p = {
            "type": "refactor",
            "target": "mod.py",
            "priority": "high",
            "flag": True,
            "no_flag": False,
            "lista": ["a", "b"],
            "num": 3,
            "texto": "hola",
            "nulo": None,
        }
        args = ProposalExecutor._proposal_to_args(p)
        assert "--target=mod.py" in args
        assert "--priority=high" in args
        assert "--flag" in args
        assert "--no_flag" not in args
        assert "--lista=a" in args and "--lista=b" in args
        assert "--num=3" in args
        assert "--texto=hola" in args
        assert "--nulo" not in args


class TestGetEngine:
    def test_engine_cargado(self) -> None:
        fake = MagicMock()
        fake_engine_mod = MagicMock()
        fake_engine_mod.PipelineEngine.return_value = fake
        import sys

        with patch.dict(sys.modules, {"scripts.pro.tuneladora.engine": fake_engine_mod}):
            ex = ProposalExecutor()
            assert ex._get_engine() == fake
        assert ex._engine == fake

    def test_engine_import_error(self) -> None:
        import sys

        with patch.dict(sys.modules, {"scripts.pro.tuneladora.engine": None}):
            ex = ProposalExecutor()
            assert ex._get_engine() is None


class TestExecute:
    def _fake_result(self, returncode: int = 0) -> MagicMock:
        r = MagicMock()
        r.returncode = returncode
        r.stdout = "out"
        r.stderr = "err"
        return r

    def test_engine_none(self) -> None:
        ex = ProposalExecutor()
        with patch.object(ex, "_get_engine", return_value=None):
            r = ex.execute({"type": "refactor"})
        assert "error" in r

    def test_exito(self) -> None:
        ex = ProposalExecutor()
        engine = MagicMock()
        engine.run_script.return_value = self._fake_result(0)
        with patch.object(ex, "_get_engine", return_value=engine):
            r = ex.execute({"type": "refactor", "target": "a.py"})
        assert r["status"] == "success"
        assert r["returncode"] == 0
        engine.run_script.assert_called_once()

    def test_fallo_returncode(self) -> None:
        ex = ProposalExecutor()
        engine = MagicMock()
        engine.run_script.return_value = self._fake_result(3)
        with patch.object(ex, "_get_engine", return_value=engine):
            r = ex.execute({"type": "test"})
        assert r["status"] == "failed"
        assert r["returncode"] == 3

    def test_excepcion(self) -> None:
        ex = ProposalExecutor()
        engine = MagicMock()
        engine.run_script.side_effect = RuntimeError("boom")
        with patch.object(ex, "_get_engine", return_value=engine):
            r = ex.execute({"type": "doc"})
        assert r["status"] == "error"
        assert "boom" in r["error"]
