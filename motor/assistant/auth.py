"""Auth middleware para el API del asistente conversacional."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from motor.assistant.config import config

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from fastapi import Request
    from starlette.responses import Response


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        if not config.auth_enabled:
            return await call_next(request)

        if request.url.path.startswith("/api/v1/chat"):
            auth_header = request.headers.get("Authorization", "")
            if not auth_header.startswith("Bearer ") or auth_header[7:] != config.api_key:
                return JSONResponse(
                    status_code=401,
                    content={"error": "Unauthorized", "message": "API key inválida o ausente"},
                )

        return await call_next(request)
