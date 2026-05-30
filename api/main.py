#!/usr/bin/env python3
"""
URA REST API
FastAPI-based REST API for URA
"""

import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field

# Agregar ruta al directorio padre para importar módulos
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.agente_policia_v2 import AgentePoliciaV2
from core.logging_config import get_logger
from core.ram_manager import read_ram
from core.central_router import get_central_router

# Configuración
logger = get_logger("ura_api", log_dir="./logs")
app = FastAPI(
    title="URA API",
    description="Universal Reasoning Assistant REST API",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Key Security
API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


async def get_api_key(api_key: str = Depends(API_KEY_HEADER)):
    """Validar API Key"""
    if api_key is None:
        return None  # Allow requests without API key for now
    # TODO: Implementar validación real de API key
    return api_key


# Modelos Pydantic
class ChatRequest(BaseModel):
    message: str = Field(..., description="User message")
    model: str | None = Field("llama3.2:1b", description="Ollama model to use")
    context: dict[str, Any] | None = Field(default_factory=dict, description="Additional context")


class ChatResponse(BaseModel):
    response: str
    model: str
    timestamp: datetime
    processing_time: float


class HealthResponse(BaseModel):
    status: str
    ollama_connected: bool
    memory_available_gb: float
    cpu_usage_percent: float


class ConfigResponse(BaseModel):
    version: str
    model: str
    security_mode: str
    features: list[str]


# Instancias globales
router = None
policia = None
ram_manager_data = None


def initialize_components():
    """Inicializar componentes de URA"""
    global router, policia, ram_manager_data
    try:
        router = get_central_router()
        policia = AgentePoliciaV2()
        ram_manager_data = read_ram()
        logger.info("Componentes de URA inicializados correctamente")
    except Exception as e:
        logger.error(f"Error inicializando componentes: {e}")


# Inicializar al startup
@app.on_event("startup")
async def startup_event():
    """Evento de startup"""
    logger.info("URA API iniciando...")
    initialize_components()


@app.on_event("shutdown")
async def shutdown_event():
    """Evento de shutdown"""
    logger.info("URA API apagándose...")


# Endpoints
@app.get("/", response_model=dict[str, str])
async def root():
    """Root endpoint"""
    return {"name": "URA API", "version": "2.0.0", "status": "running"}


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    import psutil

    ollama_connected = False  # TODO: Implementar check real

    return HealthResponse(
        status="healthy" if ollama_connected else "degraded",
        ollama_connected=ollama_connected,
        memory_available_gb=psutil.virtual_memory().available / (1024**3),
        cpu_usage_percent=psutil.cpu_percent(),
    )


@app.get("/config", response_model=ConfigResponse)
async def get_config():
    """Obtener configuración actual"""
    return ConfigResponse(
        version="2.0.0",
        model="llama3.2:1b",
        security_mode="APPLE",
        features=[
            "central_router",
            "security_policy",
            "privacy_scrubber",
            "ram_monitor",
            "self_healing",
        ],
    )


@app.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    background_tasks: BackgroundTasks,
    api_key: str | None = Depends(get_api_key),
):
    """Endpoint de chat principal"""
    start_time = datetime.now()

    try:
        # Validar comando con policía
        is_blocked, reason = policia.check_command(request.message)
        if is_blocked:
            raise HTTPException(status_code=403, detail=f"Command blocked: {reason}")

        # Procesar con central_router
        result = await router.process_request(request.message)
        response = result.get("response", "")

        processing_time = (datetime.now() - start_time).total_seconds()

        # Log request en background
        background_tasks.add_task(
            logger.log_ollama_request, request.model, request.message, processing_time, True
        )

        return ChatResponse(
            response=response,
            model=request.model,
            timestamp=datetime.now(),
            processing_time=processing_time,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error procesando chat: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/security/validate")
async def validate_command(command: str):
    """Validar comando sin ejecutar"""
    try:
        is_blocked, reason = policia.check_command(command)
        return {"command": command, "is_blocked": is_blocked, "reason": reason}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/metrics")
async def get_metrics():
    """Obtener métricas del sistema"""
    import psutil

    return {
        "cpu_usage_percent": psutil.cpu_percent(),
        "memory_usage_percent": psutil.virtual_memory().percent,
        "memory_available_gb": psutil.virtual_memory().available / (1024**3),
        "disk_usage_percent": psutil.disk_usage("/").percent,
        "timestamp": datetime.now().isoformat(),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True, log_level="info")
