"""Tests de cobertura P3 para motor/core/document_quality.py — ramas faltantes.

Cubre detect_language (cache, fallback fast, lingua OK/None), _fast_lang_detect
(todos los empates), content_type (code/html/table/documentation/article),
extract_publication_date (2 formatos, inválido), is_stale, adaptive_threshold
y doc_id_from_text (prefix).
"""

from __future__ import annotations

import sys
import types
from unittest import mock

import pytest

import motor.core.document_quality as dq


def _fake_lingua_module() -> types.ModuleType:
    """Módulo lingua fake con Language y LanguageDetectorBuilder."""
    mod = types.ModuleType("lingua")
    mod.Language = mock.Mock(
        ENGLISH="en", SPANISH="es", FRENCH="fr", GERMAN="de",
        PORTUGUESE="pt", ITALIAN="it", CATALAN="ca", DUTCH="nl",
    )
    mod.LanguageDetectorBuilder = mock.Mock()
    return mod


class TestDetectLanguage:
    def test_vacio(self) -> None:
        assert dq.detect_language("   ") == "unknown"

    def test_cache_hit(self, monkeypatch: pytest.MonkeyPatch) -> None:
        dq._LANG_CACHE.clear()
        dq._LANG_CACHE["abc"] = "zz"
        monkeypatch.setattr(dq, "hashlib", mock.Mock(md5=lambda s, usedforsecurity=False: mock.Mock(hexdigest=lambda: "abc")))
        assert dq.detect_language("texto de prueba") == "zz"
        dq._LANG_CACHE.clear()

    def test_lingua_ok(self, monkeypatch: pytest.MonkeyPatch) -> None:
        dq._LANG_CACHE.clear()
        lingua = _fake_lingua_module()
        detected = mock.Mock(iso_code_639_1=types.SimpleNamespace(name="spanish"))
        lingua.LanguageDetectorBuilder.from_languages.return_value = mock.Mock(
            build=lambda: mock.Mock(detect_language_of=lambda s: detected)
        )
        monkeypatch.setitem(sys.modules, "lingua", lingua)
        assert dq.detect_language("Hola mundo") == "spanish"
        dq._LANG_CACHE.clear()

    def test_lingua_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        dq._LANG_CACHE.clear()
        lingua = _fake_lingua_module()
        lingua.LanguageDetectorBuilder.from_languages.return_value = mock.Mock(
            build=lambda: mock.Mock(detect_language_of=lambda s: None)
        )
        monkeypatch.setitem(sys.modules, "lingua", lingua)
        assert dq.detect_language("Hola mundo") == "unknown"
        dq._LANG_CACHE.clear()

    def test_lingua_exception_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        dq._LANG_CACHE.clear()
        monkeypatch.setattr("builtins.__import__", lambda name, *a, **k: (_ for _ in ()).throw(ImportError("no lingua")))
        assert dq.detect_language("The quick brown fox") == "en"
        dq._LANG_CACHE.clear()

    def test_fast_lang_detect_todos(self) -> None:
        assert dq._fast_lang_detect("the and you that for are") == "en"
        assert dq._fast_lang_detect("que los las del por con una") == "es"
        assert dq._fast_lang_detect("zzz qqq www") == "unknown"
        assert dq._fast_lang_detect("") == "unknown"


class TestSourceReliability:
    def test_vacio(self) -> None:
        assert dq.source_reliability("") == 0.5

    def test_dominio_conocido(self) -> None:
        assert dq.source_reliability("https://github.com/foo") == 0.9
        assert dq.source_reliability("https://wikipedia.org/x") == 0.8
        assert dq.source_reliability("https://medium.com/x") == 0.5

    def test_dominio_desconocido(self) -> None:
        assert dq.source_reliability("https://example.com") == 0.5


class TestExtractPublicationDate:
    def test_iso_formato(self) -> None:
        assert dq.extract_publication_date("fecha 2024-03-15 publicada") == "2024-03-15T00:00:00"

    def test_dmy_formato(self) -> None:
        assert dq.extract_publication_date("publicado 15/03/2024 aqui") == "2024-03-15T00:00:00"

    def test_fecha_invalida(self) -> None:
        assert dq.extract_publication_date("2024-13-45") is None

    def test_sin_fecha(self) -> None:
        assert dq.extract_publication_date("sin fechas aqui") is None


class TestContentType:
    def test_code_fence(self) -> None:
        assert dq.content_type("```python\nx = 1\n```") == "code"

    def test_code_keywords(self) -> None:
        assert dq.content_type("def foo():\n    return 1") == "code"
        assert dq.content_type("import os\nimport sys") == "code"

    def test_html(self) -> None:
        assert dq.content_type("<html><body><p>hola</p></body></html>") == "html"

    def test_table(self) -> None:
        assert dq.content_type("| a | b |\n|---|---|\n| 1 | 2 |") == "table"

    def test_documentation(self) -> None:
        largo = "x" * 250
        assert dq.content_type("\n".join([largo] * 60)) == "documentation"

    def test_article(self) -> None:
        assert dq.content_type("texto normal corto") == "article"


class TestIsStale:
    def test_none(self) -> None:
        assert dq.is_stale(None) is True

    def test_viejo(self) -> None:
        assert dq.is_stale("2020-01-01T00:00:00+00:00", ttl_days=30) is True

    def test_reciente(self) -> None:
        assert dq.is_stale("2099-01-01T00:00:00+00:00", ttl_days=30) is False

    def test_sin_tz(self) -> None:
        assert dq.is_stale("2099-01-01T00:00:00") is False

    def test_invalido(self) -> None:
        assert dq.is_stale("no es fecha") is True
        assert dq.is_stale(None) is True


class TestAdaptiveThreshold:
    def test_vacio(self) -> None:
        assert dq.adaptive_threshold([]) == 0.5

    def test_plano(self) -> None:
        assert dq.adaptive_threshold([0.5, 0.5, 0.5]) == 0.5

    def test_diverso(self) -> None:
        t = dq.adaptive_threshold([0.1, 0.9], base_threshold=0.5)
        assert t >= 0.5

    def test_clamp(self) -> None:
        t = dq.adaptive_threshold([0.0, 1.0], base_threshold=0.5, std_factor=3.0)
        assert t <= 1.0

    def test_min_threshold(self) -> None:
        t = dq.adaptive_threshold([0.5, 0.51], base_threshold=0.5, min_threshold=0.2)
        assert t >= 0.2

    def test_std_unico(self) -> None:
        assert dq.adaptive_threshold([0.7]) == 0.5  # len 1 → stdev 0 → base


class TestDocId:
    def test_determinista(self) -> None:
        a = dq.doc_id_from_text("hola")
        b = dq.doc_id_from_text("hola")
        assert a == b
        assert a.startswith("doc_")
        assert dq.doc_id_from_text("hola", prefix="x") != a
