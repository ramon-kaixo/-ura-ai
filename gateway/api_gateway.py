#!/usr/bin/env python3
"""
API Gateway FastAPI — INACTIVO actualmente.

Estado: ACTIVO=False
Razón: nginx en puerto 8091 hace de proxy en producción.

Conservado porque tiene diseño moderno (FastAPI + httpx async)
por si se decide reactivar como gateway nativo en lugar de nginx.

Importadores actuales: 0
Última modificación: 2026-05-06

NO BORRAR — código de referencia para futura implementación.
NO confundir con archive/duplicados/api_gateway_root_legacy.py (Flask, buggy).

Sistema de API Gateway URA
Gateway único para todas las APIs
"""

import asyncio

import httpx
from core.logging_config import get_logger
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

logger = get_logger("api_gateway", log_dir="./logs")

app = FastAPI(title="URA API Gateway")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuración de servicios
SERVICES = {
    "ura-api": "http://localhost:8000",
    "ura-ollama": "http://localhost:11434",
    "ura-metrics": "http://localhost:8000",
}

# Rate limiting (simple)
rate_limits = {}


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """Middleware de rate limiting"""
    client_ip = request.client.host
    current_time = asyncio.get_event_loop().time()

    if client_ip in rate_limits:
        last_request, count = rate_limits[client_ip]
        if current_time - last_request < 1:  # 1 segundo
            if count >= 100:  # 100 requests por segundo
                raise HTTPException(status_code=429, detail="Rate limit exceeded")
            rate_limits[client_ip] = (last_request, count + 1)
        else:
            rate_limits[client_ip] = (current_time, 1)
    else:
        rate_limits[client_ip] = (current_time, 1)

    response = await call_next(request)
    return response


@app.get("/")
async def root():
    """Root endpoint"""
    return {"name": "URA API Gateway", "version": "1.0.0", "services": list(SERVICES.keys())}


@app.get("/health")
async def health_check():
    """Health check del gateway"""
    return {"status": "healthy", "services": SERVICES}


@app.api_route("/api/{service}/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy_request(service: str, path: str, request: Request):
    """
    Proxy requests a servicios backend

    Args:
        service: Nombre del servicio
        path: Path del endpoint
        request: Request original
    """
    if service not in SERVICES:
        raise HTTPException(status_code=404, detail=f"Service not found: {service}")

    target_url = f"{SERVICES[service]}/{path}"

    # Construir headers excluyendo headers del host
    headers = dict(request.headers)
    headers.pop("host", None)

    async with httpx.AsyncClient() as client:
        try:
            if request.method == "GET":
                response = await client.get(
                    target_url, headers=headers, params=request.query_params
                )
            elif request.method == "POST":
                body = await request.body()
                response = await client.post(target_url, headers=headers, content=body)
            elif request.method == "PUT":
                body = await request.body()
                response = await client.put(target_url, headers=headers, content=body)
            elif request.method == "DELETE":
                response = await client.delete(target_url, headers=headers)
            else:
                raise HTTPException(status_code=405, detail="Method not allowed")

            return Response(
                content=response.content,
                status_code=response.status_code,
                headers=dict(response.headers),
            )

        except httpx.RequestError as e:
            logger.error(f"Error proxying request: {e}")
            raise HTTPException(status_code=503, detail="Service unavailable")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("gateway.api_gateway:app", host="0.0.0.0", port=8080, reload=True)
