"""Utility functions for LLM router."""

from __future__ import annotations

from typing import Any

from motor.core.llm.base import FALLBACK_EMBEDDING_DIMENSION

log = __import__("logging").getLogger(__name__)


def _classify_error(exception: Exception) -> str:
    try:
        import httpx
    except ImportError:
        return "error"
    if isinstance(exception, httpx.TimeoutException):
        return "timeout"
    if isinstance(exception, httpx.ConnectError):
        return "connection_error"
    if isinstance(exception, httpx.RemoteProtocolError):
        return "protocol_error"
    if isinstance(exception, httpx.HTTPStatusError):
        return f"http_{exception.response.status_code}"
    return f"unexpected:{type(exception).__name__}"


def _is_error_result(result: Any) -> bool:
    return isinstance(result, str) and result.startswith("Error:")


def _build_error(method: str, error: str) -> Any:
    if method in ("embed", "embed_async"):
        return [[0.0] * FALLBACK_EMBEDDING_DIMENSION]
    return f"Error: {error}"
