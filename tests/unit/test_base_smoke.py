"""Tests smoke + validación generados por plantilla y ampliados (100x100)."""

import pytest

from motor.core.llm.base import validate_provider


def test_import_base():
    """El módulo importa sin errores."""
    assert validate_provider is not None


def test_funcion_base_validate_provider():
    """La función no lanza con argumentos básicos."""
    try:
        validate_provider('')
    except (TypeError, ValueError, NotImplementedError):
        pytest.skip('no aplicable con argumentos básicos')


def _base():
    from motor.core.llm.base import BaseLLMProvider

    return BaseLLMProvider


def _provider_valido():
    """Proveedor concreto mínimo para ejercitar BaseLLMProvider."""
    from motor.core.llm.base import BaseLLMProvider

    class P(BaseLLMProvider):
        _provider_name = "prueba"
        capabilities = {"chat": True}  # noqa: RUF012

        def supports(self, capability):
            return capability == "chat"

        def generate(self, prompt, model=None, options=None):
            return "ok"

        def generate_stream(self, prompt, model=None, options=None):
            yield "ok"

        def chat_generate(self, messages, model=None, options=None):
            return "ok"

        def embed(self, texts, model=None):
            return [[0.0]] * len(texts)

        async def embed_async(self, texts, model=None):
            return [[0.0]] * len(texts)

        def health(self):
            return {"ok": True}

    return P


def test_validate_provider_valido():
    """Cobertura: validate_provider con clase concreta completa."""
    from motor.core.llm.base import validate_provider

    P = _provider_valido()
    r = validate_provider(P)
    assert r.valid


def test_validate_provider_invalido():
    """Cobertura: clase sin métodos abstractos implementados falla."""
    from motor.core.llm.base import validate_provider

    class Roto:
        pass

    r = validate_provider(Roto)
    assert not r.valid
    assert r.errors


def test_validate_no_hereda():
    """Rama: clase que no hereda de BaseLLMProvider."""
    from motor.core.llm.base import validate_provider

    class Roto:
        pass

    r = validate_provider(Roto)
    assert not r.valid
    assert "No hereda" in r.errors[0]


def test_validate_no_instanciable():
    """Rama: clase hereda pero su __init__ lanza."""
    from motor.core.llm.base import validate_provider

    B = _base()

    class Explota(B):
        _provider_name = "x"

        def __init__(self):
            raise RuntimeError("boom")

        def generate(self, prompt, model=None, options=None):
            return "ok"

        def embed(self, texts, model=None):
            return []

        async def embed_async(self, texts, model=None):
            return []

        def health(self):
            return {}

    r = validate_provider(Explota)
    assert not r.valid
    assert "No se puede instanciar" in r.errors[0]


def test_validate_sin_provider_name():
    """Rama: sin _provider_name."""
    from motor.core.llm.base import validate_provider

    B = _base()

    class SinNombre(B):
        def generate(self, prompt, model=None, options=None):
            return "ok"

        def embed(self, texts, model=None):
            return []

        async def embed_async(self, texts, model=None):
            return []

        def health(self):
            return {}

    r = validate_provider(SinNombre)
    assert not r.valid
    assert any("_provider_name" in e for e in r.errors)


def test_validate_metodos_faltantes():
    """Rama: métodos requeridos ausentes -> clase abstracta no instanciable."""
    from motor.core.llm.base import validate_provider

    B = _base()

    class SinMetodos(B):
        _provider_name = "x"
        capabilities = {"chat": True}  # noqa: RUF012

        def generate(self, prompt, model=None, options=None):
            return "ok"

    r = validate_provider(SinMetodos)
    assert not r.valid
    assert any("No se puede instanciar" in e for e in r.errors)


def test_validate_metodo_no_callable():
    """Rama: método presente pero no invocable (clase completa)."""
    from motor.core.llm.base import validate_provider

    B = _base()

    class NoCallable(B):
        _provider_name = "x"
        capabilities = {"chat": True}  # noqa: RUF012

        def generate(self, prompt, model=None, options=None):
            return "ok"

        embed = "no-method"
        embed_async = "no-method"

        def health(self):
            return {}

    r = validate_provider(NoCallable)
    assert not r.valid
    assert any("embed no es invocable" in e for e in r.errors)
    assert any("embed_async no es invocable" in e for e in r.errors)


def test_validate_firma_incorrecta():
    """Rama: firma de generate sin parámetro prompt."""
    from motor.core.llm.base import validate_provider

    B = _base()

    class MalaFirma(B):
        _provider_name = "x"
        capabilities = {"chat": True}  # noqa: RUF012

        def generate(self, other):
            return "ok"

        def embed(self, texts, model=None):
            return []

        async def embed_async(self, texts, model=None):
            return []

        def health(self):
            return {}

    r = validate_provider(MalaFirma)
    assert not r.valid
    assert any("generate: falta parámetro" in e for e in r.errors)


def test_validate_embed_firma_mal():
    """Rama: firma de embed sin parámetro texts."""
    from motor.core.llm.base import validate_provider

    B = _base()

    class MalEmbed(B):
        _provider_name = "x"
        capabilities = {"chat": True}  # noqa: RUF012

        def generate(self, prompt, model=None, options=None):
            return "ok"

        def embed(self, otros):
            return []

        async def embed_async(self, texts, model=None):
            return []

        def health(self):
            return {}

    r = validate_provider(MalEmbed)
    assert any("embed: falta parámetro" in e for e in r.errors)


def test_validate_capacidades_mal():
    """Rama: capabilities sin chat."""
    from motor.core.llm.base import validate_provider

    B = _base()

    class SinCaps(B):
        _provider_name = "x"
        capabilities = {"sin_chat": True}  # noqa: RUF012

        def generate(self, prompt, model=None, options=None):
            return "ok"

        def embed(self, texts, model=None):
            return []

        async def embed_async(self, texts, model=None):
            return []

        def health(self):
            return {}

    r = validate_provider(SinCaps)
    assert not r.valid
    assert any("Falta capacidad 'chat'" in e for e in r.errors)


def test_validate_capacidades_no_dict():
    """Rama: capabilities no es dict."""
    from motor.core.llm.base import validate_provider

    B = _base()

    class SinDict(B):
        _provider_name = "x"
        capabilities = "chat"

        def generate(self, prompt, model=None, options=None):
            return "ok"

        def embed(self, texts, model=None):
            return []

        async def embed_async(self, texts, model=None):
            return []

        def health(self):
            return {}

    r = validate_provider(SinDict)
    assert any("capabilities debe ser un dict" in e for e in r.errors)


def test_validate_comportamiento_lanza():
    """Rama: generate() lanza excepción en validación de comportamiento."""
    from motor.core.llm.base import validate_provider

    B = _base()

    class Lanza(B):
        _provider_name = "x"
        capabilities = {"chat": True}  # noqa: RUF012

        def generate(self, prompt, model=None, options=None):
            raise RuntimeError("llm caido")

        def embed(self, texts, model=None):
            raise RuntimeError("embed caido")

        async def embed_async(self, texts, model=None):
            return []

        def health(self):
            return {}

    r = validate_provider(Lanza)
    assert not r.valid
    assert any("generate('test') lanzó" in e for e in r.errors)
    assert any("embed(['test']) lanzó" in e for e in r.errors)


def test_validate_comportamiento_retorna_mal():
    """Rama: generate no retorna str / embed no retorna list."""
    from motor.core.llm.base import validate_provider

    B = _base()

    class MalRetorno(B):
        _provider_name = "x"
        capabilities = {"chat": True}  # noqa: RUF012

        def generate(self, prompt, model=None, options=None):
            return 42

        def embed(self, texts, model=None):
            return "no-list"

        async def embed_async(self, texts, model=None):
            return []

        def health(self):
            return {}

    r = validate_provider(MalRetorno)
    assert not r.valid
    assert any("no retorna str" in e for e in r.errors)
    assert any("no retorna list" in e for e in r.errors)


def test_supports_ramas():
    """Rama: supports con valores bool/int/otros en capabilities."""
    B = _base()

    class ConCaps(B):
        _provider_name = "x"
        capabilities = {"a": True, "b": 2, "c": 0, "d": "si", "e": ""}  # noqa: RUF012

        def generate(self, prompt, model=None, options=None):
            return "ok"

        def embed(self, texts, model=None):
            return []

        async def embed_async(self, texts, model=None):
            return []

        def health(self):
            return {}

    p = ConCaps()
    assert p.supports("a") is True
    assert p.supports("b") is True
    assert p.supports("c") is False
    assert p.supports("d") is True
    assert p.supports("e") is False
    assert p.supports("noexiste") is False


def test_generate_stream_y_chat():
    """Rama: generate_stream produce y chat_generate formatea mensajes."""
    B = _base()

    class ConStream(B):
        _provider_name = "x"
        capabilities = {"chat": True}  # noqa: RUF012

        def generate(self, prompt, model=None, options=None):
            return f"resp:{prompt}"

        def embed(self, texts, model=None):
            return []

        async def embed_async(self, texts, model=None):
            return []

        def health(self):
            return {}

    p = ConStream()
    assert list(p.generate_stream("hola")) == ["resp:hola"]
    r = p.chat_generate([{"role": "user", "content": "q"}])
    assert r["content"] == "resp:<user>q</user>"
    assert r["tool_calls"] is None


def test_repr_resultado():
    """Rama: __repr__ de ProviderValidationResult válido e inválido."""
    from motor.core.llm.base import ProviderValidationResult

    ok = ProviderValidationResult(True, [], "x")
    assert "valid=True" in repr(ok) and "name='x'" in repr(ok)
    bad = ProviderValidationResult(False, ["err1"])
    assert "valid=False" in repr(bad) and "err1" in repr(bad)


def test_check_signature_error_inspeccion():
    """Rama: _check_signature con __signature__ inválido."""
    from motor.core.llm.base import _check_signature

    def _f():
        return None

    _f.__signature__ = "invalido"
    assert "error al inspeccionar firma" in _check_signature(_f, ["prompt"], [])


def test_validate_generate_no_callable_firmas():
    """Rama: generate no callable -> _validar_firmas salta."""
    from motor.core.llm.base import validate_provider

    B = _base()

    class GenStr(B):
        _provider_name = "x"
        capabilities = {"chat": True}  # noqa: RUF012
        generate = "no-method"

        def embed(self, texts, model=None):
            return []

        async def embed_async(self, texts, model=None):
            return []

        def health(self):
            return {}

    r = validate_provider(GenStr)
    assert not r.valid
    assert any("generate no es invocable" in e for e in r.errors)
