"""Test fallback del Router ante clasificador fuera de contrato (TASK-20260812-004)."""

from core.mochila.router import Router, RouteResult


class ClasificadorInvalido:
    """Clasificador que devuelve un tipo fuera de las rutas definidas."""

    def clasificar(self, mensajes: list, task_hint: str | None = None) -> str:
        return "tipo_desconocido"


class ClasificadorRapido:
    """Clasificador válido mínimo."""

    def clasificar(self, mensajes: list, task_hint: str | None = None) -> str:
        return "rapido"


def test_tipo_invalido_hace_fallback_a_rapido() -> None:
    providers = {"ollama": {"modelo": "qwen2.5:3b"}}
    router = Router(providers=providers, clasificador=ClasificadorInvalido())
    resultado: RouteResult = router.route([{"content": "hola"}])
    assert resultado.provider == "ollama"
    assert resultado.route_reason == "keyword:rapido"


def test_tipo_valido_sigue_igual() -> None:
    providers = {"ollama": {"modelo": "qwen2.5:3b"}}
    router = Router(providers=providers, clasificador=ClasificadorRapido())
    resultado: RouteResult = router.route([{"content": "hola"}])
    assert resultado.route_reason == "keyword:rapido"


def test_modelo_especifico_no_afectado_por_fallback() -> None:
    providers = {"openrouter": {"modelo": "x"}}
    router = Router(providers=providers, clasificador=ClasificadorInvalido())
    resultado: RouteResult = router.route([{"content": "hola"}], modelo_hint="mi-modelo")
    assert resultado.modelo == "mi-modelo"
    assert resultado.route_reason == "explicit:mi-modelo"
