"""Cobertura 100x100 de knowledge/engine/extraction_service.py (TASK-20260815-003).

Cubre MetadataExtractionService (queue_extract, get_queue_status, start/stop_worker,
_run_extractor, _publish_extracted, extract, extract_path) y las funciones de
módulo (_worker_loop, _claim_next_job*, _esperar_proceso, _process_item,
_extract_in_worker, _write_job_*, _mark_job_failed, _read_job_result) con
mocks de sqlite (FakeConn), registry, store, eventbus y multiprocessing.
"""

from __future__ import annotations

import json  # noqa: F401
import sqlite3  # noqa: F401
import threading
import time  # noqa: F401
from pathlib import Path
from types import SimpleNamespace  # noqa: F401
from typing import Any, ClassVar

import pytest

import knowledge.engine.extraction_service as es
from knowledge.engine.eventbus import MetadataExtracted, get_bus  # noqa: F401
from knowledge.engine.extraction_service import (  # noqa: F401 (re-exports para splits)
    _EXTRACTION_SEMAPHORES,
    MetadataExtractionService,
    _claim_next_job,
    _claim_next_job_fallback,
    _esperar_proceso,
    _extract_in_worker,
    _get_semaphore,
    _guess_mime,
    _mark_job_failed,
    _process_item,
    _read_job_result,
    _worker_loop,
    _write_job_done,
    _write_job_fail,
)
from knowledge.engine.extractors.base import ExtractionResult
from knowledge.engine.ontology.internal import AssetSource, AssetType, KnowledgeAsset  # noqa: F401

_DB = Path("/tmp/extraction-service-test.db")


class FakeRow:
    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def keys(self) -> Any:
        return self._data.keys()


class FakeConn:
    def __init__(self, responses: dict[str, list[Any]] | None = None) -> None:
        self._responses = responses or {}
        self._raise_on: list[tuple[str, Exception]] = []
        self._current: Any = None
        self.executed: list[tuple[str, tuple[Any, ...]]] = []
        self.commits = 0
        self.rollbacks = 0
        self.closed = False
        self.lastrowid = 42

    def add_raise(self, pattern: str, exc: Exception) -> None:
        self._raise_on.append((pattern, exc))

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> FakeConn:
        self.executed.append((sql, params))
        for i, (pattern, exc) in enumerate(self._raise_on):
            if pattern in sql:
                del self._raise_on[i]
                raise exc
        self._current = None
        for pattern, results in self._responses.items():
            if pattern in sql and results:
                self._current = results.pop(0)
                break
        return self

    def fetchone(self) -> Any:
        return self._current

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1

    def close(self) -> None:
        self.closed = True


class FakeExtractor:
    id = "fake_extractor"
    version = "1.0.0"
    supported_mime_types: ClassVar[list[str]] = ["text/markdown", "text/plain"]

    def __init__(self, result: ExtractionResult | None = None) -> None:
        self._result = result or ExtractionResult()
        self.last_source: AssetSource | None = None

    def extract(self, source: AssetSource) -> ExtractionResult:
        self.last_source = source
        return self._result


class FakeRegistry:
    def __init__(self, extractors: list[Any] | None = None) -> None:
        self._extractors = extractors or []

    def get_for_mime(self, mime: str) -> list[Any]:
        return [e for e in self._extractors if mime in e.supported_mime_types]


class FakeStore:
    def __init__(self) -> None:
        self.saved: list[Any] = []
        self.result = True

    def save_asset(self, asset: Any) -> bool:
        self.saved.append(asset)
        return self.result


class FakeSem:
    def __init__(self, acquired: bool = True) -> None:
        self._acquired = acquired
        self.acquires = 0
        self.releases = 0

    def acquire(self, blocking: bool = True, timeout: float | None = None) -> bool:
        self.acquires += 1
        return self._acquired

    def release(self) -> None:
        self.releases += 1


class FakeProc:
    def __init__(
        self,
        alive: bool = True,
        alive_after_join: bool = False,
        alive_after_terminate: bool = False,
    ) -> None:
        self._alive = alive
        self._alive_after_join = alive_after_join
        self._alive_after_terminate = alive_after_terminate
        self.started = False
        self.joins = 0
        self.terminated = 0
        self.killed = 0
        self.closed = False

    def start(self) -> None:
        self.started = True

    def join(self, timeout: float | None = None) -> None:
        self.joins += 1
        if not self._alive_after_join:
            self._alive = False

    def is_alive(self) -> bool:
        return self._alive

    def terminate(self) -> None:
        self.terminated += 1
        if not self._alive_after_terminate:
            self._alive = False

    def kill(self) -> None:
        self.killed += 1
        self._alive = False

    def close(self) -> None:
        self.closed = True


class FakeThread:
    def __init__(self, alive: bool = False) -> None:
        self._alive = alive
        self.joined = False

    def is_alive(self) -> bool:
        return self._alive

    def join(self, timeout: float | None = None) -> None:
        self.joined = True


class FakeBusRaising:
    def publish(self, event: Any) -> None:
        raise RuntimeError("bus down")


def _service(
    extractors: list[Any] | None = None,
    store: FakeStore | None = None,
) -> MetadataExtractionService:
    return MetadataExtractionService(
        _DB,
        registry=FakeRegistry(extractors or []),
        store=store or FakeStore(),
    )


def _run_loop_in_thread(
    monkeypatch: pytest.MonkeyPatch,
    conn: FakeConn | None = None,
    stop: threading.Event | None = None,
) -> tuple[threading.Thread, threading.Event]:
    monkeypatch.setattr(es, "_POLL_INTERVAL", 0.01)
    if stop is None:
        stop = threading.Event()
    monkeypatch.setattr(es, "open_db", lambda p: conn if conn is not None else FakeConn())
    thread = threading.Thread(
        target=_worker_loop,
        args=(_DB, FakeRegistry(), FakeStore(), stop, {}, threading.Lock(), 1),
        daemon=True,
    )
    thread.start()
    return thread, stop


