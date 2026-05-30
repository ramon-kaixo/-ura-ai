"""Tests for core: ura_identity, react_engine, action_signer, technical_director, auto_repair_cycle, failure_consciousness, observability."""

import logging


logging.disable(logging.CRITICAL)


class TestUraIdentity:
    def test_imports(self):
        from core.ura_identity import get_system_prompt

        assert callable(get_system_prompt)


class TestReactEngine:
    def test_imports(self):
        from core.react_engine import ReActEngine

        assert ReActEngine is not None

    def test_instantiates(self):
        from core.react_engine import ReActEngine

        engine = ReActEngine()
        assert hasattr(engine, "run")
        assert hasattr(engine, "think")


class TestActionSigner:
    def test_imports(self):
        from core.action_signer import autorizar_accion

        assert callable(autorizar_accion)


class TestTechnicalDirector:
    def test_imports(self):
        from core.technical_director import get_technical_director

        assert callable(get_technical_director)


class TestFailureConsciousness:
    def test_imports(self):
        from core.failure_consciousness import FailureConsciousness

        assert FailureConsciousness is not None


class TestObservability:
    def test_imports(self):
        from core.observability import Observability

        assert Observability is not None
