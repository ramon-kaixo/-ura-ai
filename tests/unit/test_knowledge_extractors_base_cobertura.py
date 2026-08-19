"""Tests de cobertura para knowledge/engine/extractors/base.py."""

from __future__ import annotations

import pytest

from knowledge.engine.extractors.base import (
    MAX_STREAM_CHUNK,
    ExtractionResult,
    ExtractorRegistry,
    _check_import,
    _hash_stream,
    get_registry,
)


class FakeExtractor:
    id = "fake"
    version = "1.0.0"
    supported_mime_types = ["text/plain", "text/markdown"]
    cost = "O(1)"

    def extract(self, source) -> ExtractionResult:
        return ExtractionResult()


def test_max_stream_chunk() -> None:
    assert MAX_STREAM_CHUNK == 64 * 1024


def test_hash_stream(tmp_path) -> None:
    p = tmp_path / "f.bin"
    p.write_bytes(b"hola" * 10000)
    h, size = _hash_stream(p)
    assert size == 40000
    assert len(h) == 64


def test_hash_stream_no_existe(tmp_path) -> None:
    with pytest.raises(FileNotFoundError):
        _hash_stream(tmp_path / "no.bin")


def test_check_import_disponible() -> None:
    assert _check_import("json") is True


def test_check_import_no_disponible() -> None:
    assert _check_import("modulo_inexistente_xyz") is False


def test_check_import_con_package() -> None:
    assert _check_import("modulo_inexistente_xyz", package="pkg") is False


def test_extraction_result_defaults() -> None:
    r = ExtractionResult()
    assert r.asset is None
    assert r.warnings == []
    assert r.errors == []
    assert r.duration_ms == 0.0


def test_extraction_result_completo() -> None:
    r = ExtractionResult(warnings=["w"], errors=["e"], duration_ms=1.5)
    assert r.warnings == ["w"]
    assert r.errors == ["e"]
    assert r.duration_ms == 1.5


def test_registry_register_y_get() -> None:
    reg = ExtractorRegistry()
    ext = FakeExtractor()
    reg.register(ext)
    assert reg.get("fake") is ext
    assert reg.get("no") is None


def test_registry_por_mime_y_lista() -> None:
    reg = ExtractorRegistry()
    ext = FakeExtractor()
    reg.register(ext)
    assert reg.get_for_mime("text/plain") == [ext]
    assert reg.get_for_mime("application/pdf") == []
    assert reg.list() == [ext]
    assert reg.count == 1


def test_registry_singleton() -> None:
    assert get_registry() is get_registry()
    assert isinstance(get_registry(), ExtractorRegistry)


def test_extractor_protocol_contrato() -> None:
    from knowledge.engine.extractors.base import Extractor

    assert Extractor.extract is not None
