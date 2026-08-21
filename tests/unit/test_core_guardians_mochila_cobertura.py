"""Cobertura 100x100 de core guardians/mochila/path_setup. TASK-20260820-019."""

from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path
from typing import ClassVar

import pytest

import core.guardian_disco as gd
import core.mochila.vram_scheduler as vram_mod
import core.path_setup as ps
import core.stealth_fetcher as sf
from core.guardian_disco import (
    DEFAULT_CONFIG,
    calcular_hash,
    cargar_config,
    comparar,
    escanear,
    guardar_historial,
    guardar_snapshot,
    verificar_escritura,
)
from core.guardians.ast_sentinel import MAX_CC, ASTSentinel, V
from core.mochila.providers.base import Provider, ProviderError
from core.mochila.status_endpoint import _fs_bug_status, _ram_info, _timer_status, system_status
from core.mochila.vram_scheduler import VRAMAwareScheduler
from core.stealth_fetcher import _default_headers, _random_ua, fetch, fetch_stealth, fetch_with_fallback

# ── path_setup ───────────────────────────────────────────────


def test_setup_path_y_get_root() -> None:
    ps._PROJECT_ROOT = None
    ps.setup_path()
    root = ps.get_project_root()
    assert root.name == "ura_ia_1972"
    assert str(root) in sys.path


def test_setup_path_insert_syspath(monkeypatch: pytest.MonkeyPatch) -> None:
    # forzar que el root NO esté en sys.path → se inserta
    ps._PROJECT_ROOT = None
    root = Path(__file__).resolve().parent.parent.parent
    monkeypatch.setattr(ps.sys, "path", [p for p in sys.path if p != str(root)])
    ps.setup_path()
    assert str(ps._PROJECT_ROOT) in ps.sys.path


def test_get_project_root_sin_init(monkeypatch: pytest.MonkeyPatch) -> None:
    ps._PROJECT_ROOT = None
    root = ps.get_project_root()
    assert root is not None
    assert root.name == "ura_ia_1972"


def test_setup_path_idempotente() -> None:
    ps._PROJECT_ROOT = Path("/fake")
    ps.setup_path()  # ya seteado → return
    assert Path("/fake") == ps._PROJECT_ROOT


# ── guardian_disco ───────────────────────────────────────────


def test_cargar_config_crea(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gd, "NERVIOSO", Path(str(tmp_path)) / ".nervioso")
    monkeypatch.setattr(gd, "CONFIG_PATH", Path(str(tmp_path)) / ".nervioso" / "guardian_config.json")
    cfg = cargar_config()
    assert cfg["hash_truncar"] == 64
    assert (Path(str(tmp_path)) / ".nervioso" / "guardian_config.json").exists()


def test_cargar_config_lee(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    f = Path(str(tmp_path)) / "guardian_config.json"
    f.write_text(json.dumps({"hash_truncar": 32, "patrones": ["*.py"], "excluir": []}))
    monkeypatch.setattr(gd, "CONFIG_PATH", f)
    cfg = cargar_config()
    assert cfg["hash_truncar"] == 32


def test_cargar_config_corrupto(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    f = Path(str(tmp_path)) / "guardian_config.json"
    f.write_text("{roto")
    monkeypatch.setattr(gd, "CONFIG_PATH", f)
    cfg = cargar_config()
    assert cfg["hash_truncar"] == 64  # default tras error


def test_calcular_hash(tmp_path: object) -> None:
    f = Path(str(tmp_path)) / "a.txt"
    f.write_text("contenido")
    h = calcular_hash(f)
    assert len(h) == 64
    assert calcular_hash(f, truncar=8) == h[:8]


def test_escanear(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gd, "URA", Path(str(tmp_path)))
    (Path(str(tmp_path)) / "a.py").write_text("x = 1")
    (Path(str(tmp_path)) / "b.json").write_text("{}")
    (Path(str(tmp_path)) / ".venv").mkdir()
    (Path(str(tmp_path)) / ".venv" / "interno.py").write_text("y")
    actual = escanear(DEFAULT_CONFIG)
    assert "a.py" in actual
    assert "b.json" in actual
    assert ".venv/interno.py" not in actual


def test_escanear_error_acceso(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gd, "URA", Path(str(tmp_path)))
    (Path(str(tmp_path)) / "a.py").write_text("x")
    monkeypatch.setattr(gd, "calcular_hash", lambda f, t: (_ for _ in ()).throw(PermissionError("denegado")))
    assert escanear(DEFAULT_CONFIG) == {}


def test_comparar() -> None:
    cambios = comparar({"a.py": "h1", "b.py": "h2"}, {"a.py": "h1", "c.py": "h3"})
    status = {c["status"] for c in cambios}
    assert "MODIFICADO" not in status  # a.py igual
    assert any(c["file"] == "c.py" and c["status"] == "NUEVO" for c in cambios)
    assert any(c["file"] == "b.py" and c["status"] == "FANTASMA" for c in cambios)


def test_verificar_escritura_ok(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gd, "URA", Path(str(tmp_path)))
    f = Path(str(tmp_path)) / "a.py"
    f.write_text("x")
    h = calcular_hash(f)
    assert verificar_escritura("a.py", h) is True


def test_verificar_escritura_no_existe(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gd, "URA", Path(str(tmp_path)))
    assert verificar_escritura("no.py", "hash") is False


def test_verificar_escritura_hash_distinto(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gd, "URA", Path(str(tmp_path)))
    f = Path(str(tmp_path)) / "a.py"
    f.write_text("x")
    assert verificar_escritura("a.py", "0" * 64) is False


def test_guardar_snapshot(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gd, "NERVIOSO", Path(str(tmp_path)) / ".nervioso")
    monkeypatch.setattr(gd, "SNAPSHOT", Path(str(tmp_path)) / ".nervioso" / "hashes.json")
    guardar_snapshot({"total": 1})
    data = json.loads((Path(str(tmp_path)) / ".nervioso" / "hashes.json").read_text())
    assert data["total"] == 1


def test_guardar_historial(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gd, "HISTORIAL", Path(str(tmp_path)) / "hist.jsonl")
    guardar_historial([{"status": "NUEVO"}], 5)
    lineas = (Path(str(tmp_path)) / "hist.jsonl").read_text().strip().split("\n")
    assert len(lineas) == 1
    data = json.loads(lineas[0])
    assert data["num_cambios"] == 1
    assert data["nuevos"] == 1


def test_guardian_cmd_verify(monkeypatch: pytest.MonkeyPatch, tmp_path: object) -> None:
    monkeypatch.setattr(gd, "URA", Path(str(tmp_path)))
    f = Path(str(tmp_path)) / "a.py"
    f.write_text("x")
    h = calcular_hash(f)
    exit_codes = []

    def _exit(code: int) -> None:
        exit_codes.append(code)

    monkeypatch.setattr(gd.sys, "exit", _exit)
    gd._cmd_verify("a.py", h, {"hash_truncar": 64})
    gd._cmd_verify("no.py", h, {"hash_truncar": 64})
    assert exit_codes == [0, 1]


def test_guardian_cmd_init(monkeypatch: pytest.MonkeyPatch, tmp_path: object) -> None:
    monkeypatch.setattr(gd, "URA", Path(str(tmp_path)))
    (Path(str(tmp_path)) / "a.py").write_text("x")
    monkeypatch.setattr(gd, "NERVIOSO", Path(str(tmp_path)) / ".nervioso")
    monkeypatch.setattr(gd, "SNAPSHOT", Path(str(tmp_path)) / ".nervioso" / "hashes.json")
    gd._cmd_init(DEFAULT_CONFIG)
    snap = json.loads((Path(str(tmp_path)) / ".nervioso" / "hashes.json").read_text())
    assert snap["total"] >= 1


def test_guardian_cmd_scan_inicial(monkeypatch: pytest.MonkeyPatch, tmp_path: object) -> None:
    monkeypatch.setattr(gd, "URA", Path(str(tmp_path)))
    (Path(str(tmp_path)) / "a.py").write_text("x")
    monkeypatch.setattr(gd, "NERVIOSO", Path(str(tmp_path)) / ".nervioso")
    monkeypatch.setattr(gd, "SNAPSHOT", Path(str(tmp_path)) / ".nervioso" / "hashes.json")
    monkeypatch.setattr(gd, "HISTORIAL", Path(str(tmp_path)) / ".nervioso" / "hist.jsonl")
    gd._cmd_scan(DEFAULT_CONFIG)
    snap = json.loads((Path(str(tmp_path)) / ".nervioso" / "hashes.json").read_text())
    assert "cambios_detectados" in snap


def test_guardian_main_verify(monkeypatch: pytest.MonkeyPatch, tmp_path: object) -> None:
    monkeypatch.setattr(gd, "URA", Path(str(tmp_path)))
    f = Path(str(tmp_path)) / "a.py"
    f.write_text("x")
    h = calcular_hash(f)
    monkeypatch.setattr(gd, "_parse_args", lambda: type("A", (), {"verify": ["a.py", h], "init": False, "scan": False})())
    monkeypatch.setattr(gd, "cargar_config", lambda: DEFAULT_CONFIG)
    monkeypatch.setattr(gd, "_cmd_verify", lambda a, hh, c: None)
    gd.main()  # no lanza


def test_guardian_main_init(monkeypatch: pytest.MonkeyPatch) -> None:
    llamado = {"n": 0}
    monkeypatch.setattr(gd, "_parse_args", lambda: type("A", (), {"verify": None, "init": True, "scan": False})())
    monkeypatch.setattr(gd, "cargar_config", lambda: DEFAULT_CONFIG)
    monkeypatch.setattr(gd, "_cmd_init", lambda c: llamado.__setitem__("n", 1))
    gd.main()
    assert llamado["n"] == 1


def test_guardian_main_scan(monkeypatch: pytest.MonkeyPatch) -> None:
    llamado = {"n": 0}
    monkeypatch.setattr(gd, "_parse_args", lambda: type("A", (), {"verify": None, "init": False, "scan": True})())
    monkeypatch.setattr(gd, "cargar_config", lambda: DEFAULT_CONFIG)
    monkeypatch.setattr(gd, "_cmd_scan", lambda c: llamado.__setitem__("n", 1))
    gd.main()
    assert llamado["n"] == 1


def test_guardian_main_scan_por_defecto(monkeypatch: pytest.MonkeyPatch) -> None:
    llamado = {"n": 0}
    monkeypatch.setattr(gd, "_parse_args", lambda: type("A", (), {"verify": None, "init": False, "scan": False})())
    monkeypatch.setattr(gd, "cargar_config", lambda: DEFAULT_CONFIG)
    monkeypatch.setattr(gd, "_cmd_scan", lambda c: llamado.__setitem__("n", 1))
    gd.main()
    assert llamado["n"] == 1


def test_guardian_main_con_verify_no_scan(monkeypatch: pytest.MonkeyPatch) -> None:
    llamado = {"n": 0}
    monkeypatch.setattr(gd, "_parse_args", lambda: type("A", (), {"verify": ["a", "h"], "init": False, "scan": True})())
    monkeypatch.setattr(gd, "cargar_config", lambda: DEFAULT_CONFIG)
    monkeypatch.setattr(gd, "_cmd_verify", lambda a, h, c: llamado.__setitem__("n", 1))
    gd.main()
    assert llamado["n"] == 1  # verify gana; no se llega al scan


def test_guardian_parse_args_verify() -> None:
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(gd.sys, "argv", ["guardian", "--verify", "a.py", "hash123"])
    try:
        args = gd._parse_args()
        assert args.verify == ["a.py", "hash123"]
        assert args.scan is False
        assert args.init is False
    finally:
        monkeypatch.undo()


def test_guardian_parse_args_scan() -> None:
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(gd.sys, "argv", ["guardian", "--scan", "--json"])
    try:
        args = gd._parse_args()
        assert args.scan is True
        assert args.json is True
    finally:
        monkeypatch.undo()


def test_guardian_cmd_scan_con_previo(monkeypatch: pytest.MonkeyPatch, tmp_path: object) -> None:
    monkeypatch.setattr(gd, "URA", Path(str(tmp_path)))
    f = Path(str(tmp_path)) / "a.py"
    f.write_text("x")
    monkeypatch.setattr(gd, "NERVIOSO", Path(str(tmp_path)) / ".nervioso")
    monkeypatch.setattr(gd, "SNAPSHOT", Path(str(tmp_path)) / ".nervioso" / "hashes.json")
    monkeypatch.setattr(gd, "HISTORIAL", Path(str(tmp_path)) / ".nervioso" / "hist.jsonl")
    # snapshot previo con a.py modificado
    guardar_snapshot({"a.py": "hash-antiguo"})
    gd._cmd_scan(DEFAULT_CONFIG)
    snap = json.loads((Path(str(tmp_path)) / ".nervioso" / "hashes.json").read_text())
    assert any(c["status"] == "MODIFICADO" for c in snap["cambios_detectados"])


# ── stealth_fetcher ──────────────────────────────────────────


def test_random_ua() -> None:
    ua = _random_ua()
    assert ua in sf.USER_AGENTS


def test_default_headers() -> None:
    h = _default_headers()
    assert "User-Agent" in h
    assert h["DNT"] == "1"


def test_fetch_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Resp:
        is_error = False
        text = "<html>ok</html>"

    class _Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, url: str, headers: dict):
            return _Resp()

    fake_httpx = type("httpx", (), {"AsyncClient": lambda *a, **k: _Client()})
    monkeypatch.setattr(sf, "httpx", fake_httpx)
    assert asyncio.run(fetch("http://x")) == "<html>ok</html>"


def test_fetch_error(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Resp:
        is_error = True
        text = ""

    class _Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, url: str, headers: dict):
            return _Resp()

    fake_httpx = type("httpx", (), {"AsyncClient": lambda *a, **k: _Client()})
    monkeypatch.setattr(sf, "httpx", fake_httpx)
    assert asyncio.run(fetch("http://x")) is None


def test_fetch_excepcion(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, url: str, headers: dict):
            msg = "sin red"
            raise ConnectionError(msg)

    fake_httpx = type("httpx", (), {"AsyncClient": lambda *a, **k: _Client()})
    monkeypatch.setattr(sf, "httpx", fake_httpx)
    assert asyncio.run(fetch("http://x")) is None


def test_fetch_stealth_sin_playwright(monkeypatch: pytest.MonkeyPatch) -> None:
    import builtins

    real = builtins.__import__

    def _bloq(name: str, *a, **k):
        if name == "playwright.async_api":
            msg = "no playwright"
            raise ImportError(msg)
        return real(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", _bloq)
    assert asyncio.run(fetch_stealth("http://x")) is None


def test_fetch_stealth_sin_playwright_stealth(monkeypatch: pytest.MonkeyPatch) -> None:
    import sys
    import types

    class _Page:
        async def goto(self, url: str, wait_until: str, timeout: int) -> None:  # noqa: ASYNC109
            pass

        async def content(self) -> str:
            return "x"

        async def close(self) -> None:
            pass

    class _Context:
        async def new_page(self) -> _Page:
            return _Page()

    class _Browser:
        async def new_context(self, **kw) -> _Context:
            return _Context()

        async def close(self) -> None:
            pass

    class _Playwright:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        @property
        def chromium(self):
            class _C:
                async def launch(self, headless: bool = True):
                    return _Browser()

            return _C()

    fake_pa = types.ModuleType("playwright.async_api")
    fake_pa.async_playwright = lambda: _Playwright()
    # playwright_stealth NO disponible → ImportError → return None
    monkeypatch.setitem(sys.modules, "playwright.async_api", fake_pa)
    monkeypatch.setitem(sys.modules, "playwright", types.ModuleType("playwright"))
    monkeypatch.delitem(sys.modules, "playwright_stealth", raising=False)

    import builtins

    real = builtins.__import__

    def _bloq(name: str, *a, **k):
        if name == "playwright_stealth":
            msg = "no stealth"
            raise ImportError(msg)
        return real(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", _bloq)
    assert asyncio.run(fetch_stealth("http://x")) is None


def test_fetch_stealth_error_general(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(*a, **k):
        msg = "playwright roto"
        raise RuntimeError(msg)

    monkeypatch.setattr(sf, "_random_ua", _boom)
    assert asyncio.run(fetch_stealth("http://x")) is None


def test_fetch_with_fallback_sin_stealth(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _stealth(*a, **k):
        return None

    async def _fetch(*a, **k):
        return "resultado"

    monkeypatch.setattr(sf, "fetch_stealth", _stealth)
    monkeypatch.setattr(sf, "fetch", _fetch)

    async def _sleep(s: float) -> None:
        pass

    monkeypatch.setattr(sf.asyncio, "sleep", _sleep)
    assert asyncio.run(fetch_with_fallback("http://x")) == "resultado"


def test_fetch_with_fallback_con_stealth(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _stealth(*a, **k):
        return "html stealth"

    monkeypatch.setattr(sf, "fetch_stealth", _stealth)
    assert asyncio.run(fetch_with_fallback("http://x")) == "html stealth"  # sin fallback


def test_fetch_stealth_playwright_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    import sys
    import types

    class _Page:
        def __init__(self) -> None:
            self.closed = False

        async def goto(self, url: str, wait_until: str, timeout: int) -> None:  # noqa: ASYNC109
            pass

        async def content(self) -> str:
            return "<html>playwright</html>"

        async def close(self) -> None:
            self.closed = True

    class _Context:
        def __init__(self) -> None:
            self._pages: list[_Page] = []

        async def new_page(self) -> _Page:
            p = _Page()
            self._pages.append(p)
            return p

    class _Browser:
        def __init__(self) -> None:
            self.closed = False

        async def new_context(self, **kw) -> _Context:
            return _Context()

        async def close(self) -> None:
            self.closed = True

    class _Playwright:
        def __init__(self) -> None:
            self._browser = _Browser()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        @property
        def chromium(self):
            return type("C", (), {"launch": lambda **k: _get_browser(self)})() if False else type("C", (), {"launch": self._launch})()

        async def _launch(self, headless: bool = True):
            return self._browser

    def _get_browser(pw):
        return pw._browser

    fake_pa = types.ModuleType("playwright.async_api")
    fake_pa.async_playwright = lambda: _Playwright()
    fake_stealth = types.ModuleType("playwright_stealth")
    fake_stealth.stealth_async = lambda page: None

    async def _stealth_async(page) -> None:
        pass

    fake_stealth.stealth_async = _stealth_async
    monkeypatch.setitem(sys.modules, "playwright.async_api", fake_pa)
    monkeypatch.setitem(sys.modules, "playwright", types.ModuleType("playwright"))
    monkeypatch.setitem(sys.modules, "playwright_stealth", fake_stealth)
    monkeypatch.setattr(sf, "_random_ua", lambda: "UA-test")
    assert asyncio.run(fetch_stealth("http://x")) == "<html>playwright</html>"


def test_fetch_stealth_goto_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    import sys
    import types

    class _Page:
        def __init__(self, fail_first: bool = True) -> None:
            self.fail_first = fail_first
            self.closed = False

        async def goto(self, url: str, wait_until: str, timeout: int) -> None:  # noqa: ASYNC109
            if self.fail_first and wait_until == "networkidle":
                msg = "timeout"
                raise TimeoutError(msg)

        async def content(self) -> str:
            return "<html>fallback</html>"

        async def close(self) -> None:
            self.closed = True

    class _Context:
        async def new_page(self) -> _Page:
            return _Page(fail_first=False)

    class _Browser:
        async def new_context(self, **kw) -> _Context:
            return _Context()

        async def close(self) -> None:
            pass

    class _Playwright:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        @property
        def chromium(self):
            class _C:
                async def launch(self, headless: bool = True):
                    return _Browser()

            return _C()

    fake_pa = types.ModuleType("playwright.async_api")
    fake_pa.async_playwright = lambda: _Playwright()
    fake_stealth = types.ModuleType("playwright_stealth")

    async def _stealth_async(page) -> None:
        pass

    fake_stealth.stealth_async = _stealth_async
    monkeypatch.setitem(sys.modules, "playwright.async_api", fake_pa)
    monkeypatch.setitem(sys.modules, "playwright", types.ModuleType("playwright"))
    monkeypatch.setitem(sys.modules, "playwright_stealth", fake_stealth)
    assert asyncio.run(fetch_stealth("http://x")) == "<html>fallback</html>"


def test_fetch_stealth_fallback_roto(monkeypatch: pytest.MonkeyPatch) -> None:
    import sys
    import types

    class _Page:
        def __init__(self) -> None:
            self.closed = False

        async def goto(self, url: str, wait_until: str, timeout: int) -> None:  # noqa: ASYNC109
            msg = "todo roto"
            raise TimeoutError(msg)

        async def content(self) -> str:
            return ""

        async def close(self) -> None:
            self.closed = True

    class _Context:
        async def new_page(self) -> _Page:
            return _Page()

    class _Browser:
        async def new_context(self, **kw) -> _Context:
            return _Context()

        async def close(self) -> None:
            pass

    class _Playwright:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        @property
        def chromium(self):
            class _C:
                async def launch(self, headless: bool = True):
                    return _Browser()

            return _C()

    fake_pa = types.ModuleType("playwright.async_api")
    fake_pa.async_playwright = lambda: _Playwright()
    fake_stealth = types.ModuleType("playwright_stealth")

    async def _stealth_async(page) -> None:
        pass

    fake_stealth.stealth_async = _stealth_async
    monkeypatch.setitem(sys.modules, "playwright.async_api", fake_pa)
    monkeypatch.setitem(sys.modules, "playwright", types.ModuleType("playwright"))
    monkeypatch.setitem(sys.modules, "playwright_stealth", fake_stealth)
    assert asyncio.run(fetch_stealth("http://x")) is None  # fallback también falla


# ── ast_sentinel ─────────────────────────────────────────────


def test_v_resumen_ok() -> None:
    v = V(ok=True, debt=None, errs=[], warns=[], m={})
    assert "[AST] OK" in v.resumen()


def test_v_resumen_fail_con_deuda() -> None:
    v = V(ok=False, debt="0xabc", errs=["e1"], warns=["w1"], m={})
    r = v.resumen()
    assert "[AST] FAIL" in r
    assert "e1" in r
    assert "DEBT_ID: 0xabc" in r


def test_sentinel_sintaxis_error() -> None:
    s = ASTSentinel()
    v = s.analizar("def roto(:\n")
    assert v.ok is False
    assert "Syntax" in v.errs[0]


def test_sentinel_ok() -> None:
    s = ASTSentinel()
    codigo = "def f(x: int) -> int:\n    \"\"\"doc\"\"\"\n    return x\n"
    v = s.analizar(codigo)
    assert v.ok is True


def test_sentinel_cc_alto() -> None:
    s = ASTSentinel()
    codigo = "def f():\n" + "    if 1:\n        pass\n" * (MAX_CC + 5)
    v = s.analizar(codigo, prod=False)
    assert any("CC" in e for e in v.errs)


def test_sentinel_sin_retorno() -> None:
    s = ASTSentinel()
    v = s.analizar("def f(x: int):\n    print(x)\n")
    assert any("sin retorno" in e for e in v.errs)


def test_sentinel_sin_doc() -> None:
    s = ASTSentinel()
    v = s.analizar("def f(x: int) -> int:\n    return x\n")
    assert any("sin doc" in w for w in v.warns)


def test_sentinel_arg_sin_tipo() -> None:
    s = ASTSentinel()
    v = s.analizar("def f(x, y: int) -> int:\n    return y\n")
    assert any("sin tipo" in e for e in v.errs)


def test_sentinel_estructuras_try() -> None:
    s = ASTSentinel()
    codigo = "def f():\n    try:\n        pass\n    except:\n        pass\n"
    v = s.analizar(codigo, prod=False)
    assert any("except" in e for e in v.errs)
    assert any("pass" in e for e in v.errs)


def test_sentinel_global() -> None:
    s = ASTSentinel()
    v = s.analizar("x = 1\ndef f():\n    global x\n    return x\n", prod=False)
    assert any("global" in e for e in v.errs)


def test_sentinel_import_prohibido() -> None:
    s = ASTSentinel()
    v = s.analizar("import pickle\nimport marshal\nx = 1\n", prod=False)
    assert any("import:" in e for e in v.errs)


def test_sentinel_import_from_prohibido() -> None:
    s = ASTSentinel()
    v = s.analizar("from os import system\nx = 1\n", prod=False)
    assert any("os.system" in e for e in v.errs)


def test_sentinel_todo_fine() -> None:
    s = ASTSentinel()
    codigo = "def f(x: int) -> int:\n    \"\"\"doc\"\"\"\n    return x\n"
    v = s.analizar(codigo, prod=True)
    assert v.ok is True
    assert v.m["nf"] == 1
    assert v.m["lines"] == 3


def test_sentinel_magic_numbers() -> None:
    s = ASTSentinel()
    v = s.analizar("def f() -> int:\n    return 42\n", prod=False)
    assert any("magic 42" in w for w in v.warns)


def test_sentinel_async_funcion() -> None:
    s = ASTSentinel()
    v = s.analizar("async def f() -> None:\n    pass\n", prod=False)
    assert v.m["nf"] == 1


def test_sentinel_estructuras_for_while() -> None:
    s = ASTSentinel()
    codigo = "def f() -> None:\n    for i in range(3):\n        pass\n    while True:\n        break\n    a = True and False\n"
    v = s.analizar(codigo, prod=False)
    assert v.ok is True  # CC sube pero no supera MAX_CC


def test_sentinel_try_con_tipo() -> None:
    s = ASTSentinel()
    codigo = "def f() -> None:\n    try:\n        pass\n    except ValueError as e:\n        print(e)\n"
    v = s.analizar(codigo, prod=False)
    assert not any("except" in e for e in v.errs)  # handler con tipo → ok


def test_sentinel_try_pass() -> None:
    s = ASTSentinel()
    codigo = "def f() -> None:\n    try:\n        pass\n    except Exception as e:\n        pass\n"
    v = s.analizar(codigo, prod=False)
    assert any("pass" in e for e in v.errs)


def test_sentinel_import_ok() -> None:
    s = ASTSentinel()
    v = s.analizar("import json\nfrom pathlib import Path\nx = 1\n", prod=False)
    assert not any("import:" in e for e in v.errs)


def test_sentinel_linea_sin_deuda() -> None:
    s = ASTSentinel()
    v = s.analizar("def f() -> int:\n    return 1\n", prod=False)
    assert not any("deuda" in w for w in v.warns)


def test_sentinel_deuda_todo() -> None:
    s = ASTSentinel()
    v = s.analizar("# TODO: arreglar esto\nx = 1\n", prod=False)
    assert any("deuda" in w for w in v.warns)


# ── mochila providers/base ───────────────────────────────────


def test_provider_error() -> None:
    e = ProviderError("msg", "provider", 500)
    assert e.provider == "provider"
    assert e.status_code == 500
    assert str(e) == "msg"


def test_provider_abstracto() -> None:
    with pytest.raises(TypeError):
        Provider()


def test_provider_elipsis_via_super() -> None:
    class _Parcial(Provider):
        @property
        def nombre(self) -> str:
            r = super().nombre
            if r is None:
                return "p"
            return r

        @property
        def timeout(self) -> int:
            r = super().timeout
            if r is None:
                return 0
            return r

        async def chat(self, modelo, mensajes, stream=False, tools=None, max_tokens=4096, temperature=0.0):
            r = await super().chat(modelo, mensajes, stream, tools, max_tokens, temperature)
            if r is None:
                yield {"ok": True}

        async def health(self) -> dict:
            r = await super().health()
            if r is None:
                return {}
            return r

    p = _Parcial()
    assert p.nombre == "p"
    assert p.timeout == 0
    import inspect

    assert inspect.isasyncgenfunction(p.chat)
    assert inspect.iscoroutinefunction(p.health)

    async def _probar():
        async for x in p.chat("m", []):
            assert x == {"ok": True}
        assert await p.health() == {}

    asyncio.run(_probar())


def test_provider_props_abstractas() -> None:
    class _P(Provider):
        @property
        def nombre(self) -> str:
            return "p"

        @property
        def timeout(self) -> int:
            return 30

        async def chat(self, modelo, mensajes, stream=False, tools=None, max_tokens=4096, temperature=0.0):
            yield {}

        async def health(self) -> dict:
            return {}

    p = _P()
    assert p.nombre == "p"
    assert p.timeout == 30


# ── mochila status_endpoint ──────────────────────────────────


def test_fs_bug_status() -> None:
    r = _fs_bug_status()
    assert "estado" in r
    assert "archivos_criticos_perdidos" in r


def test_ram_info_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Proc:
        def __init__(self) -> None:
            self.stdout = b"              total        used        free\nMem:              16          14           2\n"

        async def communicate(self):
            return self.stdout, b""

    class _Cmd:
        def __init__(self, *a, **k) -> None:
            pass

        async def communicate(self):
            return _Proc().stdout, b""

    async def _fake_exec(*a, **k):
        return _Cmd()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", _fake_exec)
    r = asyncio.run(_ram_info())
    assert r["total_gb"] == 16
    assert r["usado_gb"] == 14
    assert r["riesgo"] == "medio"


def test_ram_info_sin_linea_mem(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Cmd:
        async def communicate(self):
            return b"Swap: 1 2 3\n", b""

    async def _fake_exec(*a, **k):
        return _Cmd()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", _fake_exec)
    assert asyncio.run(_ram_info()) == {"error": "free -g not available"}


def test_ram_info_file_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake(*a, **k):
        raise FileNotFoundError("free no existe")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", _fake)
    assert asyncio.run(_ram_info()) == {"error": "free not available"}


def test_ram_info_error(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Proc:
        async def communicate(self):
            msg = "roto"
            raise RuntimeError(msg)

    async def _fake(*a, **k):
        return _Proc()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", _fake)
    assert asyncio.run(_ram_info()) == {"error": "free -g not available"}


def test_timer_status_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Proc:
        async def communicate(self):
            return b"active\n", b""

    async def _fake(*a, **k):
        return _Proc()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", _fake)
    assert asyncio.run(_timer_status("svc")) == "active"


def test_timer_status_error(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake(*a, **k):
        msg = "roto"
        raise RuntimeError(msg)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", _fake)
    assert asyncio.run(_timer_status("svc")) == "unknown"


def test_system_status(monkeypatch: pytest.MonkeyPatch) -> None:
    class _CB:
        def estado(self, p: str) -> str:
            return "closed"

    class _CT:
        def resumen_hoy(self) -> dict:
            return {"coste": 1}

    class _Router:
        rutas: ClassVar[dict] = {"a": 1}

    async def _ram():
        return {"total_gb": 16}

    async def _alem():
        return {"global": "ok"}

    async def _tun():
        return {"tunnel_active": False}

    async def _timer(n):
        return "active"

    monkeypatch.setattr("core.mochila.status_endpoint._ram_info", _ram)
    monkeypatch.setattr("core.mochila.status_endpoint._alemania_status", _alem)
    monkeypatch.setattr("core.mochila.status_endpoint._tunnel_status", _tun)
    monkeypatch.setattr("core.mochila.status_endpoint._timer_status", _timer)
    r = asyncio.run(system_status({"p1": "x"}, _CT(), _CB(), 3, _Router()))
    assert r["mochila"]["providers"] == ["p1"]
    assert r["mochila"]["tools"] == 3
    assert r["ram"]["total_gb"] == 16
    assert r["timers"]["guard"] == "active"


def test_alemania_status(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    from core.mochila import status_endpoint as se

    f = Path(str(tmp_path)) / ".nervioso" / "alertas" / "estado_alemania.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps({"global": "ok", "ips": {"x": 1}}))
    monkeypatch.setattr(se.Path, "home", staticmethod(lambda: Path(str(tmp_path))))
    r = asyncio.run(se._alemania_status())
    assert r["global"] == "ok"


def test_alemania_status_error(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    from core.mochila import status_endpoint as se

    monkeypatch.setattr(se.Path, "home", staticmethod(lambda: Path(str(tmp_path)) / "no-existe-home"))
    r = asyncio.run(se._alemania_status())
    assert r == {"global": "unknown", "ips": {}, "servicios": {}}


def test_tunnel_status(monkeypatch: pytest.MonkeyPatch) -> None:
    from core.mochila import status_endpoint as se

    class _Proc:
        async def communicate(self):
            return b"active\n", b""

    async def _exec(*a, **k):
        return _Proc()

    class _Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, url: str):
            return type("R", (), {"status_code": 200})()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", _exec)
    monkeypatch.setattr(se.httpx, "AsyncClient", lambda *a, **k: _Client())
    r = asyncio.run(se._tunnel_status())
    assert r == {"tunnel_active": True, "searxng_accessible": True}


def test_tunnel_status_error(monkeypatch: pytest.MonkeyPatch) -> None:
    from core.mochila import status_endpoint as se

    async def _exec(*a, **k):
        msg = "no systemctl"
        raise FileNotFoundError(msg)

    class _Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, url: str):
            msg = "sin searxng"
            raise ConnectionError(msg)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", _exec)
    monkeypatch.setattr(se.httpx, "AsyncClient", lambda *a, **k: _Client())
    r = asyncio.run(se._tunnel_status())
    assert r == {"tunnel_active": False, "searxng_accessible": False}


# ── mochila vram_scheduler ───────────────────────────────────


def test_vram_detect_max(monkeypatch: pytest.MonkeyPatch) -> None:
    class _R:
        returncode = 0
        stdout = "24576\n"

    monkeypatch.setattr(vram_mod.subprocess, "run", lambda *a, **k: _R())
    assert VRAMAwareScheduler._detect_max_vram(100) == 24576


def test_vram_detect_max_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def _roto(*a, **k):
        msg = "no nvidia"
        raise FileNotFoundError(msg)

    monkeypatch.setattr(vram_mod.subprocess, "run", _roto)
    assert VRAMAwareScheduler._detect_max_vram(100) == 100


def test_vram_detect_max_na() -> None:
    class _R:
        returncode = 0
        stdout = "N/A\n"

    vram_mod.subprocess.run = lambda *a, **k: _R()
    try:
        assert VRAMAwareScheduler._detect_max_vram(100) == 100
    finally:
        vram_mod.subprocess.run = __import__('subprocess').run


def test_vram_available_mb() -> None:
    s = VRAMAwareScheduler.__new__(VRAMAwareScheduler)
    s.max_mb = 100
    s._current_mb = 30
    assert s.available_mb() == 70


def test_vram_estimar_overhead() -> None:
    # 2400 chars → (600)*0.002 = 1.2 → int = 1
    assert VRAMAwareScheduler.estimar_vram({"model": "otro", "prompt": "p" * 2400}) == 512 + 1


def test_vram_estimar() -> None:
    assert VRAMAwareScheduler.estimar_vram({"_vram_mb": "5000"}) == 5000
    assert VRAMAwareScheduler.estimar_vram({"model": "qwen2.5-coder:14b", "prompt": "x" * 400}) == 9000  # overhead int(0.2)=0
    assert VRAMAwareScheduler.estimar_vram({"model": "otro", "messages": "m" * 400}) == 512  # overhead 0


def test_vram_acquire_ok() -> None:
    async def _main():
        s = VRAMAwareScheduler.__new__(VRAMAwareScheduler)
        s.max_mb = 1000
        s._current_mb = 100
        s._queue = []
        s._active = {}
        s._lock = asyncio.Lock()
        rid = await s.acquire(500)
        assert rid is not None
        assert len(s._active) == 1
        return rid

    assert asyncio.run(_main()) is not None


def test_vram_acquire_ocupado() -> None:
    async def _main():
        s = VRAMAwareScheduler.__new__(VRAMAwareScheduler)
        s.max_mb = 1000
        s._current_mb = 100
        s._queue = []
        s._active = {"x": {}}
        s._lock = asyncio.Lock()
        assert await s.acquire(500) is None  # activo → None

    asyncio.run(_main())


def test_vram_acquire_sin_vram_timeout() -> None:
    async def _main():
        s = VRAMAwareScheduler.__new__(VRAMAwareScheduler)
        s.max_mb = 100
        s._current_mb = 100
        s._queue = []
        s._active = {}
        s._lock = asyncio.Lock()
        rid = await s.acquire(500, deadline_flex=0.1)
        assert rid is None  # timeout

    asyncio.run(_main())


def test_vram_release() -> None:
    async def _main():
        s = VRAMAwareScheduler.__new__(VRAMAwareScheduler)
        s._active = {"r1": {}}
        s._lock = asyncio.Lock()
        await s.release("r1")
        assert s._active == {}
        await s.release("no-existe")  # no lanza

    asyncio.run(_main())


def test_vram_sync_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Proc:
        returncode = 0

        async def communicate(self):
            return b"1024 MiB\n2048 MiB\n", b""

    async def _exec(*a, **k):
        return _Proc()

    class _Client:
        def __init__(self) -> None:
            self.calls = []

        async def get(self, url: str):
            self.calls.append(url)
            return type("R", (), {"status_code": 200, "json": lambda self: {"models": [{"name": "m1"}]}})()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", _exec)
    s = VRAMAwareScheduler.__new__(VRAMAwareScheduler)
    s._consecutive_smi_errors = 0
    s._scheduler_log = __import__("logging").getLogger("t")
    s._current_mb = 0
    s.max_mb = 10000
    s._hot_models = set()
    s._ollama_client = _Client()
    asyncio.run(s.sync_vram())
    assert s._current_mb == 3072
    assert s._hot_models == {"m1"}


def test_vram_sync_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Proc:
        returncode = 0

        async def communicate(self):
            msg = "lento"
            raise TimeoutError(msg)

    async def _exec(*a, **k):
        return _Proc()

    class _Client:
        async def get(self, url: str):
            return type("R", (), {"status_code": 500, "json": lambda: {}})()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", _exec)
    s = VRAMAwareScheduler.__new__(VRAMAwareScheduler)
    s._consecutive_smi_errors = 0
    s._scheduler_log = __import__("logging").getLogger("t")
    s._current_mb = 0
    s.max_mb = 10000
    s._ollama_client = _Client()
    asyncio.run(s.sync_vram())
    assert s._consecutive_smi_errors >= 1


def test_vram_sync_returncode_no_cero(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Proc:
        returncode = 1  # nvidia-smi falló

        async def communicate(self):
            return b"", b""

    async def _exec(*a, **k):
        return _Proc()

    class _Client:
        async def get(self, url: str):
            return type("R", (), {"status_code": 200, "json": lambda self: {"models": []}})()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", _exec)
    s = VRAMAwareScheduler.__new__(VRAMAwareScheduler)
    s._consecutive_smi_errors = 0
    s._scheduler_log = __import__("logging").getLogger("t")
    s._current_mb = 999
    s.max_mb = 10000
    s._hot_models = set()
    s._ollama_client = _Client()
    asyncio.run(s.sync_vram())
    assert s._current_mb == 999  # returncode != 0 → no actualiza


def test_vram_sync_kill_proc_error_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Proc:
        returncode = 0

        async def communicate(self):
            msg = "lento"
            raise TimeoutError(msg)

        async def kill(self) -> None:
            pass

        async def wait(self) -> None:
            pass

    async def _exec(*a, **k):
        return _Proc()

    class _Client:
        async def get(self, url: str):
            return type("R", (), {"status_code": 500, "json": lambda self: {}})()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", _exec)
    # proc.communicate lanza TimeoutError directamente (no wait_for)
    s = VRAMAwareScheduler.__new__(VRAMAwareScheduler)
    s._consecutive_smi_errors = 0
    s._scheduler_log = __import__("logging").getLogger("t")
    s._current_mb = 0
    s.max_mb = 10000
    s._hot_models = set()
    s._ollama_client = _Client()

    async def _wait_for(coro, tmo):
        return await coro

    monkeypatch.setattr(asyncio, "wait_for", _wait_for)
    asyncio.run(s.sync_vram())  # TimeoutError del communicate → kill → wait
    assert s._consecutive_smi_errors == 1


def test_vram_sync_kill_error_interno(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Proc:
        returncode = 0

        async def communicate(self):
            msg = "lento"
            raise TimeoutError(msg)

        async def kill(self) -> None:
            msg = "kill roto"
            raise OSError(msg)

        async def wait(self) -> None:
            pass

    async def _exec(*a, **k):
        return _Proc()

    class _Client:
        async def get(self, url: str):
            return type("R", (), {"status_code": 500, "json": lambda self: {}})()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", _exec)

    async def _wait_for(coro, tmo):
        return await coro

    monkeypatch.setattr(asyncio, "wait_for", _wait_for)
    s = VRAMAwareScheduler.__new__(VRAMAwareScheduler)
    s._consecutive_smi_errors = 0
    s._scheduler_log = __import__("logging").getLogger("t")
    s._current_mb = 0
    s.max_mb = 10000
    s._hot_models = set()
    s._ollama_client = _Client()
    asyncio.run(s.sync_vram())  # kill falla → log.debug
    assert s._consecutive_smi_errors == 1


def test_vram_acquire_boot_flujo_real(monkeypatch: pytest.MonkeyPatch) -> None:
    import core.mochila.vram_scheduler as vm

    original_sleep = asyncio.sleep

    async def _sleep_rapido(s: float) -> None:
        await original_sleep(0.01)

    monkeypatch.setattr(vm.asyncio, "sleep", _sleep_rapido)

    async def _main():
        s = VRAMAwareScheduler.__new__(VRAMAwareScheduler)
        s.max_mb = 1000
        s._current_mb = 0
        s._queue = []
        s._active = {}
        s._lock = asyncio.Lock()

        task = asyncio.create_task(s.acquire_boot_vram(500))
        await original_sleep(0.02)
        fut, _mb, _dl, _data = s._queue[0]
        fut.set_result("boot-ok")
        result = await task
        assert result is True
        await original_sleep(0.05)
        assert "boot-ok" not in s._active  # _release completó

    asyncio.run(_main())


def test_vram_sync_communicate_error_kill_roto(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Proc:
        returncode = 0

        async def communicate(self):
            msg = "exploto"
            raise RuntimeError(msg)

        def kill(self):  # sync → lanza directamente (sin await)
            msg = "kill roto"
            raise OSError(msg)

        async def wait(self) -> None:
            pass

    async def _exec(*a, **k):
        return _Proc()

    class _Client:
        async def get(self, url: str):
            return type("R", (), {"status_code": 500, "json": lambda self: {}})()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", _exec)

    async def _wait_for(coro, tmo):
        return await coro

    monkeypatch.setattr(asyncio, "wait_for", _wait_for)
    s = VRAMAwareScheduler.__new__(VRAMAwareScheduler)
    s._consecutive_smi_errors = 0
    s._scheduler_log = __import__("logging").getLogger("t")
    s._current_mb = 0
    s.max_mb = 10000
    s._hot_models = set()
    s._ollama_client = _Client()
    asyncio.run(s.sync_vram())  # RuntimeError del communicate → except Exception → kill sync lanza → except e2
    assert s._consecutive_smi_errors == 1
    async def _exec(*a, **k):
        msg = "roto"
        raise RuntimeError(msg)

    class _Client:
        async def get(self, url: str):
            return type("R", (), {"status_code": 500, "json": lambda: {}})()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", _exec)
    s = VRAMAwareScheduler.__new__(VRAMAwareScheduler)
    s._consecutive_smi_errors = 2
    s._scheduler_log = __import__("logging").getLogger("t")
    s._current_mb = 0
    s.max_mb = 10000
    s._ollama_client = _Client()
    asyncio.run(s.sync_vram())
    assert s._consecutive_smi_errors == 3
    assert s._current_mb == 10000  # bloqueado


def test_vram_loop_once(monkeypatch: pytest.MonkeyPatch) -> None:
    s = VRAMAwareScheduler.__new__(VRAMAwareScheduler)
    s._scheduler_log = __import__("logging").getLogger("t")
    s._current_mb = 0
    s.max_mb = 1000
    s._active = {}
    s._queue = []
    s._lock = asyncio.Lock()
    s._ollama_client = type("C", (), {"get": lambda self, url: type("R", (), {"status_code": 200, "json": lambda self: {"models": []}})()})()

    class _Proc:
        returncode = 0

        async def communicate(self):
            return b"", b""

    async def _exec(*a, **k):
        return _Proc()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", _exec)
    asyncio.run(s._scheduler_loop_once())  # no lanza


def test_vram_loop_once_procesa_cola(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Proc:
        returncode = 0

        async def communicate(self):
            return b"", b""

    async def _exec(*a, **k):
        return _Proc()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", _exec)

    async def _main():
        s = VRAMAwareScheduler.__new__(VRAMAwareScheduler)
        s._scheduler_log = __import__("logging").getLogger("t")
        s._current_mb = 0
        s.max_mb = 1000
        s._active = {}
        s._lock = asyncio.Lock()
        s._hot_models = set()
        s._ollama_client = type("C", (), {"get": lambda self, url: type("R", (), {"status_code": 200, "json": lambda self: {"models": []}})()})()

        fut = asyncio.get_running_loop().create_future()
        s._queue = [(fut, 500, time.time() + 100, {"model": "m"})]
        await s._scheduler_loop_once()
        assert fut.done()
        assert len(s._active) == 1

    asyncio.run(_main())


def test_vram_start_stop_close(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _once() -> None:
        pass

    monkeypatch.setattr(VRAMAwareScheduler, "_scheduler_loop_once", _once)

    async def _main():
        s = VRAMAwareScheduler.__new__(VRAMAwareScheduler)
        s._task = None

        class _Client:
            async def aclose(self) -> None:
                pass

        s._ollama_client = _Client()
        await s.start_loop()
        assert s._task is not None
        await s.stop_loop()
        await s.close()

    asyncio.run(_main())


def test_vram_init_real(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    class _R:
        returncode = 0
        stdout = "24576\n"

    class _Client:
        async def aclose(self) -> None:
            pass

    import sys
    import types

    fake_httpx = types.ModuleType("httpx")
    fake_httpx.AsyncClient = lambda *a, **k: _Client()
    monkeypatch.setitem(sys.modules, "httpx", fake_httpx)
    monkeypatch.setattr(vram_mod.subprocess, "run", lambda *a, **k: _R())
    s = VRAMAwareScheduler(default_max_mb=100, queue_timeout=5.0)
    assert s.max_mb == 24576
    assert s.queue_timeout == 5.0
    assert s._hot_models == set()
    assert s._active == {}


def test_vram_sync_kill_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Proc:
        returncode = 0

        async def communicate(self):
            msg = "lento"
            raise TimeoutError(msg)

        async def kill(self) -> None:
            pass

        async def wait(self) -> None:
            pass

    async def _exec(*a, **k):
        return _Proc()

    class _Client:
        async def get(self, url: str):
            return type("R", (), {"status_code": 500, "json": lambda self: {}})()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", _exec)
    monkeypatch.setattr(asyncio, "wait_for", lambda coro, timeout: (_ for _ in ()).throw(TimeoutError("t")))
    s = VRAMAwareScheduler.__new__(VRAMAwareScheduler)
    s._consecutive_smi_errors = 0
    s._scheduler_log = __import__("logging").getLogger("t")
    s._current_mb = 0
    s.max_mb = 10000
    s._hot_models = set()
    s._ollama_client = _Client()
    asyncio.run(s.sync_vram())
    assert s._consecutive_smi_errors == 1


def test_vram_sync_kill_error(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Proc:
        returncode = 0

        async def communicate(self):
            msg = "lento"
            raise TimeoutError(msg)

        async def kill(self) -> None:
            msg = "kill roto"
            raise OSError(msg)

        async def wait(self) -> None:
            pass

    async def _exec(*a, **k):
        return _Proc()

    class _Client:
        async def get(self, url: str):
            return type("R", (), {"status_code": 500, "json": lambda self: {}})()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", _exec)
    monkeypatch.setattr(asyncio, "wait_for", lambda coro, timeout: (_ for _ in ()).throw(TimeoutError("t")))
    s = VRAMAwareScheduler.__new__(VRAMAwareScheduler)
    s._consecutive_smi_errors = 0
    s._scheduler_log = __import__("logging").getLogger("t")
    s._current_mb = 0
    s.max_mb = 10000
    s._hot_models = set()
    s._ollama_client = _Client()
    asyncio.run(s.sync_vram())  # kill falla → log.debug, no lanza
    assert s._consecutive_smi_errors == 1


def test_vram_acquire_timeout() -> None:
    async def _main():
        s = VRAMAwareScheduler.__new__(VRAMAwareScheduler)
        s.max_mb = 100
        s._current_mb = 100
        s._queue = []
        s._active = {}
        s._lock = asyncio.Lock()
        rid = await s.acquire(500, deadline_flex=0.05)
        assert rid is None

    asyncio.run(_main())


def test_vram_acquire_boot_timeout() -> None:
    async def _main():
        s = VRAMAwareScheduler.__new__(VRAMAwareScheduler)
        s.max_mb = 100
        s._current_mb = 100
        s._queue = []
        s._active = {}
        s._lock = asyncio.Lock()
        assert await s.acquire_boot_vram(500) is False

    asyncio.run(_main())


def test_vram_acquire_boot_real() -> None:
    async def _main():
        s = VRAMAwareScheduler.__new__(VRAMAwareScheduler)
        s.max_mb = 1000
        s._current_mb = 0
        s._queue = []
        s._active = {}
        s._lock = asyncio.Lock()
        s._ollama_client = type("C", (), {"aclose": lambda self: None})()
        # proceso de cola manual antes de adquirir
        fut = asyncio.get_running_loop().create_future()
        s._queue.append((fut, 500, time.time() + 120, {"model": "static_boot_service"}))
        fut.set_result("boot-ok")
        rid = await asyncio.wait_for(fut, timeout=1.0)
        assert rid == "boot-ok"
        s._active[rid] = {"mb": 500}
        # cubrir _release: esperamos 0.05s en vez de 3
        import core.mochila.vram_scheduler as vm

        original = vm.asyncio.sleep

        async def _sleep_rapido(s: float) -> None:
            await original(min(s, 0.05))

        vm.asyncio.sleep = _sleep_rapido
        try:
            # simular el create_task de _release
            async def _release() -> None:
                try:
                    await vm.asyncio.sleep(3.0)
                finally:
                    async with s._lock:
                        s._active.pop(rid, None)

            task = asyncio.create_task(_release())
            await task
            assert rid not in s._active
        finally:
            vm.asyncio.sleep = original

    asyncio.run(_main())


def test_vram_loop_con_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _once(self) -> None:
        pass

    llamadas = {"n": 0}

    async def _sleep(s: float) -> None:
        llamadas["n"] += 1
        if llamadas["n"] >= 2:
            raise asyncio.CancelledError

    monkeypatch.setattr(VRAMAwareScheduler, "_scheduler_loop_once", _once)
    monkeypatch.setattr(asyncio, "sleep", _sleep)
    s = VRAMAwareScheduler.__new__(VRAMAwareScheduler)

    async def _main():
        with pytest.raises(asyncio.CancelledError):
            await s._scheduler_loop()

    asyncio.run(_main())
    assert llamadas["n"] == 2


def test_vram_stop_loop_sin_task() -> None:
    async def _main():
        s = VRAMAwareScheduler.__new__(VRAMAwareScheduler)
        s._task = None
        await s.stop_loop()  # no lanza

    asyncio.run(_main())


def test_vram_loop_once_con_fut_done(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Proc:
        returncode = 0

        async def communicate(self):
            return b"", b""

    async def _exec(*a, **k):
        return _Proc()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", _exec)

    async def _main():
        s = VRAMAwareScheduler.__new__(VRAMAwareScheduler)
        s._scheduler_log = __import__("logging").getLogger("t")
        s._current_mb = 0
        s.max_mb = 1000
        s._active = {}
        s._lock = asyncio.Lock()
        s._hot_models = set()
        s._ollama_client = type("C", (), {"get": lambda self, url: type("R", (), {"status_code": 200, "json": lambda self: {"models": []}})()})()

        fut = asyncio.get_running_loop().create_future()
        fut.set_result("ya")
        s._queue = [(fut, 500, time.time() + 100, {"model": "m"})]
        await s._scheduler_loop_once()  # fut done → no lo procesa
        assert len(s._active) == 0

    asyncio.run(_main())


def test_vram_loop_once_error(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _exec(*a, **k):
        msg = "roto"
        raise RuntimeError(msg)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", _exec)

    async def _main():
        s = VRAMAwareScheduler.__new__(VRAMAwareScheduler)
        s._scheduler_log = __import__("logging").getLogger("t")
        s._current_mb = 0
        s.max_mb = 1000
        s._active = {}
        s._lock = asyncio.Lock()
        s._hot_models = set()
        s._ollama_client = type("C", (), {"get": lambda self, url: type("R", (), {"status_code": 200, "json": lambda self: {"models": []}})()})()
        await s._scheduler_loop_once()  # error → log.error, no lanza

    asyncio.run(_main())

def test_vram_sync_error_tres(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _exec(*a, **k):
        msg = "roto"
        raise RuntimeError(msg)

    class _Client:
        async def get(self, url: str):
            return type("R", (), {"status_code": 500, "json": lambda self: {}})()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", _exec)
    s = VRAMAwareScheduler.__new__(VRAMAwareScheduler)
    s._consecutive_smi_errors = 2
    s._scheduler_log = __import__("logging").getLogger("t")
    s._current_mb = 0
    s.max_mb = 10000
    s._hot_models = set()
    s._ollama_client = _Client()
    asyncio.run(s.sync_vram())
    assert s._consecutive_smi_errors == 3
    assert s._current_mb == 10000  # bloqueado
