"""Tests para core/mochila/routes/memoria.py — endpoints de memoria."""
from __future__ import annotations

from types import SimpleNamespace
from unittest import mock


class TestMemoriaRouter:
    def _app(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from core.mochila.routes.memoria import create_memoria_router

        app = FastAPI()
        app.include_router(create_memoria_router(mock.Mock()))
        return TestClient(app)

    def test_ingestar_video_ok(self, tmp_path) -> None:
        f = tmp_path / "video.mp4"
        f.write_bytes(b"x")
        client = self._app()
        r = client.post("/memoria/ingestar/video", json={"path": str(f)})
        assert r.status_code == 200
        assert r.json()["status"] == "stub"

    def test_ingestar_video_no_encontrado(self) -> None:
        client = self._app()
        r = client.post("/memoria/ingestar/video", json={"path": "/tmp/no_existe_video_xyz.mp4"})
        assert r.status_code == 404

    def test_analizar(self) -> None:
        with mock.patch("core.mochila.routes.memoria.analizar", mock.AsyncMock(return_value={"fases": ["saber"]})) as analizar:
            client = self._app()
            r = client.post("/memoria/analizar", json={"peticion": "explica X"})
        assert r.status_code == 200
        assert r.json() == {"fases": ["saber"]}
        analizar.assert_awaited_once_with("explica X")

    def test_sintetizar(self) -> None:
        with mock.patch("core.mochila.routes.memoria.sintetizar", mock.AsyncMock(return_value={"informe": "resumen"})):
            client = self._app()
            r = client.post("/memoria/sintetizar", json={"peticion": "que es Y"})
        assert r.status_code == 200
        assert r.json() == {"informe": "resumen"}

    def test_fases(self) -> None:
        for fase, fn_name in [("saber", "fase_saber"), ("hacer", "fase_hacer"), ("comprar", "fase_comprar")]:
            with mock.patch(f"core.mochila.routes.memoria.{fn_name}", mock.AsyncMock(return_value={"fase": fase})):
                client = self._app()
                r = client.post(f"/memoria/fase/{fase}", json={"keywords": "kw"})
            assert r.status_code == 200
            assert r.json() == {"fase": fase}

    def test_vigilancia_parte(self) -> None:
        with mock.patch("core.mochila.routes.memoria.generar_parte", mock.AsyncMock(return_value={"fuentes_vigiladas": 2})):
            client = self._app()
            r = client.get("/memoria/vigilancia/parte")
        assert r.status_code == 200
        assert r.json() == {"fuentes_vigiladas": 2}

    def test_consultar(self) -> None:
        with mock.patch("core.mochila.routes.memoria.memoria_consultar", mock.AsyncMock(return_value={"desde": "memoria"})):
            client = self._app()
            r = client.post("/memoria/consultar", json={"query": "q", "forzar_web": True})
        assert r.status_code == 200
        assert r.json() == {"desde": "memoria"}

    def test_health_ok(self) -> None:
        client_obj = mock.Mock()
        client_obj.get_collection.return_value = SimpleNamespace(points_count=42, config=SimpleNamespace(params=SimpleNamespace(vectors="768")))
        with mock.patch("core.memoria.qdrant_store._get_client", return_value=client_obj):
            client = self._app()
            r = client.get("/memoria/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert data["puntos"] == 42

    def test_health_error(self) -> None:
        with mock.patch("core.memoria.qdrant_store._get_client", side_effect=OSError("no qdrant")):
            client = self._app()
            r = client.get("/memoria/health")
        assert r.status_code == 200
        assert r.json()["status"] == "error"

    def test_ingestar(self) -> None:
        with mock.patch("core.mochila.routes.memoria.procesar_inbox_completo", mock.AsyncMock(return_value={"status": "stub"})):
            client = self._app()
            r = client.post("/memoria/ingestar")
        assert r.status_code == 200
        assert r.json() == {"status": "stub"}
