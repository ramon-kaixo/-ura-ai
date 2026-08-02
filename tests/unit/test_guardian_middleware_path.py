"""Tests para core/mochila/guardian_middleware.py y core/path_setup.py."""
from __future__ import annotations

from unittest import mock

import pytest


class TestGuardianMiddleware:
    def _app(self, guardian_result: dict | None = None):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from core.mochila.guardian_middleware import GuardianMiddleware

        app = FastAPI()

        @app.get("/health")
        async def health():
            return {"status": "ok"}

        @app.get("/v1/models")
        async def models():
            return {"models": []}

        @app.get("/protected")
        async def protected():
            return {"ok": True}

        @app.post("/protected")
        async def protected_post():
            return {"ok": True}

        app.add_middleware(GuardianMiddleware)
        return TestClient(app)

    def test_paths_permitidos(self) -> None:
        client = self._app()
        assert client.get("/health").status_code == 200
        assert client.get("/v1/models").status_code == 200

    def test_get_no_guardado(self) -> None:
        client = self._app()
        r = client.get("/protected")
        assert r.status_code == 200

    def test_post_permitido(self) -> None:
        with mock.patch("core.mochila.guardian_middleware.guardian") as g:
            g.ejecutar.return_value = {"permitido": True}
            client = self._app()
            r = client.post("/protected")
        assert r.status_code == 200

    def test_post_bloqueado(self) -> None:
        with mock.patch("core.mochila.guardian_middleware.guardian") as g:
            g.ejecutar.return_value = {"permitido": False, "razon": "regla x"}
            client = self._app()
            r = client.post("/protected")
        assert r.status_code == 403
        data = r.json()
        assert data["error"] == "Guardian bloqueo la operacion"
        assert data["detalle"]["permitido"] is False

    def test_init_guardian(self) -> None:
        with mock.patch("core.mochila.guardian_middleware.guardian") as g:
            g.estado.return_value = {"reglas": ["r1", "r2"]}
            from core.mochila.guardian_middleware import init_guardian

            out = init_guardian()
        assert out == {"guardian": {"reglas": ["r1", "r2"]}}


class TestPathSetup:
    def test_setup_path_agrega_raiz(self, monkeypatch) -> None:
        import core.path_setup as ps

        monkeypatch.setattr(ps, "_PROJECT_ROOT", None)
        ps.setup_path()
        root = ps.get_project_root()
        assert root.name == "ura_ia_1972"
        assert str(root) in __import__("sys").path

    def test_setup_path_idempotente(self, monkeypatch) -> None:
        import sys

        import core.path_setup as ps

        monkeypatch.setattr(ps, "_PROJECT_ROOT", None)
        ps.setup_path()
        n_paths = len(sys.path)
        ps.setup_path()
        assert len(sys.path) == n_paths

    def test_get_project_root_sin_setup(self, monkeypatch) -> None:
        import core.path_setup as ps

        monkeypatch.setattr(ps, "_PROJECT_ROOT", None)
        root = ps.get_project_root()
        assert root is not None
