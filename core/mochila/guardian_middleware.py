"""Middleware del Guardian para la Mochila."""
import logging
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import JSONResponse
from core.guardian_openclaw import get_guardian

log = logging.getLogger("mochila.guardian")
guardian = get_guardian()


class GuardianMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        method = request.method
        if path in ("/health", "/v1/models", "/metrics", "/breaker"):
            return await call_next(request)
        if method in ("POST", "PUT", "DELETE"):
            accion = f"{method} {path}"
            resultado = guardian.ejecutar(accion, path=path, method=method)
            if not resultado.get("permitido", True):
                log.warning(f"Guardian bloqueo {accion}: {resultado.get('razon','')}")
                return JSONResponse(status_code=403, content={"error": "Guardian bloqueo la operacion", "detalle": resultado})
        return await call_next(request)



def init_guardian():
    estado = guardian.estado()
    log.info(f"GuardianOpenClaw: {len(estado.get('reglas',[]))} reglas activas")
    return {"guardian": estado}
