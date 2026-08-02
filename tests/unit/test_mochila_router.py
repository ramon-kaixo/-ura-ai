"""Tests for core/mochila/router.py."""

import pytest

from core.mochila.router import NoProviderAvailable, Router, RouteResult


def make_providers():
    return {"ollama": object(), "openrouter": object()}


class TestRutasPorDefecto:
    def test_existen_tres_tipos(self):
        from core.mochila.router import RUTAS_POR_DEFECTO

        assert set(RUTAS_POR_DEFECTO) == {"codigo", "razonamiento", "rapido"}


class TestElegirProvider:
    def test_modelo_explicito_con_provider(self):
        r = Router(providers=make_providers())
        res = r.elegir_provider("rapido", "openrouter/anthropic/claude-sonnet-4")
        assert res.provider == "openrouter"
        assert res.modelo == "anthropic/claude-sonnet-4"
        assert res.route_reason.startswith("explicit:")

    def test_modelo_explicito_sin_provider_usar_ollama(self):
        r = Router(providers=make_providers())
        res = r.elegir_provider("rapido", "mi-modelo-custom")
        assert res.provider == "ollama"
        assert res.modelo == "mi-modelo-custom"

    def test_modelo_explicito_provider_inexistente(self):
        r = Router(providers=make_providers())
        res = r.elegir_provider("rapido", "nope/m")
        assert res.provider == "ollama"

    def test_auto_recorre_ruta(self):
        r = Router(providers=make_providers())
        res = r.elegir_provider("codigo", "auto")
        assert res.provider in ("ollama", "openrouter")

    def test_sin_provider_usa_ruta_rapido(self):
        r = Router(providers={"ollama": object()})
        res = r.elegir_provider("codigo", None)
        assert res.provider == "ollama"

    def test_levanta_sin_providers(self):
        r = Router(providers={})
        with pytest.raises(NoProviderAvailable):
            r.elegir_provider("codigo", None)

    def test_levanta_si_ruta_vacia(self):
        r = Router(providers={}, rutas={"codigo": [], "rapido": []})
        with pytest.raises(NoProviderAvailable):
            r.elegir_provider("codigo", None)

    def test_prioriza_provider_disponible(self):
        r = Router(providers={"openrouter": object()})
        res = r.elegir_provider("codigo", None)
        assert res.provider == "openrouter"


class TestClasificadorKeyword:
    def test_task_hint_directo(self):
        from core.mochila.router import ClasificadorKeyword

        c = ClasificadorKeyword()
        assert c.clasificar([], "codigo") == "codigo"
        assert c.clasificar([], "razonamiento") == "razonamiento"
        assert c.clasificar([], "rapido") == "rapido"

    def test_hint_invalido_no_aplica(self):
        from core.mochila.router import ClasificadorKeyword

        c = ClasificadorKeyword()
        assert c.clasificar([{"content": "hola"}], "otra_cosa") == "rapido"

    def test_mas_palabras_codigo(self):
        from core.mochila.router import ClasificadorKeyword

        c = ClasificadorKeyword()
        msg = [{"content": "refactor de esta funcion, hay un bug, haz fix con test"}]
        assert c.clasificar(msg) == "codigo"

    def test_mas_palabras_razonamiento(self):
        from core.mochila.router import ClasificadorKeyword

        c = ClasificadorKeyword()
        msg = [{"content": "analiza esta arquitectura y recomienda la mejor estrategia"}]
        assert c.clasificar(msg) == "razonamiento"

    def test_empate_rapido(self):
        from core.mochila.router import ClasificadorKeyword

        c = ClasificadorKeyword()
        assert c.clasificar([{"content": "hola que tal"}]) == "rapido"

    def test_multiples_mensajes(self):
        from core.mochila.router import ClasificadorKeyword

        c = ClasificadorKeyword()
        msg = [{"content": "hola"}, {"content": "funcion con bug"}]
        assert c.clasificar(msg) == "codigo"


class TestRoute:
    def test_route_con_hint(self):
        r = Router(providers=make_providers())
        res = r.route([{"content": "hola"}], task_hint="codigo")
        assert isinstance(res, RouteResult)
        assert res.route_reason == "keyword:codigo"

    def test_route_modelo_explicito(self):
        r = Router(providers=make_providers())
        res = r.route([{"content": "hola"}], modelo_hint="ollama/foo")
        assert res.provider == "ollama"
        assert res.modelo == "foo"

    def test_route_auto_como_sin_hint(self):
        r = Router(providers=make_providers())
        res = r.route([{"content": "hola"}], modelo_hint="auto")
        assert res.provider in ("ollama", "openrouter")
