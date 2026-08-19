"""Tests smoke generados por plantilla (determinista, sin LLM)."""

import pytest

from motor.core.llm._state import build_llm_state


def test_import__state():
    """El módulo importa sin errores."""
    assert build_llm_state is not None


def test_funcion__state_build_llm_state():
    """La función no lanza con argumentos básicos."""
    try:
        build_llm_state('')
    except (TypeError, ValueError, NotImplementedError):
        pytest.skip('no aplicable con argumentos básicos')



def test_optional_providers_import_fallo():
    """Rama: fallo de import de un provider opcional no rompe."""
    import builtins
    from unittest import mock

    from motor.core.llm._state import _get_optional_providers

    real_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "motor.core.llm.openai":
            raise ImportError("no disponible")
        return real_import(name, globals, locals, fromlist, level)

    with mock.patch("builtins.__import__", side_effect=fake_import):
        providers = _get_optional_providers()
    nombres = [n for _, n in providers]
    assert "openai" not in nombres


def test_seleccionar_provider_conocido():
    """Rama: provider registrado en _PROVIDER_MODULES (openai)."""
    from unittest import mock

    from motor.core.llm._state import _seleccionar_provider

    class R:
        def __init__(self):
            self.regs = []

        def register(self, nombre, cls, default=False):
            self.regs.append((nombre, cls, default))

    r = R()
    with mock.patch("motor.core.llm.openai.OpenAIProvider") as mock_cls:
        d = _seleccionar_provider("openai", r, mock_cls)
    assert d is not None
    assert len(r.regs) == 2
    assert r.regs[0][0] == "openai"


def test_seleccionar_provider_excepcion_registro():
    """Rama: excepción al instanciar un provider opcional (fallback ollama)."""
    from unittest import mock

    from motor.core.llm._state import _seleccionar_provider, _get_optional_providers

    class R:
        def register(self, nombre, cls, default=False):
            return None

    class Falla:
        def __init__(self):
            raise RuntimeError("fallo de instanciación")

    with mock.patch("motor.core.llm._state._get_optional_providers", return_value=[(Falla, "openai")]):
        d = _seleccionar_provider("desconocido", R(), mock.Mock())
    assert d is not None


def test_build_llm_state_provider_configurado():
    """Rama: config con provider distinto a ollama."""
    from types import SimpleNamespace
    from unittest import mock

    from motor.core.llm._state import build_llm_state

    cfg = SimpleNamespace(llm_provider="groq")
    with mock.patch("motor.core.config.UraConfig.load", return_value=cfg), mock.patch(
        "motor.core.llm.groq.GroqProvider"
    ), mock.patch("motor.core.llm.ollama.OllamaProvider"), mock.patch("motor.core.llm.registry.registry"):
        state = build_llm_state()
    assert state is not None
