"""Helpers compartidos para tests de motor.core.qdrant_client (splits).

Re-exports marcados con noqa F401: los splits los importan desde aquí.
"""
# ruff: noqa: I001
from __future__ import annotations

import asyncio  # noqa: F401
import hashlib  # noqa: F401
import json  # noqa: F401
import sys  # noqa: F401
from types import ModuleType, SimpleNamespace  # noqa: F401
from unittest.mock import AsyncMock, MagicMock, patch  # noqa: F401

import httpx  # noqa: F401
import pytest


import motor.core.qdrant_client as qc_mod  # noqa: F401
from motor.core.config import UraConfig
from motor.core.qdrant_client import (  # noqa: F401
    COLECCION_DOCUMENTOS,
    COLECCION_INCIDENTES,
    COLECCION_TRANSACCIONES,
    VECTOR_SIZE_EMBEDDING,
    QdrantClient,
    URAQdrantClient,
)

class UnexpectedResponse(Exception):
    """Fake de qdrant_client.http.exceptions.UnexpectedResponse."""


class FakeDistance:
    COSINE = "Cosine"


class FakeVectorParams:
    def __init__(self, size: int | None = None, distance: str | None = None) -> None:
        self.size = size
        self.distance = distance


class FakePointStruct:
    def __init__(self, id: int | None = None, vector: list | None = None, payload: dict | None = None) -> None:  # noqa: A002
        self.id = id
        self.vector = vector
        self.payload = payload


class FakeMatchValue:
    def __init__(self, value: object | None = None) -> None:
        self.value = value


class FakeFieldCondition:
    def __init__(self, key: str | None = None, match: FakeMatchValue | None = None) -> None:
        self.key = key
        self.match = match


class FakeFilter:
    def __init__(self, must: list | None = None) -> None:
        self.must = must


class FakeFilterSelector:
    def __init__(self, filter: FakeFilter | None = None) -> None:  # noqa: A002
        self.filter = filter


class FakeModels:
    Distance = FakeDistance
    VectorParams = FakeVectorParams
    PointStruct = FakePointStruct
    MatchValue = FakeMatchValue
    FieldCondition = FakeFieldCondition
    Filter = FakeFilter
    FilterSelector = FakeFilterSelector


class FakeQC:
    """Fake de la librería nativa qdrant_client.QdrantClient."""

    def __init__(self, host: str | None = None, port: int | None = None, timeout: int | None = None) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self.existing: list[str] = []
        self.created: list[str] = []
        self.upserted: tuple[str, list] | None = None
        self.deleted: tuple[str, object] | None = None
        self.scroll_result: tuple[list, object] | None = None
        self.query_result: object | None = None
        self.fail_get_collections = False
        self.fail_upsert = False
        self.fail_query = False
        self.fail_delete = False
        self.fail_scroll = False
        self.get_collection_error: Exception | None = None

    def get_collections(self) -> list:
        if self.fail_get_collections:
            raise RuntimeError("conn refused")
        return []

    def get_collection(self, name: str) -> bool:
        if self.get_collection_error is not None:
            raise self.get_collection_error
        if name in self.existing:
            return True
        raise UnexpectedResponse("not found")

    def recreate_collection(self, collection_name: str | None = None, vectors_config: object | None = None) -> None:
        self.created.append(collection_name or "")

    def upsert(self, collection_name: str | None = None, points: list | None = None) -> None:
        if self.fail_upsert:
            raise RuntimeError("upsert fail")
        self.upserted = (collection_name or "", points or [])

    def query_points(self, collection_name: str | None = None, query: object | None = None, limit: int | None = None) -> object:
        if self.fail_query:
            raise RuntimeError("query fail")
        return self.query_result

    def delete(self, collection_name: str | None = None, points_selector: object | None = None) -> None:
        if self.fail_delete:
            raise RuntimeError("delete fail")
        self.deleted = (collection_name or "", points_selector)

    def scroll(self, collection_name: str | None = None, limit: int | None = None) -> tuple[list, object]:
        if self.fail_scroll:
            raise RuntimeError("scroll fail")
        return self.scroll_result or ([], None)


class FakeResp:
    def __init__(self, status_code: int = 200, json_data: dict | None = None) -> None:
        self.status_code = status_code
        self._json = json_data or {}

    def json(self) -> dict:
        return self._json


def make_config() -> MagicMock:
    config = MagicMock(spec=UraConfig)
    config.qdrant_host = "127.0.0.1"
    config.qdrant_port = 6333
    config.schema_version = "3.1"
    return config


@pytest.fixture
def native_modules() -> dict:
    """Módulos fake de la librería qdrant_client (imports intrafunción)."""
    qdrant = ModuleType("qdrant_client")
    http = ModuleType("qdrant_client.http")
    exceptions = ModuleType("qdrant_client.http.exceptions")
    models = ModuleType("qdrant_client.http.models")
    exceptions.UnexpectedResponse = UnexpectedResponse
    models.VectorParams = FakeVectorParams
    models.Distance = FakeDistance
    models.PointStruct = FakePointStruct
    models.MatchValue = FakeMatchValue
    models.FieldCondition = FakeFieldCondition
    models.Filter = FakeFilter
    models.FilterSelector = FakeFilterSelector
    http.exceptions = exceptions
    http.models = models
    qdrant.http = http
    qdrant.QdrantClient = FakeQC
    return {
        "qdrant_client": qdrant,
        "qdrant_client.http": http,
        "qdrant_client.http.exceptions": exceptions,
        "qdrant_client.http.models": models,
    }


@pytest.fixture
def client() -> QdrantClient:
    with patch.object(QdrantClient, "_conectar"):
        return QdrantClient(make_config())


# ===================================================================
# _conectar — nativo, REST fallback, degradado
# ===================================================================

