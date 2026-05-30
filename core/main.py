#!/usr/bin/env python3
"""
URA API v2 - Current version of the API
"""

from typing import Any

from core.logging_config import get_logger
from fastapi import APIRouter

logger = get_logger("api_v2", log_dir="./logs")

router = APIRouter(prefix="/v2", tags=["v2"])


@router.get("/")
async def v2_root() -> dict[str, Any]:
    """Root endpoint v2"""
    return {
        "version": "2.0.0",
        "status": "active",
        "features": [
            "OAuth2 authentication",
            "RBAC authorization",
            "Streaming responses",
            "GraphQL API",
        ],
    }


@router.post("/chat")
async def v2_chat(message: str, model: str = "llama3.2:1b") -> dict[str, Any]:
    """Chat endpoint v2"""
    logger.info(f"v2 chat request: {message[:50]}...")
    return {"response": f"Response from v2: {message}", "model": model, "version": "2.0.0"}


@router.get("/health")
async def v2_health() -> dict[str, str]:
    """Health check v2"""
    return {"status": "healthy", "version": "2.0.0"}
