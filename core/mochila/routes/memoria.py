from pathlib import Path

from fastapi import APIRouter, HTTPException

from core.memoria.analizador import analizar
from core.memoria.consulta import consultar as memoria_consultar
from core.memoria.ingesto import procesar_inbox_completo
from core.memoria.rastreadores.comprar import fase_comprar
from core.memoria.rastreadores.hacer import fase_hacer
from core.memoria.rastreadores.saber import fase_saber
from core.memoria.sintetizador import sintetizar
from core.memoria.vigilante import generar_parte
from core.mochila.models import (
    AnalizarRequest,
    ConsultaRequest,
    FaseRequest,
    SintesisRequest,
    VideoIngestRequest,
)


def create_memoria_router(state) -> APIRouter:
    router = APIRouter()

    @router.post("/memoria/ingestar/video")
    async def memoria_ingestar_video(body: VideoIngestRequest):
        ruta = Path(body.path)
        if not ruta.exists():  # noqa: ASYNC240
            raise HTTPException(status_code=404, detail=f"No encontrado: {body.path}")
        return {"status": "stub", "detail": "pipeline_video no implementado"}

    @router.post("/memoria/analizar")
    async def memoria_analizar(body: AnalizarRequest):
        return await analizar(body.peticion)

    @router.post("/memoria/sintetizar")
    async def memoria_sintetizar(body: SintesisRequest):
        return await sintetizar(body.peticion)

    @router.post("/memoria/fase/saber")
    async def memoria_fase_saber(body: FaseRequest):
        return await fase_saber(body.keywords)

    @router.post("/memoria/fase/hacer")
    async def memoria_fase_hacer(body: FaseRequest):
        return await fase_hacer(body.keywords)

    @router.post("/memoria/fase/comprar")
    async def memoria_fase_comprar(body: FaseRequest):
        return await fase_comprar(body.keywords)

    @router.get("/memoria/vigilancia/parte")
    async def memoria_vigilancia_parte():
        return await generar_parte()

    @router.post("/memoria/consultar")
    async def memoria_consultar_endpoint(body: ConsultaRequest):
        return await memoria_consultar(body.query, body.forzar_web)

    @router.get("/memoria/health")
    async def memoria_health():
        try:
            from core.memoria.qdrant_store import _get_client

            client = _get_client()
            info = client.get_collection("ideas")
            return {
                "status": "ok",
                "coleccion": "ideas",
                "puntos": info.points_count,
                "vectores": str(info.config.params.vectors),
            }
        except Exception as e:
            return {"status": "error", "detail": str(e)}

    @router.post("/memoria/ingestar")
    async def memoria_ingestar():
        return await procesar_inbox_completo()

    return router
