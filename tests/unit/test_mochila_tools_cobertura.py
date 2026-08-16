"""Cobertura 100x100 de core/mochila/tools.py (TASK-20260815-003).

Cubre las herramientas de la mochila (web_search, page_read, file_read,
crawl_web, ejecutar_tool) y sus helpers internos usando mocks de
httpx.AsyncClient y de crawl4ai, sin red real ni efectos laterales.
"""

from __future__ import annotations

import sys
import time
import types
from pathlib import Path
from types import SimpleNamespace
from typing import Self

import pytest

from core.mochila import tools as tools_mod
from core.mochila.tools import (
    DEFAULT_ENGINE,
    PAGEREAD_MAX_SIZE,
    PAGEREAD_TIMEOUT,
    SEARXNG_TIMEOUT,
    TOOL_HANDLERS,
    TOOL_SCHEMAS,
    WEBSEARCH_INTERVAL,
    _buscar_ddg,
    _buscar_searxng,
    _en_whitelist,
    _extraer_texto,
    crawl_web,
    ejecutar_tool,
    file_read,
    page_read,
    web_search,
)

DDG_HTML = """
<html><body>
<a rel="nofollow" href="https://example.com/1" class='result-link'>Uno</a>
<a rel="nofollow" href="https://example.com/2" class='result-link'>Dos</a>
<a rel="nofollow" href="https://example.com/3" class='result-link'>Tres</a>
<td class='result-snippet'>Snip <b>uno</b></td>
<td class='result-snippet'>Snip dos</td>
<td class='result-snippet'>Snip tres</td>
</body></html>
"""

DDG_HTML_ENTITIES = """
<a rel="nofollow" href="https://example.com/e" class='result-link'>Titulo &#x27;A&#x27; &amp; B</a>
"""

DDG_SNIPPET_ENTITIES = """
<a rel="nofollow" href="https://example.com/s" class='result-link'>Solo</a>
<td class='result-snippet'>m&aacute;s &amp; m&aacute;s</td>
<td class='result-snippet'>sobra</td>
"""


class FakeResp:
    """Respuesta httpx falsa."""

    def __init__(
        self,
        text: str = "",
        status_code: int = 200,
        is_error: bool = False,
        json_data: dict | None = None,
        headers: dict | None = None,
    ) -> None:
        self.text = text
        self.status_code = status_code
        self.is_error = is_error
        self._json = json_data
        self.headers = headers or {}

    def json(self) -> dict:
        return self._json or {}


class FakeClient:
    """Cliente httpx.AsyncClient falso (context manager async)."""

    def __init__(
        self,
        post_resp: FakeResp | None = None,
        get_resp: FakeResp | None = None,
        post_error: Exception | None = None,
        get_error: Exception | None = None,
    ) -> None:
        self._post_resp = post_resp
        self._get_resp = get_resp
        self._post_error = post_error
        self._get_error = get_error

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *args: object) -> bool:
        return False

    async def post(self, *args: object, **kwargs: object) -> FakeResp:
        if self._post_error:
            raise self._post_error
        return self._post_resp or FakeResp()

    async def get(self, *args: object, **kwargs: object) -> FakeResp:
        if self._get_error:
            raise self._get_error
        return self._get_resp or FakeResp()


@pytest.fixture(autouse=True)
def _reset_tools_state(monkeypatch: pytest.MonkeyPatch) -> None:
    """Aísla el estado global del módulo entre tests."""
    monkeypatch.setattr(tools_mod, "_last_search", 0.0)
    monkeypatch.setattr(tools_mod, "WEBSEARCH_INTERVAL", WEBSEARCH_INTERVAL)
    monkeypatch.setattr(tools_mod, "DEFAULT_ENGINE", DEFAULT_ENGINE)


def _set_engine(monkeypatch: pytest.MonkeyPatch, engine: str) -> None:
    monkeypatch.setattr(tools_mod, "DEFAULT_ENGINE", engine)


def _set_client(monkeypatch: pytest.MonkeyPatch, client: FakeClient) -> None:
    monkeypatch.setattr(tools_mod.httpx, "AsyncClient", lambda *a, **k: client)


# ---------------------------------------------------------------------------
# _en_whitelist
# ---------------------------------------------------------------------------


def test_en_whitelist_dentro() -> None:
    assert _en_whitelist(Path("/home/ramon/URA/ura_ia_1972/README.md")) is True


def test_en_whitelist_fuera() -> None:
    assert _en_whitelist(Path("/etc/passwd")) is False


def test_en_whitelist_continue_hasta_segunda_entrada(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(tools_mod, "WHITELIST_DIRS", [Path("/no/existe"), tmp_path])
    assert _en_whitelist(tmp_path / "a.txt") is True


def test_en_whitelist_resolve_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Path, "resolve", lambda self: (_ for _ in ()).throw(OSError("boom")))
    assert _en_whitelist(Path("/tmp/x")) is False


# ---------------------------------------------------------------------------
# _extraer_texto
# ---------------------------------------------------------------------------


def test_extraer_texto_limpia_script_style_y_tags() -> None:
    html = "<html><head><style>a{color:red}</style></head><body><script>var x=1</script><p>Hola <b>mundo</b></p></body></html>"
    assert _extraer_texto(html) == "Hola mundo"


def test_extraer_texto_trunca_por_max_chars() -> None:
    html = "<p>12345678901234567890</p>"
    assert _extraer_texto(html, max_chars=5) == "12345"


def test_extraer_texto_html_vacio() -> None:
    assert _extraer_texto("") == ""


# ---------------------------------------------------------------------------
# _buscar_ddg
# ---------------------------------------------------------------------------


async def test_buscar_ddg_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_client(monkeypatch, FakeClient(post_resp=FakeResp(text=DDG_HTML)))
    res = await _buscar_ddg("hola", max_results=2)
    assert "error" not in res
    assert res["total_results"] == 2
    assert res["results"][0]["title"] == "Uno"
    assert res["results"][1]["title"] == "Dos"
    assert res["results"][0]["snippet"] == "Snip uno"


async def test_buscar_ddg_max_results_limita_y_snippets_sobran(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_client(monkeypatch, FakeClient(post_resp=FakeResp(text=DDG_HTML)))
    res = await _buscar_ddg("hola", max_results=1)
    assert res["total_results"] == 1
    assert res["results"][0]["snippet"] == "Snip uno"


async def test_buscar_ddg_limpia_entidades(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_client(monkeypatch, FakeClient(post_resp=FakeResp(text=DDG_HTML_ENTITIES + DDG_SNIPPET_ENTITIES)))
    res = await _buscar_ddg("hola", max_results=5)
    assert res["results"][0]["title"] == "Titulo 'A'   B"
    assert res["results"][0]["snippet"] == "m s m s"


async def test_buscar_ddg_error_http(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_client(monkeypatch, FakeClient(post_resp=FakeResp(is_error=True, status_code=500)))
    res = await _buscar_ddg("hola")
    assert res["error"] == "DDG error: 500"
    assert res["query"] == "hola"


async def test_buscar_ddg_excepcion(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_client(monkeypatch, FakeClient(post_error=RuntimeError("red caida")))
    res = await _buscar_ddg("hola")
    assert res["error"] == "red caida"


async def test_buscar_ddg_sin_resultados(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_client(monkeypatch, FakeClient(post_resp=FakeResp(text="<html>sin links</html>")))
    res = await _buscar_ddg("hola")
    assert res["total_results"] == 0
    assert res["results"] == []


# ---------------------------------------------------------------------------
# _buscar_searxng
# ---------------------------------------------------------------------------


async def test_buscar_searxng_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_client(
        monkeypatch,
        FakeClient(
            get_resp=FakeResp(
                json_data={
                    "results": [
                        {"title": "T1", "url": "https://u1", "content": "c1"},
                        {"title": "T2", "url": "https://u2", "content": "c2"},
                        {"title": "T3", "url": "https://u3", "content": "c3"},
                    ]
                }
            )
        ),
    )
    res = await _buscar_searxng("hola", max_results=2)
    assert "error" not in res
    assert res["total_results"] == 2
    assert res["results"][0] == {"title": "T1", "url": "https://u1", "snippet": "c1"}


async def test_buscar_searxng_sin_results(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_client(monkeypatch, FakeClient(get_resp=FakeResp(json_data={})))
    res = await _buscar_searxng("hola")
    assert res["total_results"] == 0
    assert res["results"] == []


async def test_buscar_searxng_error_http(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_client(monkeypatch, FakeClient(get_resp=FakeResp(is_error=True, status_code=503)))
    res = await _buscar_searxng("hola")
    assert res["error"] == "SearXNG error: 503"


async def test_buscar_searxng_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_client(monkeypatch, FakeClient(get_error=httpx_timeout()))
    res = await _buscar_searxng("hola")
    assert res["error"] == "SearXNG timeout"


async def test_buscar_searxng_error_generico(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_client(monkeypatch, FakeClient(get_error=ValueError("raro")))
    res = await _buscar_searxng("hola")
    assert res["error"] == "SearXNG error"


def httpx_timeout() -> Exception:
    import httpx

    return httpx.TimeoutException("t")


class _ModuloImportRoto(types.ModuleType):
    """Módulo crawl4ai falso que lanza ImportError en todo atributo."""

    def __getattr__(self, name: str) -> object:
        raise ImportError("crawl4ai no instalado")


class FakeCrawlerOk:
    """Crawler crawl4ai falso que devuelve éxito."""

    def __init__(self, verbose: bool = False, markdown: str | None = "md") -> None:
        self._markdown = markdown

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *args: object) -> bool:
        return False

    async def arun(self, url: str) -> object:
        return SimpleNamespace(success=True, markdown=self._markdown, text="texto-plano")


class FakeCrawlerFallo:
    """Crawler crawl4ai falso que devuelve error del sitio."""

    def __init__(self, verbose: bool = False) -> None:
        pass

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *args: object) -> bool:
        return False

    async def arun(self, url: str) -> object:
        return SimpleNamespace(success=False, error="sitio caido", markdown=None, text="")


class FakeCrawlerRoto:
    """Crawler crawl4ai falso que explota en la inicialización."""

    def __init__(self, verbose: bool = False) -> None:
        pass

    async def __aenter__(self) -> Self:
        raise RuntimeError("crawler explotado")

    async def __aexit__(self, *args: object) -> bool:
        return False


class FakeCrawlerSinMarkdown:
    """Crawler crawl4ai falso sin markdown (usa text)."""

    def __init__(self, verbose: bool = False) -> None:
        pass

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *args: object) -> bool:
        return False

    async def arun(self, url: str) -> object:
        return SimpleNamespace(success=True, markdown=None, text="texto-plano")


# ---------------------------------------------------------------------------
# web_search (routing + rate limit)
# ---------------------------------------------------------------------------


async def test_web_search_ddg_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_engine(monkeypatch, "duckduckgo")
    _set_client(monkeypatch, FakeClient(post_resp=FakeResp(text=DDG_HTML)))
    res = await web_search("hola")
    assert "error" not in res
    assert res["total_results"] == 3


async def test_web_search_ddg_fallback_searxng(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_engine(monkeypatch, "duckduckgo")
    _set_client(
        monkeypatch,
        FakeClient(
            post_resp=FakeResp(is_error=True, status_code=500),
            get_resp=FakeResp(json_data={"results": [{"title": "T", "url": "u", "content": "c"}]}),
        ),
    )
    res = await web_search("hola")
    assert res["total_results"] == 1


async def test_web_search_ambos_error_devuelve_ddg(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_engine(monkeypatch, "duckduckgo")
    _set_client(
        monkeypatch,
        FakeClient(
            post_resp=FakeResp(is_error=True, status_code=500),
            get_resp=FakeResp(is_error=True, status_code=503),
        ),
    )
    res = await web_search("hola")
    assert res["error"] == "DDG error: 500"


async def test_web_search_searxng_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_engine(monkeypatch, "searxng")
    _set_client(monkeypatch, FakeClient(get_resp=FakeResp(json_data={"results": [{"title": "T"}]})))
    res = await web_search("hola")
    assert res["total_results"] == 1


async def test_web_search_searxng_fallback_ddg(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_engine(monkeypatch, "searxng")
    _set_client(
        monkeypatch,
        FakeClient(
            get_resp=FakeResp(is_error=True, status_code=503),
            post_resp=FakeResp(text=DDG_HTML),
        ),
    )
    res = await web_search("hola")
    assert res["total_results"] == 3


async def test_web_search_searxng_ambos_error_devuelve_sx(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_engine(monkeypatch, "searxng")
    _set_client(
        monkeypatch,
        FakeClient(
            get_resp=FakeResp(is_error=True, status_code=503),
            post_resp=FakeResp(is_error=True, status_code=500),
        ),
    )
    res = await web_search("hola")
    assert res["error"] == "SearXNG error: 503"


async def test_web_search_rate_limit_duerme(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_engine(monkeypatch, "duckduckgo")
    _set_client(monkeypatch, FakeClient(post_resp=FakeResp(text=DDG_HTML)))
    monkeypatch.setattr(tools_mod, "WEBSEARCH_INTERVAL", 10.0)
    tools_mod._last_search = time.time()
    dormidos: list[float] = []

    async def _sleep(delay: float) -> None:
        dormidos.append(delay)

    monkeypatch.setattr(tools_mod.asyncio, "sleep", _sleep)
    res = await web_search("hola")
    assert "error" not in res
    assert len(dormidos) == 1
    assert dormidos[0] > 0


async def test_web_search_sin_espera_cuando_reciente(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_engine(monkeypatch, "duckduckgo")
    _set_client(monkeypatch, FakeClient(post_resp=FakeResp(text=DDG_HTML)))
    dormidos: list[float] = []

    async def _sleep(delay: float) -> None:
        dormidos.append(delay)

    monkeypatch.setattr(tools_mod.asyncio, "sleep", _sleep)
    res = await web_search("hola")
    assert "error" not in res
    assert dormidos == []


# ---------------------------------------------------------------------------
# page_read
# ---------------------------------------------------------------------------


async def test_page_read_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_client(
        monkeypatch,
        FakeClient(
            get_resp=FakeResp(
                text="<html><body><p>Hola</p></body></html>",
                headers={"content-type": "text/html; charset=utf-8"},
            )
        ),
    )
    res = await page_read("https://example.com")
    assert res["status"] == 200
    assert res["content"] == "Hola"
    assert res["extracted_length"] == 4


async def test_page_read_error_http(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_client(monkeypatch, FakeClient(get_resp=FakeResp(is_error=True, status_code=404)))
    res = await page_read("https://example.com")
    assert res["error"] == "HTTP 404 para: https://example.com"


async def test_page_read_content_type_no_soportado(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_client(
        monkeypatch,
        FakeClient(get_resp=FakeResp(text="pdf-bytes", headers={"content-type": "application/pdf"})),
    )
    res = await page_read("https://example.com/doc")
    assert res["error"] == "Content-Type no soportado: application/pdf"


async def test_page_read_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_client(monkeypatch, FakeClient(get_error=httpx_timeout()))
    res = await page_read("https://example.com")
    assert res["error"] == f"Timeout ({PAGEREAD_TIMEOUT}s) leyendo: https://example.com"


async def test_page_read_error_generico(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_client(monkeypatch, FakeClient(get_error=RuntimeError("dns")))
    res = await page_read("https://example.com")
    assert res["error"] == "dns"


async def test_page_read_max_chars_acotado(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tools_mod, "PAGEREAD_MAX_SIZE", 10)
    _set_client(
        monkeypatch,
        FakeClient(get_resp=FakeResp(text="<p>12345678901234567890</p>", headers={"content-type": "text/html"})),
    )
    res = await page_read("https://example.com", max_chars=PAGEREAD_MAX_SIZE + 100)
    assert res["extracted_length"] == 10
    assert res["content"] == "1234567890"


# ---------------------------------------------------------------------------
# file_read
# ---------------------------------------------------------------------------


def test_file_read_denegado_fuera_whitelist(tmp_path: Path) -> None:
    ruta = tmp_path / "outside.txt"
    ruta.write_text("x")
    res = _sync_file_read(str(tmp_path / ".." / ruta.name))
    assert res["error"] == f"Acceso denegado: {tmp_path / '..' / ruta.name}"


def test_file_read_relativo_no_existe() -> None:
    res = _sync_file_read("nunca-existira-mochila-tools.txt")
    assert res["error"].startswith("Archivo no encontrado:")


def test_file_read_no_es_archivo(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(tools_mod, "WHITELIST_DIRS", [tmp_path])
    res = _sync_file_read(str(tmp_path))
    assert res["error"] == f"No es un archivo: {tmp_path}"


def test_file_read_ok(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(tools_mod, "WHITELIST_DIRS", [tmp_path])
    archivo = tmp_path / "a.txt"
    archivo.write_text("linea1\nlinea2\n", encoding="utf-8")
    res = _sync_file_read(str(archivo))
    assert res["path"] == str(archivo.resolve())
    assert res["lines"] == 2
    assert res["size"] == 14
    assert res["content"] == "linea1\nlinea2"


def test_file_read_max_lines(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(tools_mod, "WHITELIST_DIRS", [tmp_path])
    archivo = tmp_path / "b.txt"
    archivo.write_text("\n".join(f"l{i}" for i in range(5)), encoding="utf-8")
    res = _sync_file_read(str(archivo), max_lines=3)
    assert res["lines"] == 4
    assert res["content"].endswith("... (3 lineas mostradas)")


def test_file_read_oserror(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(tools_mod, "WHITELIST_DIRS", [tmp_path])
    archivo = tmp_path / "c.txt"
    archivo.write_text("x", encoding="utf-8")

    def _roto(*args: object, **kwargs: object) -> object:
        raise OSError("permiso denegado")

    monkeypatch.setattr("builtins.open", _roto)
    res = _sync_file_read(str(archivo))
    assert res["error"] == "permiso denegado"


def _sync_file_read(path: str, max_lines: int = 200) -> dict:
    import asyncio as _aio

    return _aio.run(file_read(path, max_lines=max_lines))


# ---------------------------------------------------------------------------
# ejecutar_tool
# ---------------------------------------------------------------------------


async def test_ejecutar_tool_desconocida() -> None:
    res = await ejecutar_tool("nope", {})
    assert res == {"error": "Tool desconocida: nope"}


async def test_ejecutar_tool_conocida(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_engine(monkeypatch, "duckduckgo")
    _set_client(monkeypatch, FakeClient(post_resp=FakeResp(text=DDG_HTML)))
    res = await ejecutar_tool("web_search", {"query": "hola", "max_results": 1})
    assert res["total_results"] == 1


async def test_ejecutar_tool_crawl_web_registrada() -> None:
    assert "crawl_web" in TOOL_HANDLERS
    assert callable(TOOL_HANDLERS["crawl_web"])


# ---------------------------------------------------------------------------
# crawl_web
# ---------------------------------------------------------------------------


def _instalar_crawl4ai_fake(monkeypatch: pytest.MonkeyPatch, crawler_cls: type) -> None:
    modulo = types.ModuleType("crawl4ai")
    modulo.AsyncWebCrawler = crawler_cls  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "crawl4ai", modulo)


def _instalar_crawl4ai_import_error(monkeypatch: pytest.MonkeyPatch) -> None:
    modulo = _ModuloImportRoto("crawl4ai")
    monkeypatch.setitem(sys.modules, "crawl4ai", modulo)


async def test_crawl_web_ok_con_markdown(monkeypatch: pytest.MonkeyPatch) -> None:
    _instalar_crawl4ai_fake(monkeypatch, FakeCrawlerOk)
    res = await crawl_web("https://example.com")
    assert res["status"] == 200
    assert res["content"] == "md"


async def test_crawl_web_ok_sin_markdown_usa_text(monkeypatch: pytest.MonkeyPatch) -> None:
    _instalar_crawl4ai_fake(monkeypatch, FakeCrawlerSinMarkdown)
    res = await crawl_web("https://example.com")
    assert res["content"] == "texto-plano"


async def test_crawl_web_max_chars(monkeypatch: pytest.MonkeyPatch) -> None:
    _instalar_crawl4ai_fake(monkeypatch, FakeCrawlerOk)
    res = await crawl_web("https://example.com", max_chars=1)
    assert res["content"] == "m"


async def test_crawl_web_error_sitio(monkeypatch: pytest.MonkeyPatch) -> None:
    _instalar_crawl4ai_fake(monkeypatch, FakeCrawlerFallo)
    res = await crawl_web("https://example.com")
    assert res["error"] == "Crawl4AI: sitio caido"


async def test_crawl_web_import_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _instalar_crawl4ai_import_error(monkeypatch)
    res = await crawl_web("https://example.com")
    assert res["error"] == "crawl4ai no instalado"


async def test_crawl_web_error_generico(monkeypatch: pytest.MonkeyPatch) -> None:
    _instalar_crawl4ai_fake(monkeypatch, FakeCrawlerRoto)
    res = await crawl_web("https://example.com")
    assert res["error"] == "crawler explotado"


# ---------------------------------------------------------------------------
# Constantes y esquemas (regresión de contrato)
# ---------------------------------------------------------------------------


def test_contrato_esquemas() -> None:
    nombres = {s["function"]["name"] for s in TOOL_SCHEMAS}
    assert nombres == {"web_search", "page_read", "file_read", "crawl_web"}


def test_contrato_handlers() -> None:
    assert set(TOOL_HANDLERS) == {"web_search", "page_read", "file_read", "crawl_web"}


def test_contrato_timeouts_positivos() -> None:
    assert SEARXNG_TIMEOUT > 0
    assert PAGEREAD_TIMEOUT > 0
    assert WEBSEARCH_INTERVAL >= 0
