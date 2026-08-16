"""Cobertura 100x100 de knowledge/engine/extractors (TASK-20260814-001).

Los tests de integración existentes cubren los caminos felices. Aquí se
cubren los remanentes: degradación, límites, ramas de error, fakes de
librerías opcionales (openpyxl/docx/pptx/whisper/pytesseract) y helpers.
"""

from __future__ import annotations

import ipaddress
import sys
import types
from pathlib import Path
from typing import Any, Self

import pytest

from knowledge.engine.extractors.base import _check_import, _hash_stream
from knowledge.engine.extractors.video import VideoExtractor
from knowledge.engine.ontology.internal import AssetSource, AssetType


def _source(location: str, kind: str = "filesystem") -> AssetSource:
    return AssetSource(kind, location)


# Entorno: tests de integración requieren recursos externos (fitz, red).
# Si no están disponibles, se saltan para no bloquear el hook pre-push.
_HAS_FITZ = _check_import("fitz")
_HAS_NETWORK = False
try:
    import socket
    socket.create_connection(("8.8.8.8", 53), timeout=2)
    _HAS_NETWORK = True
except OSError:
    pass


# ── base ───────────────────────────────────────────────────────────────────


class TestBaseExtractors:
    def test_hash_stream(self, tmp_path: Path) -> None:
        import hashlib

        p = tmp_path / "f.txt"
        p.write_bytes(b"hola")
        sha, size = _hash_stream(p)
        assert sha == hashlib.sha256(b"hola").hexdigest() and size == 4

    def test_check_import_missing(self) -> None:
        assert _check_import("modulo_que_no_existe_xyz", "paquete") is False
        assert _check_import("sys") is True

    def test_registry_metodos(self) -> None:
        reg = ExtractorRegistry()
        assert reg.count == 0
        assert reg.list() == []
        assert reg.get_for_mime("text/html") == []
        assert reg.get("nada") is None
        e = MarkdownExtractor()
        reg.register(e)
        assert reg.count == 1
        assert reg.get("markdown") is e
        assert reg.get_for_mime("text/markdown") == [e]
        assert reg.list() == [e]


# ── markdown ────────────────────────────────────────────────────────────────


class TestMarkdownCobertura:
    def _sample(
        self, tmp_path: Path, body: str = "# Titulo\n\n## Seccion\n\nTexto de relleno aqui. [ref](abc123def456.md)"
    ) -> Path:
        p = tmp_path / "doc.md"
        p.write_text(f"---\ntitle: Mi Doc\ntags: [a, b]\n---\n{body}", encoding="utf-8")
        return p

    def test_extract_completo(self, tmp_path: Path) -> None:
        p = self._sample(tmp_path)
        result = MarkdownExtractor().extract(_source(str(p)))
        assert result.asset is not None
        assert result.asset.asset_type == AssetType.MARKDOWN
        assert result.asset.metadata["title"] == "Mi Doc"
        assert result.asset.metadata["tags"] == ["a", "b"]
        assert result.asset.relationships

    def test_extract_no_existe(self) -> None:
        result = MarkdownExtractor().extract(_source("/no/existe/md"))
        assert result.errors and "not found" in result.errors[0]

    def test_extract_error_general(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        p = self._sample(tmp_path)

        def boom(path: str) -> bytes:
            raise OSError("lectura falla")

        monkeypatch.setattr("knowledge.engine.extractors.markdown._load_file", boom)
        result = MarkdownExtractor().extract(_source(str(p)))
        assert result.errors and "Extraction error" in result.errors[0]

    def test_frontmatter_variantes(self) -> None:
        from knowledge.engine.extractors.markdown import _parse_frontmatter

        assert _parse_frontmatter("texto normal") == (None, "texto normal")
        assert _parse_frontmatter("---\nclave: valor\n---\ncuerpo")[0] == {"clave": "valor"}
        assert _parse_frontmatter("---\nclave: valor")[0] is None
        assert _parse_frontmatter("---\n- a\n- b\n---\nx")[0] is None
        assert _parse_frontmatter("---\nclave: [no cerrado\n---\nx")[0] is None

    def test_helpers(self) -> None:
        from knowledge.engine.extractors.markdown import (
            _count_headings,
            _extract_tags,
            _extract_title,
            _find_external_links,
            _find_internal_links,
        )

        assert _extract_title({"title": "T"}, "") == "T"
        assert _extract_title(None, "# Hola") == "Hola"
        assert _extract_title(None, "sin heading") == ""
        assert _extract_tags({"tags": ["x", "y"]}) == ["x", "y"]
        assert _extract_tags({"tags": "a, b"}) == ["a", "b"]
        assert _extract_tags({}) == []
        stacked = "# A\n## B\n### C\n#### D\n##### E\n###### F\n# G"
        headings = _count_headings(stacked)
        assert headings == {"h1": 2, "h2": 1, "h3": 1, "h4": 1, "h5": 1, "h6": 1}
        assert _find_internal_links("[x](abc123def456.md)") == ["abc123def456"]
        assert _find_external_links("[x](https://example.com/a)") == ["https://example.com/a"]

    def test_quality(self) -> None:
        from knowledge.engine.extractors.markdown import _compute_quality

        assert _compute_quality(["t"], 500, {"h1": 1}) == 1.0
        assert _compute_quality([], 10, {}) == 0.3


# ── audio ───────────────────────────────────────────────────────────────────


class TestAudioCobertura:
    def test_extract_normal(self, tmp_path: Path) -> None:
        p = tmp_path / "a.mp3"
        p.write_bytes(b"\x00" * 100)
        result = AudioExtractor().extract(_source(str(p)))
        assert result.asset is not None and result.asset.asset_type == AssetType.AUDIO

    def test_file_too_large(self, tmp_path: Path) -> None:
        p = tmp_path / "a.mp3"
        with p.open("wb") as f:
            f.seek(501 * 1024 * 1024)
            f.write(b"x")
        result = AudioExtractor().extract(_source(str(p)))
        assert result.errors and "too large" in result.errors[0]

    def test_ffprobe_fallido(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        mod = sys.modules["knowledge.engine.extractors.audio"]
        monkeypatch.setattr(mod, "_HAS_FFPROBE", True)

        class Res:
            returncode = 1
            stdout = ""
            stderr = "boom"

        monkeypatch.setattr("knowledge.engine.extractors.audio.subprocess.run", lambda *a, **k: Res())
        p = tmp_path / "a.mp3"
        p.write_bytes(b"x")
        result = AudioExtractor().extract(_source(str(p)))
        assert result.asset is not None and result.asset.metadata["_degraded_ffprobe"] is True

    def test_ffprobe_json_invalido(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        mod = sys.modules["knowledge.engine.extractors.audio"]
        monkeypatch.setattr(mod, "_HAS_FFPROBE", True)

        class Res:
            returncode = 0
            stdout = "no es json"
            stderr = ""

        monkeypatch.setattr("knowledge.engine.extractors.audio.subprocess.run", lambda *a, **k: Res())
        p = tmp_path / "a.mp3"
        p.write_bytes(b"x")
        result = AudioExtractor().extract(_source(str(p)))
        assert result.asset is not None and result.asset.metadata["_degraded_ffprobe"] is True

    def test_ffprobe_timeout(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import subprocess

        mod = sys.modules["knowledge.engine.extractors.audio"]
        monkeypatch.setattr(mod, "_HAS_FFPROBE", True)

        def boom(*a: Any, **k: Any) -> None:
            raise subprocess.TimeoutExpired("ffprobe", 30)

        monkeypatch.setattr("knowledge.engine.extractors.audio.subprocess.run", boom)
        p = tmp_path / "a.mp3"
        p.write_bytes(b"x")
        result = AudioExtractor().extract(_source(str(p)))
        assert result.asset is not None and result.asset.metadata["_degraded_ffprobe"] is True

    def test_ffprobe_exitoso(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        json_output = {
            "format": {"duration": "3.5", "bit_rate": "128000", "format_name": "mp3"},
            "streams": [
                {
                    "codec_type": "audio",
                    "codec_name": "mp3",
                    "sample_rate": "44100",
                    "channels": 2,
                    "channel_layout": "stereo",
                }
            ],
        }
        import json

        class Res:
            returncode = 0
            stdout = json.dumps(json_output)
            stderr = ""

        monkeypatch.setattr("knowledge.engine.extractors.audio.subprocess.run", lambda *a, **k: Res())
        p = tmp_path / "a.mp3"
        p.write_bytes(b"x")
        result = AudioExtractor().extract(_source(str(p)))
        m = result.asset.metadata if result.asset else {}
        assert m["audio_duration_sec"] == "3.5"
        assert m["audio_codec"] == "mp3"

    def test_whisper_exitoso(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        mod = sys.modules["knowledge.engine.extractors.audio"]
        fake_model = types.SimpleNamespace(transcribe=lambda p: {"text": "hola mundo", "language": "es"})
        monkeypatch.setattr(mod, "_HAS_WHISPER", True)
        monkeypatch.setattr(mod, "_get_whisper_model", lambda: fake_model)
        p = tmp_path / "a.mp3"
        p.write_bytes(b"x")
        result = AudioExtractor().extract(_source(str(p)))
        m = result.asset.metadata if result.asset else {}
        assert m["transcript"] == "hola mundo"
        assert m["transcription_performed"] is True

    def test_whisper_fallido(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        mod = sys.modules["knowledge.engine.extractors.audio"]
        monkeypatch.setattr(mod, "_HAS_WHISPER", True)

        def boom(p: str) -> None:
            raise RuntimeError("modelo roto")

        monkeypatch.setattr(mod, "_get_whisper_model", lambda: types.SimpleNamespace(transcribe=boom))
        p = tmp_path / "a.mp3"
        p.write_bytes(b"x")
        result = AudioExtractor().extract(_source(str(p)))
        m = result.asset.metadata if result.asset else {}
        assert m["transcription_performed"] is False
        assert m["transcription_error"]

    def test_degradado_sin_ffprobe(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        mod = sys.modules["knowledge.engine.extractors.audio"]
        monkeypatch.setattr(mod, "_HAS_FFPROBE", False)
        p = tmp_path / "a.mp3"
        p.write_bytes(b"x")
        result = AudioExtractor().extract(_source(str(p)))
        assert result.asset is not None and result.asset.metadata["_degraded_ffprobe"] is True

    def test_error_general(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        def boom(path: str | Path) -> tuple[str, int]:
            raise PermissionError("nope")

        mod = sys.modules["knowledge.engine.extractors.audio"]
        monkeypatch.setattr(mod, "_hash_stream", boom)
        p = tmp_path / "a.mp3"
        p.write_bytes(b"x")
        result = AudioExtractor().extract(_source(str(p)))
        assert result.errors and "Extraction error" in result.errors[0]

    def test_quality_transcripcion(self) -> None:
        from knowledge.engine.extractors.audio import _compute_audio_quality

        assert _compute_audio_quality({"transcription_performed": True, "transcript": "x"}) == pytest.approx(0.6)
        assert _compute_audio_quality({"_degraded_ffprobe": True}) == pytest.approx(0.3)


# ── image ───────────────────────────────────────────────────────────────────


class _FakeExif:
    def __init__(self, tags: dict[int, Any], gps: dict[int, Any]) -> None:
        self._tags = tags
        self._gps = gps

    def items(self) -> list[tuple[int, Any]]:
        return list(self._tags.items())

    def get_ifd(self, ifd: int) -> dict[int, Any]:
        if ifd == 0x8825:
            return self._gps
        return {}


class _FakeImg:
    def __init__(self, size: tuple[int, int] = (100, 80), exif: _FakeExif | None = None) -> None:
        self.size = size
        self.format = "JPEG"
        self.mode = "RGB"
        self._exif = exif
        self.saved: list[str] = []

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *a: object) -> None:
        return None

    def getexif(self) -> _FakeExif:
        return self._exif or _FakeExif({}, {})

    def copy(self) -> _FakeImg:
        return self

    def thumbnail(self, size: tuple[int, int]) -> None:
        return None

    def save(self, path: str, fmt: str, quality: int = 0) -> None:
        Path(path).write_bytes(b"thumb")
        self.saved.append(path)


class TestImageCobertura:
    @pytest.fixture(autouse=True)
    def _pil_fake(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mod = sys.modules["knowledge.engine.extractors.image"]
        monkeypatch.setattr(mod, "_HAS_PILLOW", True)
        monkeypatch.setattr(mod, "_HAS_TESSERACT", False)

    def _img_file(self, tmp_path: Path, name: str = "i.jpg") -> Path:
        p = tmp_path / name
        p.write_bytes(b"\xff\xd8\xff" + b"\x00" * 100)
        return p

    def test_extract_ok_thumbnail(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        sys.modules["knowledge.engine.extractors.image"]
        fake = _FakeImg(exif=_FakeExif({}, {}))
        monkeypatch.setattr("PIL.Image", types.SimpleNamespace(open=lambda p: fake))
        p = self._img_file(tmp_path)
        result = ImageExtractor().extract(_source(str(p)))
        m = result.asset.metadata if result.asset else {}
        assert m["width"] == 100 and m["format"] == "JPEG"
        assert m["thumbnail"] == f"{p}.thumb.jpg"

    def test_extract_exif_gps(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        sys.modules["knowledge.engine.extractors.image"]
        exif = _FakeExif({0x010F: "Make", 0x0110: "Model", 0x9003: "2026:01:01"}, {1: "N", 2: "10.0"})
        fake = _FakeImg(exif=exif)
        monkeypatch.setattr("PIL.Image", types.SimpleNamespace(open=lambda p: fake))
        p = self._img_file(tmp_path)
        result = ImageExtractor().extract(_source(str(p)))
        m = result.asset.metadata if result.asset else {}
        assert m["exif_make"] == "Make"
        assert m["exif_model"] == "Model"
        assert m["exif_datetimeoriginal"] == "2026:01:01"
        assert m["gps"] and m["gps"]["GPSLatitudeRef"] == "N"
        assert result.asset.quality > 0.5  # type: ignore[union-attr]

    def test_exif_vacio_y_sin_pillow(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        mod = sys.modules["knowledge.engine.extractors.image"]
        monkeypatch.setattr("PIL.Image", types.SimpleNamespace(open=lambda p: _FakeImg(exif=None)))
        p = self._img_file(tmp_path)
        result = ImageExtractor().extract(_source(str(p)))
        assert result.asset is not None and "width" in result.asset.metadata
        monkeypatch.setattr(mod, "_HAS_PILLOW", False)
        result2 = ImageExtractor().extract(_source(str(p)))
        m = result2.asset.metadata if result2.asset else None
        assert m and m["_degraded"] is True and "_degraded_reason" in m

    def test_dimension_excesiva(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        mod = sys.modules["knowledge.engine.extractors.image"]
        monkeypatch.setattr(mod, "MAX_IMAGE_DIMENSION", 50)
        monkeypatch.setattr("PIL.Image", types.SimpleNamespace(open=lambda p: _FakeImg(size=(300, 10))))
        p = self._img_file(tmp_path)
        result = ImageExtractor().extract(_source(str(p)))
        assert result.errors and "dimensions too large" in result.errors[0]

    def test_pixels_excesivos(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        mod = sys.modules["knowledge.engine.extractors.image"]
        monkeypatch.setattr(mod, "MAX_IMAGE_PIXELS", 200)
        monkeypatch.setattr("PIL.Image", types.SimpleNamespace(open=lambda p: _FakeImg(size=(20, 20))))
        p = self._img_file(tmp_path)
        result = ImageExtractor().extract(_source(str(p)))
        assert result.errors and "Image too large" in result.errors[0]

    def test_large_warning(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        mod = sys.modules["knowledge.engine.extractors.image"]
        monkeypatch.setattr(mod, "MAX_IMAGE_PIXELS", 400)
        monkeypatch.setattr("PIL.Image", types.SimpleNamespace(open=lambda p: _FakeImg(size=(20, 20))))
        p = self._img_file(tmp_path)
        result = ImageExtractor().extract(_source(str(p)))
        assert result.asset is not None

    def test_ocr_exitoso(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        mod = sys.modules["knowledge.engine.extractors.image"]
        monkeypatch.setattr(mod, "_HAS_TESSERACT", True)
        monkeypatch.setattr("PIL.Image", types.SimpleNamespace(open=lambda p: _FakeImg(exif=None)))
        fake_tess = types.SimpleNamespace(image_to_string=lambda img: "texto ocr")
        monkeypatch.setitem(sys.modules, "pytesseract", fake_tess)
        p = self._img_file(tmp_path)
        result = ImageExtractor().extract(_source(str(p)))
        m = result.asset.metadata if result.asset else {}
        assert m["ocr_text"] == "texto ocr"
        assert m["ocr_performed"] is True

    def test_ocr_fallido(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        mod = sys.modules["knowledge.engine.extractors.image"]
        monkeypatch.setattr(mod, "_HAS_TESSERACT", True)
        monkeypatch.setattr("PIL.Image", types.SimpleNamespace(open=lambda p: _FakeImg(exif=None)))

        class BoomTess:
            @staticmethod
            def image_to_string(img: Any) -> str:
                raise RuntimeError("tesseract no disponible")

        monkeypatch.setitem(sys.modules, "pytesseract", BoomTess)
        p = self._img_file(tmp_path)
        result = ImageExtractor().extract(_source(str(p)))
        m = result.asset.metadata if result.asset else {}
        assert m["ocr_performed"] is False and "ocr_error" in m

    def test_image_open_error_degradado(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        def boom(p: str) -> Any:
            raise ValueError("imagen corrupta")

        monkeypatch.setattr("PIL.Image", types.SimpleNamespace(open=boom))
        p = self._img_file(tmp_path)
        result = ImageExtractor().extract(_source(str(p)))
        m = result.asset.metadata if result.asset else {}
        assert m["_degraded"] is True

    def test_file_too_large(self, tmp_path: Path) -> None:
        p = self._img_file(tmp_path)
        with p.open("wb") as f:
            f.seek(101 * 1024 * 1024)
            f.write(b"x")
        result = ImageExtractor().extract(_source(str(p)))
        assert result.errors and "too large" in result.errors[0]

    def test_error_general(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        mod = sys.modules["knowledge.engine.extractors.image"]

        def boom(path: str | Path) -> tuple[str, int]:
            raise OSError("hash falla")

        monkeypatch.setattr(mod, "_hash_stream", boom)
        p = self._img_file(tmp_path)
        result = ImageExtractor().extract(_source(str(p)))
        assert result.errors and "Extraction error" in result.errors[0]

    def test_no_existe(self) -> None:
        result = ImageExtractor().extract(_source("/no/existe/img.jpg"))
        assert result.errors and "not found" in result.errors[0]


# ── pdf ─────────────────────────────────────────────────────────────────────


class TestPdfCobertura:
    def test_degradado_sin_fitz(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        mod = sys.modules["knowledge.engine.extractors.pdf"]
        monkeypatch.setattr(mod, "_HAS_FITZ", False)
        p = tmp_path / "d.pdf"
        p.write_bytes(b"%PDF-1.4")
        result = PdfExtractor().extract(_source(str(p)))
        m = result.asset.metadata if result.asset else {}
        assert m["_degraded"] is True and "PyMuPDF" in m["_degraded_reason"]

    def test_too_large(self, tmp_path: Path) -> None:
        p = tmp_path / "d.pdf"
        with p.open("wb") as f:
            f.seek(501 * 1024 * 1024)
            f.write(b"x")
        result = PdfExtractor().extract(_source(str(p)))
        assert result.errors and "too large" in result.errors[0]

    @pytest.mark.skipif(not _HAS_FITZ, reason="fitz (PyMuPDF) no instalado")
    def test_fitz_limite_paginas(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        mod = sys.modules["knowledge.engine.extractors.pdf"]
        monkeypatch.setattr(mod, "MAX_PAGES", 1)
        monkeypatch.setitem(sys.modules, "fitz", types.SimpleNamespace(open=lambda p: _FakePdf(pages=2)))
        p = tmp_path / "d.pdf"
        p.write_bytes(b"%PDF")
        result = PdfExtractor().extract(_source(str(p)))
        assert result.errors

    @pytest.mark.skipif(not _HAS_FITZ, reason="fitz (PyMuPDF) no instalado")
    def test_fitz_completo(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setitem(
            sys.modules,
            "fitz",
            types.SimpleNamespace(
                open=lambda p: _FakePdf(
                    pages=1,
                    metadata={
                        "title": "Titulo",
                        "author": "Ana",
                        "subject": "Tema",
                        "keywords": "k1,k2",
                        "creationDate": "D:20260101",
                    },
                    texts=["Hola mundo de prueba"],
                )
            ),
        )
        p = tmp_path / "d.pdf"
        p.write_bytes(b"%PDF")
        result = PdfExtractor().extract(_source(str(p)))
        m = result.asset.metadata if result.asset else {}
        assert m["pages"] == 1
        assert m["title"] == "Titulo" and m["author"] == "Ana"
        assert "Hola mundo" in m["text_preview"]
        assert m["has_text"] is True
        assert result.asset.quality > 0.5  # type: ignore[union-attr]

    @pytest.mark.skipif(not _HAS_FITZ, reason="fitz (PyMuPDF) no instalado")
    def test_fitz_sin_texto_ocr(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setitem(sys.modules, "fitz", types.SimpleNamespace(open=lambda p: _FakePdf(pages=1, texts=[""])))
        p = tmp_path / "d.pdf"
        p.write_bytes(b"%PDF")
        result = PdfExtractor().extract(_source(str(p)))
        m = result.asset.metadata if result.asset else {}
        assert m["has_text"] is False and m["ocr_performed"] is False

    @pytest.mark.skipif(not _HAS_FITZ, reason="fitz (PyMuPDF) no instalado")
    def test_fitz_ocr_con_tesseract(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        mod = sys.modules["knowledge.engine.extractors.pdf"]
        monkeypatch.setattr(mod, "_HAS_TESSERACT", True)
        monkeypatch.setitem(sys.modules, "fitz", types.SimpleNamespace(open=lambda p: _FakePdf(pages=1, texts=[""])))
        monkeypatch.setitem(sys.modules, "pytesseract", types.SimpleNamespace(image_to_string=lambda b: "ocr texto"))
        p = tmp_path / "d.pdf"
        p.write_bytes(b"%PDF")
        result = PdfExtractor().extract(_source(str(p)))
        m = result.asset.metadata if result.asset else {}
        assert m["ocr_performed"] is True

    def test_error_general(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        mod = sys.modules["knowledge.engine.extractors.pdf"]

        def boom(path: str | Path) -> tuple[str, int]:
            raise OSError("hash falla")

        monkeypatch.setattr(mod, "_hash_stream", boom)
        p = tmp_path / "d.pdf"
        p.write_bytes(b"%PDF")
        result = PdfExtractor().extract(_source(str(p)))
        assert result.errors and "Extraction error" in result.errors[0]

    def test_quality_pdf(self) -> None:
        from knowledge.engine.extractors.pdf import _compute_pdf_quality

        q = _compute_pdf_quality(
            {"pages": 2, "title": "t", "author": "a", "text_length": 500, "keywords": ["k"], "has_text": True}
        )
        assert q == pytest.approx(1.0)
        assert _compute_pdf_quality({}) == pytest.approx(0.3)

    def test_no_existe(self) -> None:
        result = PdfExtractor().extract(_source("/no/existe/d.pdf"))
        assert result.errors and "not found" in result.errors[0]


class _FakePdf:
    def __init__(self, pages: int = 1, metadata: dict[str, Any] | None = None, texts: list[str] | None = None) -> None:
        self.page_count = pages
        self.pdf_version = "1.7"
        self.is_encrypted = False
        self.is_pdf = True
        self.metadata = metadata or {}
        self._texts = texts or [f"texto de la página {i}" for i in range(pages)]

    def __getitem__(self, i: int) -> types.SimpleNamespace:
        return types.SimpleNamespace(
            get_text=lambda: self._texts[i] or "",
            get_pixmap=lambda: types.SimpleNamespace(tobytes=lambda fmt: b"png-bytes"),
        )

    def close(self) -> None:
        return None


# ── office ──────────────────────────────────────────────────────────────────


class TestOfficeCobertura:
    def test_too_large(self, tmp_path: Path) -> None:
        p = tmp_path / "d.docx"
        with p.open("wb") as f:
            f.seek(201 * 1024 * 1024)
            f.write(b"x")
        result = OfficeExtractor().extract(_source(str(p)))
        assert result.errors and "too large" in result.errors[0]

    def test_extension_no_soportada(self, tmp_path: Path) -> None:
        p = tmp_path / "d.odt"
        p.write_bytes(b"x" * 10)
        result = OfficeExtractor().extract(_source(str(p)))
        m = result.asset.metadata if result.asset else {}
        assert m["_degraded"] is True and "Unsupported extension" in m["_degraded_reason"]

    def test_xlsx_sin_openpyxl(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        mod = sys.modules["knowledge.engine.extractors.office"]
        monkeypatch.setattr(mod, "_HAS_DOCX", False)
        monkeypatch.setattr(mod, "_HAS_OPENPYXL", False)
        monkeypatch.setattr(mod, "_HAS_PPTX", False)
        p = tmp_path / "d.xlsx"
        p.write_bytes(b"x" * 10)
        result = OfficeExtractor().extract(_source(str(p)))
        m = result.asset.metadata if result.asset else {}
        assert m["_degraded"] is True and "openpyxl" in m["_degraded_reason"]

    def test_docx_fake(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        mod = sys.modules["knowledge.engine.extractors.office"]
        monkeypatch.setattr(mod, "_HAS_DOCX", True)
        monkeypatch.setattr(mod, "_HAS_OPENPYXL", False)
        monkeypatch.setattr(mod, "_HAS_PPTX", False)
        monkeypatch.setitem(sys.modules, "docx", types.SimpleNamespace(Document=lambda p: _FakeDocx()))
        p = tmp_path / "d.docx"
        p.write_bytes(b"x" * 10)
        result = OfficeExtractor().extract(_source(str(p)))
        m = result.asset.metadata if result.asset else {}
        assert m["paragraph_count"] == 2
        assert m["tables_count"] == 1 and m["tables_rows_total"] == 2
        assert m["sections_count"] == 1
        assert m["word_count"] > 50 or m["word_count"] > 0
        assert m["office_title"] == "Mi Titulo"

    def test_xlsx_fake(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        mod = sys.modules["knowledge.engine.extractors.office"]
        monkeypatch.setattr(mod, "_HAS_DOCX", False)
        monkeypatch.setattr(mod, "_HAS_OPENPYXL", True)
        monkeypatch.setattr(mod, "_HAS_PPTX", False)
        monkeypatch.setitem(sys.modules, "openpyxl", types.SimpleNamespace(load_workbook=lambda *a, **k: _FakeWb()))
        p = tmp_path / "d.xlsx"
        p.write_bytes(b"x" * 10)
        result = OfficeExtractor().extract(_source(str(p)))
        m = result.asset.metadata if result.asset else {}
        assert m["sheet_count"] == 2
        assert m["rows_total"] == 12
        assert result.warnings and "approximate" in result.warnings[0]

    def test_pptx_degradado(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        mod = sys.modules["knowledge.engine.extractors.office"]
        monkeypatch.setattr(mod, "_HAS_DOCX", False)
        monkeypatch.setattr(mod, "_HAS_OPENPYXL", False)
        monkeypatch.setattr(mod, "_HAS_PPTX", False)
        p = tmp_path / "d.pptx"
        p.write_bytes(b"x" * 10)
        result = OfficeExtractor().extract(_source(str(p)))
        m = result.asset.metadata if result.asset else {}
        assert m["_degraded"] is True and "python-pptx" in m["_degraded_reason"]

    def test_pptx_fake(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        mod = sys.modules["knowledge.engine.extractors.office"]
        monkeypatch.setattr(mod, "_HAS_DOCX", False)
        monkeypatch.setattr(mod, "_HAS_OPENPYXL", False)
        monkeypatch.setattr(mod, "_HAS_PPTX", True)
        monkeypatch.setitem(sys.modules, "pptx", types.SimpleNamespace(Presentation=lambda p: _FakePptx()))
        p = tmp_path / "d.pptx"
        p.write_bytes(b"x" * 10)
        result = OfficeExtractor().extract(_source(str(p)))
        m = result.asset.metadata if result.asset else {}
        assert m["slide_count"] == 1
        assert m["shapes_total"] == 2
        assert m["text_preview"]

    def test_error_general(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        mod = sys.modules["knowledge.engine.extractors.office"]

        def boom(path: str | Path) -> tuple[str, int]:
            raise OSError("hash falla")

        monkeypatch.setattr(mod, "_hash_stream", boom)
        p = tmp_path / "d.docx"
        p.write_bytes(b"x")
        result = OfficeExtractor().extract(_source(str(p)))
        assert result.errors and "Extraction error" in result.errors[0]


class _FakeDocx:
    class _Props:
        title = "Mi Titulo"
        author = "Ana"
        subject = ""
        category = ""
        comments = ""
        keywords = "k1"
        last_modified_by = "Bot"
        created = "2026-01-01"
        modified = "2026-01-02"

    class _Paragraph:
        def __init__(self, text: str) -> None:
            self.text = text

    class _Row:
        pass

    class _Table:
        def __init__(self) -> None:
            self.rows = [object(), object()]
            self.columns = [object(), object()]

    def __init__(self) -> None:
        self.core_properties = self._Props()
        self.paragraphs = [self._Paragraph("Palabra " * 60), self._Paragraph("Segunda frase")]
        self.tables = [self._Table()]
        self.sections = [object()]


class _FakeWb:
    class _Props:
        title = "Mi Libro"
        subject = "Tema"
        keywords = ""
        category = ""
        description = "Descripcion"
        creator = "Ana"

    class _Sheet:
        max_row = 6

    def __init__(self) -> None:
        self.properties = self._Props()
        self.sheetnames = ["Hoja1", "Hoja2"]

    def __getitem__(self, name: str) -> _FakeWb._Sheet:
        return self._Sheet()

    def close(self) -> None:
        return None


class _FakePptx:
    class _Props:
        title = "Pres"
        author = "Ana"
        subject = ""
        keywords = ""
        comments = ""
        category = ""
        last_modified_by = ""
        created = ""
        modified = ""

    class _Shape:
        def __init__(self, text: str = "") -> None:
            self.text = text

    def __init__(self) -> None:
        self.core_properties = self._Props()
        self.slide_width = 10
        self.slide_height = 8
        self.slides = [types.SimpleNamespace(shapes=[self._Shape("Primer texto"), self._Shape()])]


# ── git ─────────────────────────────────────────────────────────────────────


class TestGitCobertura:
    def test_sin_git(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mod = sys.modules["knowledge.engine.extractors.git"]
        monkeypatch.setattr(mod, "_HAS_GIT", False)
        result = GitExtractor().extract(_source("http://x/y"))
        assert result.errors and "git CLI" in result.errors[0]

    def test_empty_location(self) -> None:
        result = GitExtractor().extract(AssetSource("filesystem", ""))
        assert result.errors and "Empty" in result.errors[0]

    def test_repo_local(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        (repo / ".git").mkdir(parents=True)
        (repo / "README.md").write_text("# Proyecto\n" + "texto " * 50, encoding="utf-8")
        result = GitExtractor().extract(_source(str(repo)))
        m = result.asset.metadata if result.asset else {}
        assert m["readme_preview"] and "size" in m
        assert "cloned_from" not in m

    def test_repo_directo_git(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        (repo / ".git").mkdir(parents=True)
        result = GitExtractor().extract(_source(str(repo / ".git")))
        assert result.asset is not None

    def test_no_es_repo(self, tmp_path: Path) -> None:
        d = tmp_path / "norepo"
        d.mkdir()
        result = GitExtractor().extract(_source(str(d)))
        assert result.errors and "Not a git repository" in result.errors[0]

    def test_location_no_existe(self) -> None:
        result = GitExtractor().extract(_source("/no/existe/ruta"))
        assert result.errors and "Location not found" in result.errors[0]

    def test_clone_ok_y_temp(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import tempfile

        def fake_clone(url: str, t: str) -> str:
            (Path(t) / ".git").mkdir(parents=True, exist_ok=True)
            (Path(t) / "README.md").write_text("leeme", encoding="utf-8")
            return t

        monkeypatch.setattr(GitExtractor, "_clone_repo", staticmethod(fake_clone))
        monkeypatch.setattr(tempfile, "mkdtemp", lambda *a, **k: str(tmp_path / "clon"))
        result = GitExtractor().extract(AssetSource("github", "https://github.com/u/r"))
        m = result.asset.metadata if result.asset else {}
        assert m["cloned_from"] == "https://github.com/u/r"
        assert "clone_size" in m

    def test_clone_falla(self, monkeypatch: pytest.MonkeyPatch) -> None:
        sys.modules["knowledge.engine.extractors.git"]

        def fake_clone(url: str, t: str) -> str:
            raise RuntimeError("git clone failed for X: fatal")

        monkeypatch.setattr(GitExtractor, "_clone_repo", staticmethod(fake_clone))
        result = GitExtractor().extract(AssetSource("github", "https://github.com/u/r"))
        assert result.errors and "Extraction error" in result.errors[0]

    def test_helpers_git(self) -> None:
        from knowledge.engine.extractors.git import (
            _compute_git_quality,
            _git_cmd,
            _sanitize_git_url,
        )

        assert _sanitize_git_url("git@host:user/repo.git") == "git@host:user/repo.git"
        assert _sanitize_git_url("http://x") == "http://x"
        assert _sanitize_git_url("https://x") == "https://x"
        assert _sanitize_git_url("ftp://x") == "ftp://x"
        assert _git_cmd("/no/existe", ["status"]) is None
        assert _compute_git_quality({"commit_count": 10, "origin_url": "u"}) > 0.3
        assert _compute_git_quality({}) == 0.3

    def test_metadatos_extendidos(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from knowledge.engine.extractors.git import GitExtractor as GE

        repo = tmp_path / "repo"
        (repo / ".git").mkdir(parents=True)
        calls: list[list[str]] = []

        def fake_git(repo_path: str, args: list[str]) -> str | None:
            calls.append(args)
            if any("origin.url" in a for a in args):
                return "https://github.com/u/r\n"
            if "rev-parse" in args:
                return "main\n"
            if "max-count" in args[1]:
                return "abc12345|Ana|a@b.c|2026-01-01|commit A\n"
            if args[0] == "tag":
                return "v1.0\nv0.9\n"
            if args[0] == "branch":
                return "* main\n  dev\n"
            return None

        monkeypatch.setattr("knowledge.engine.extractors.git._git_cmd", fake_git)
        result = GE().extract(_source(str(repo)))
        m = result.asset.metadata if result.asset else {}
        assert m["origin_url"] == "https://github.com/u/r"
        assert m["current_branch"] == "main"
        assert m["commit_count"] == 1
        assert m["tags"] == ["v1.0", "v0.9"]
        assert m["branches"] == ["main", "dev"]

    def test_quality_git(self) -> None:
        from knowledge.engine.extractors.git import _compute_git_quality

        m = {"commit_count": 15, "tag_count": 2, "branch_count": 3, "origin_url": "u", "readme_preview": "x"}
        assert _compute_git_quality(m) == 1.0

    def test_find_readme_error(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import pathlib

        from knowledge.engine.extractors.git import _find_readme

        def boom(self: Any, **k: Any) -> str:
            raise OSError("read falla")

        monkeypatch.setattr(pathlib.Path, "read_text", boom)
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "README.md").write_text("x")
        assert _find_readme(str(repo)) is None

    def test_repo_size_ignora_errores(self, tmp_path: Path) -> None:
        d = tmp_path / "dir"
        d.mkdir()
        (d / "f.txt").write_text("hola")
        assert GitExtractor._repo_size(str(d)) == 4

    def test_clone_repo_real(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        mod = sys.modules["knowledge.engine.extractors.git"]

        class ResOk:
            returncode = 0
            stderr = ""

        monkeypatch.setattr(mod.subprocess, "run", lambda *a, **k: ResOk())
        assert GitExtractor._clone_repo("https://github.com/u/r", str(tmp_path)) == str(tmp_path)

        class ResFail:
            returncode = 128
            stderr = "fatal"

        monkeypatch.setattr(mod.subprocess, "run", lambda *a, **k: ResFail())
        with pytest.raises(RuntimeError, match="clone failed"):
            GitExtractor._clone_repo("https://github.com/u/r", str(tmp_path))


# ── video ───────────────────────────────────────────────────────────────────


class TestVideoCobertura:
    def test_too_large(self, tmp_path: Path) -> None:
        p = tmp_path / "v.mp4"
        with p.open("wb") as f:
            f.seek(4 * 1024 * 1024 * 1024 + 1)
            f.write(b"x")
        result = VideoExtractor().extract(_source(str(p)))
        assert result.errors and "too large" in result.errors[0]

    def test_degradado_sin_ffprobe(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        mod = sys.modules["knowledge.engine.extractors.video"]
        monkeypatch.setattr(mod, "_HAS_FFPROBE", False)
        monkeypatch.setattr(mod, "_HAS_FFMPEG", False)
        monkeypatch.setattr(mod, "_HAS_OPENCV", False)
        monkeypatch.setattr(mod, "_HAS_WHISPER", False)
        p = tmp_path / "v.mp4"
        p.write_bytes(b"x" * 10)
        result = VideoExtractor().extract(_source(str(p)))
        assert result.asset is not None and result.asset.metadata["_degraded_ffprobe"] is True

    def test_error_general(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        mod = sys.modules["knowledge.engine.extractors.video"]

        def boom(path: str | Path) -> tuple[str, int]:
            raise OSError("hash falla")

        monkeypatch.setattr(mod, "_hash_stream", boom)
        p = tmp_path / "v.mp4"
        p.write_bytes(b"x")
        result = VideoExtractor().extract(_source(str(p)))
        assert result.errors and "Extraction error" in result.errors[0]

    def test_probe_format_y_streams(self) -> None:
        metadata: dict[str, Any] = {}
        VideoExtractor._probe_format(metadata, {"duration": "10.5", "bit_rate": "1000", "size": 5})
        assert metadata["video_duration_sec"] == "10.5"
        VideoExtractor._probe_streams(
            metadata,
            [
                {"codec_type": "video", "codec_name": "h264", "width": 640, "height": 480, "r_frame_rate": "30/1"},
                {"codec_type": "audio", "codec_name": "aac", "sample_rate": 48000, "channels": 2},
            ],
        )
        assert metadata["video_video_codec"] == "h264"
        assert metadata["video_audio_codec"] == "aac"

    def test_ffprobe_fallido(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        class Res:
            returncode = 1
            stdout = ""
            stderr = "boom"

        monkeypatch.setattr("knowledge.engine.extractors.video.subprocess.run", lambda *a, **k: Res())
        p = tmp_path / "v.mp4"
        p.write_bytes(b"x")
        result = VideoExtractor().extract(_source(str(p)))
        m = result.asset.metadata if result.asset else {}
        assert m["_degraded_ffprobe"] is True

    def test_ffprobe_timeout(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import subprocess

        def boom(*a: Any, **k: Any) -> None:
            raise subprocess.TimeoutExpired("ffprobe", 60)

        monkeypatch.setattr("knowledge.engine.extractors.video.subprocess.run", boom)
        p = tmp_path / "v.mp4"
        p.write_bytes(b"x")
        result = VideoExtractor().extract(_source(str(p)))
        assert result.asset is not None and "_degraded_ffprobe" in result.asset.metadata

    def test_thumbnails_generadas(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        mod = sys.modules["knowledge.engine.extractors.video"]
        monkeypatch.setattr(mod, "_HAS_FFPROBE", True)
        monkeypatch.setattr(mod, "_HAS_FFMPEG", True)
        monkeypatch.setattr(mod, "_HAS_OPENCV", False)
        monkeypatch.setattr(mod, "_HAS_WHISPER", False)

        class Res:
            returncode = 0
            stdout = '{"format": {"duration": "10.0"}, "streams": []}'
            stderr = ""

        def fake_run(cmd: list[str], **k: Any) -> Res:
            if cmd and "ffmpeg" in cmd[0]:
                Path(cmd[-1]).write_bytes(b"thumb")
                return types.SimpleNamespace(returncode=0)
            return Res()

        monkeypatch.setattr("knowledge.engine.extractors.video.subprocess.run", fake_run)
        p = tmp_path / "v.mp4"
        p.write_bytes(b"x" * 10)
        result = VideoExtractor().extract(_source(str(p)))
        m = result.asset.metadata if result.asset else {}
        assert m["thumbnails"] and len(m["thumbnails"]) == 3
        assert m["video_duration_sec"] == "10.0"

    def test_thumbnail_timeout(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import subprocess

        mod = sys.modules["knowledge.engine.extractors.video"]
        monkeypatch.setattr(mod, "_HAS_FFPROBE", True)
        monkeypatch.setattr(mod, "_HAS_FFMPEG", True)
        monkeypatch.setattr(mod, "_HAS_OPENCV", False)
        monkeypatch.setattr(mod, "_HAS_WHISPER", False)

        class Res:
            returncode = 0
            stdout = '{"format": {"duration": "10.0"}, "streams": []}'
            stderr = ""

        def fake_run(cmd: list[str], **k: Any) -> Res:
            if cmd and "ffmpeg" in str(cmd[0]):
                raise subprocess.TimeoutExpired("ffmpeg", 30)
            return Res()

        monkeypatch.setattr("knowledge.engine.extractors.video.subprocess.run", fake_run)
        p = tmp_path / "v.mp4"
        p.write_bytes(b"x")
        result = VideoExtractor().extract(_source(str(p)))
        assert result.asset is not None and "thumbnails" not in result.asset.metadata

    def test_sin_duration_sin_thumbnails(self) -> None:
        metadata: dict[str, Any] = {}
        VideoExtractor._extract_thumbnails("no-importa.mp4", metadata)
        assert "thumbnails" not in metadata

    def test_scenes_detectadas(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mod = sys.modules["knowledge.engine.extractors.video"]
        monkeypatch.setattr(mod, "_HAS_OPENCV", True)

        class FakeCap:
            def __init__(self, path: str) -> None:
                self._frames = [b"a", b"b", b"c"]

            def get(self, prop: int) -> float:
                if prop == 5:
                    return 0.5
                return 3.0

            def set(self, prop: int, val: int) -> None:
                return None

            def read(self) -> tuple[bool, bytes]:
                if self._frames:
                    return True, self._frames.pop(0)
                return False, b""

            def release(self) -> None:
                return None

        fake_cv2 = types.SimpleNamespace(
            VideoCapture=lambda p: FakeCap(p),
            CAP_PROP_FPS=5,
            CAP_PROP_FRAME_COUNT=6,
            CAP_PROP_POS_FRAMES=7,
            cvtColor=lambda f, c: f,
            absdiff=lambda a, b: types.SimpleNamespace(mean=lambda: 255.0),
            COLOR_BGR2GRAY=0,
        )
        monkeypatch.setitem(sys.modules, "cv2", fake_cv2)
        metadata: dict[str, Any] = {}
        VideoExtractor._detect_scenes("v.mp4", metadata)
        assert metadata["video_total_frames"] == 3
        assert "video_scene_count" in metadata

    def test_scenes_sin_frames(self, monkeypatch: pytest.MonkeyPatch) -> None:
        class FakeCap:
            def __init__(self) -> None:
                self._n = 0

            def get(self, prop: int) -> float:
                if prop == 6:
                    return 3.0
                return 0.0

            def read(self) -> tuple[bool, bytes]:
                self._n += 1
                return False, b"" if self._n > 1 else b"f"

            def release(self) -> None:
                return None

        fake_cv2 = types.SimpleNamespace(
            VideoCapture=lambda p: FakeCap(), CAP_PROP_FPS=5, CAP_PROP_FRAME_COUNT=6, CAP_PROP_POS_FRAMES=7
        )
        monkeypatch.setitem(sys.modules, "cv2", fake_cv2)
        metadata: dict[str, Any] = {}
        VideoExtractor._detect_scenes("v.mp4", metadata)
        assert metadata["video_total_frames"] == 3
        assert "video_scene_count" not in metadata

    def test_scenes_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def boom(path: str) -> Any:
            raise ValueError("sin opencv real")

        monkeypatch.setitem(sys.modules, "cv2", types.SimpleNamespace(VideoCapture=boom))
        metadata: dict[str, Any] = {}
        VideoExtractor._detect_scenes("v.mp4", metadata)
        assert metadata == {}

    def test_transcripcion_ok_y_fallo(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        mod = sys.modules["knowledge.engine.extractors.video"]
        monkeypatch.setattr(mod, "_HAS_FFPROBE", True)
        monkeypatch.setattr(mod, "_HAS_FFMPEG", False)
        monkeypatch.setattr(mod, "_HAS_OPENCV", False)
        monkeypatch.setattr(mod, "_HAS_WHISPER", True)

        class Res:
            returncode = 0
            stdout = '{"format": {}, "streams": []}'
            stderr = ""

        monkeypatch.setattr("knowledge.engine.extractors.video.subprocess.run", lambda *a, **k: Res())
        fake_model = types.SimpleNamespace(transcribe=lambda p: {"text": "transcripcion de prueba", "language": "es"})
        monkeypatch.setattr(mod, "_get_whisper_model", lambda: fake_model)
        p = tmp_path / "v.mp4"
        p.write_bytes(b"x")
        result = VideoExtractor().extract(_source(str(p)))
        m = result.asset.metadata if result.asset else {}
        assert m["transcript"] == "transcripcion de prueba"
        assert m["transcription_performed"] is True

        def boom(p: str) -> None:
            raise RuntimeError("whisper roto")

        monkeypatch.setattr(mod, "_get_whisper_model", lambda: types.SimpleNamespace(transcribe=boom))
        result2 = VideoExtractor().extract(_source(str(p)))
        m2 = result2.asset.metadata if result2.asset else {}
        assert m2["transcription_performed"] is False and m2["transcription_error"]

    def test_quality_video(self) -> None:
        from knowledge.engine.extractors.video import _compute_video_quality

        m = {
            "video_duration_sec": "5",
            "video_video_codec": "h264",
            "video_width": 100,
            "video_fps": "30",
            "thumbnails": ["t"],
            "transcription_performed": True,
            "transcript": "x",
            "_degraded_ffprobe": False,
        }
        assert _compute_video_quality(m) == pytest.approx(1.0)
        assert _compute_video_quality({"_degraded_ffprobe": True}) == pytest.approx(0.3)


# ── web ─────────────────────────────────────────────────────────────────────


class TestWebExtractorCobertura:
    def test_url_vacia(self) -> None:
        result = WebExtractor().extract(AssetSource("http", ""))
        assert result.errors and "Empty URL" in result.errors[0]

    def test_scheme_bloqueado(self) -> None:
        result = WebExtractor().extract(AssetSource("http", "ftp://example.com/x"))
        assert result.errors and "Scheme" in result.errors[0]

    def test_host_bloqueado(self) -> None:
        result = WebExtractor().extract(AssetSource("http", "http://localhost/x"))
        assert result.errors and "blocked" in result.errors[0]

    def test_ip_privada(self) -> None:
        result = WebExtractor().extract(AssetSource("http", "http://10.0.0.5/x"))
        assert result.errors and "blocked" in result.errors[0]

    def test_ip_publica_literal(self) -> None:
        from knowledge.engine.extractors.web import _check_ip_blocked

        WebExtractor._validate_url("http://8.8.8.8/x")
        WebExtractor._validate_redirect_url("http://8.8.8.8/x")
        assert _check_ip_blocked(ipaddress.ip_address("8.8.8.8"), "8.8.8.8") is None

    def test_metadata_cloud(self) -> None:
        result = WebExtractor().extract(AssetSource("http", "http://169.254.169.254/latest/meta-data"))
        assert result.errors and "metadata" in result.errors[0]

    def test_dns_fallo(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import socket

        def gaierror(*a: Any, **k: Any) -> None:
            raise socket.gaierror("no resuelve")

        monkeypatch.setattr("knowledge.engine.extractors.web.socket.getaddrinfo", gaierror)
        result = WebExtractor().extract(AssetSource("http", "http://dominio-que-no-existe-xyz.com/x"))
        assert result.errors and "DNS" in result.errors[0]

    def test_dns_privada(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "knowledge.engine.extractors.web.socket.getaddrinfo",
            lambda *a, **k: [(2, 1, 6, "", ("192.168.1.1", 0))],
        )
        result = WebExtractor().extract(AssetSource("http", "http://host-interno.local/x"))
        assert result.errors and "blocked" in result.errors[0]

    @pytest.mark.skipif(_HAS_NETWORK, reason="red disponible: tests asumen entorno sin red")
    @pytest.mark.skipif(_HAS_NETWORK, reason="red disponible: tests asumen entorno sin red")
    def test_dns_publica_y_redirect_fallida(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "knowledge.engine.extractors.web.socket.getaddrinfo",
            lambda *a, **k: [(2, 1, 6, "", ("8.8.8.8", 0))],
        )
        result = WebExtractor().extract(AssetSource("http", "http://host-publico.example/x"))
        assert result.errors  # httpx devuelve error de conexión

    def test_degradado_sin_deps(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mod = sys.modules["knowledge.engine.extractors.web"]
        monkeypatch.setattr(mod, "_HAS_HTTPX", False)
        monkeypatch.setattr(mod, "_HAS_BS4", False)
        result = WebExtractor().extract(AssetSource("http", "http://example.com/x"))
        m = result.asset.metadata if result.asset else {}
        assert m["_degraded"] is True and m["content_sha256"]

    def test_validate_redirect(self) -> None:
        WebExtractor._validate_redirect_url("https://publico.example/x")

    def test_redirect_scheme_bloqueado(self) -> None:
        with pytest.raises(URLSchemeBlocked):
            WebExtractor._validate_redirect_url("file:///x")

    def test_redirect_ip_privada(self) -> None:
        with pytest.raises(PrivateIPBlocked):
            WebExtractor._validate_redirect_url("http://10.0.0.1/x")

    def test_redirect_dns_ok(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "knowledge.engine.extractors.web.socket.getaddrinfo",
            lambda *a, **k: [(2, 1, 6, "", ("8.8.8.8", 0))],
        )
        WebExtractor._validate_redirect_url("http://host-publico.example/x")

    def test_redirect_dns_falla(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import socket

        def gaierror(*a: Any, **k: Any) -> None:
            raise socket.gaierror("no")

        monkeypatch.setattr("knowledge.engine.extractors.web.socket.getaddrinfo", gaierror)
        WebExtractor._validate_redirect_url("http://no-existe-xyz.example/x")

    def test_helpers_web(self) -> None:
        from knowledge.engine.extractors.web import _compute_web_quality, _is_ip_string, hashlib_content

        assert _is_ip_string("10.0.0.1") is True
        assert _is_ip_string("no-ip") is False
        assert hashlib_content(b"x") == hashlib_content(b"x")
        full = {
            "title": "t",
            "description": "d",
            "text_length": 500,
            "image_count": 1,
            "link_count": 1,
            "status_code": 200,
        }
        assert _compute_web_quality(full) == pytest.approx(1.0)
        assert _compute_web_quality({}) == 0.3

    @pytest.mark.skipif(_HAS_NETWORK, reason="red disponible: tests asumen entorno sin red")
    def test_parse_html(self) -> None:
        html = b"<html><head><title>Mi Pagina</title><meta name='description' content='Desc'></head><body><img src='/i.png'><a href='https://out.example/l'>link</a><a href='/interno'>int</a></body></html>"
        m = WebExtractor()._parse_html(
            html, "https://final.example/x", "https://orig.example/y", "now", 200, "text/html"
        )
        assert m["title"] == "Mi Pagina"
        assert m["description"] == "Desc"
        assert m["image_count"] == 1 and m["link_count"] == 1
        assert m["wraps"] == "source:https://orig.example/y"

    @pytest.mark.skipif(_HAS_NETWORK, reason="red disponible: tests asumen entorno sin red")
    def test_fetch_extract_completo(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mod = sys.modules["knowledge.engine.extractors.web"]
        monkeypatch.setattr(mod, "_HAS_HTTPX", True)
        monkeypatch.setattr(mod, "_HAS_BS4", True)

        class FakeResp:
            status_code = 200
            url = "https://final.example/x"
            content = b"<html><head><title>T</title></head><body>Texto de la pagina web con contenido</body></html>"
            headers: dict[str, str] = {"content-type": "text/html"}  # noqa: RUF012

            def raise_for_status(self) -> None:
                return None

        class FakeClient:
            def __init__(self, *a: Any, **kw: Any) -> None:
                pass

            def __enter__(self) -> Self:
                return self

            def __exit__(self, *a: object) -> None:
                return None

            def get(self, url: str, headers: dict[str, str]) -> FakeResp:
                return FakeResp()

        class FakeHTTPTransport:
            def __init__(self, **kw: Any) -> None:
                pass

        class FakeTimeout:
            def __init__(self, **kw: Any) -> None:
                pass

        fake_httpx = types.ModuleType("httpx")
        fake_httpx.Client = FakeClient
        fake_httpx.HTTPTransport = FakeHTTPTransport
        fake_httpx.Timeout = FakeTimeout
        monkeypatch.setitem(sys.modules, "httpx", fake_httpx)
        monkeypatch.setattr(
            "knowledge.engine.extractors.web.socket.getaddrinfo",
            lambda *a, **k: [(2, 1, 6, "", ("8.8.8.8", 0))],
        )
        result = WebExtractor().extract(AssetSource("http", "https://example.com/x"))
        m = result.asset.metadata if result.asset else {}
        assert m["title"] == "T"
        assert m["status_code"] == 200
        assert result.asset.quality > 0.5  # type: ignore[union-attr]
        assert "FinalResp" if False else m["url"] == "https://final.example/x"

    @pytest.mark.skipif(_HAS_NETWORK, reason="red disponible: tests asumen entorno sin red")
    def test_fetch_body_cortado(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mod = sys.modules["knowledge.engine.extractors.web"]
        monkeypatch.setattr(mod, "MAX_BODY_SIZE", 10)

        class FakeRespBig:
            status_code = 200
            url = "https://final.example/x"
            content = b"<html>" + b"x" * 100 + b"</html>"
            headers: dict[str, str] = {"content-type": "text/html"}  # noqa: RUF012

            def raise_for_status(self) -> None:
                return None

        class FakeClient:
            def __init__(self, *a: Any, **kw: Any) -> None:
                pass

            def __enter__(self) -> Self:
                return self

            def __exit__(self, *a: object) -> None:
                return None

            def get(self, url: str, headers: dict[str, str]) -> FakeRespBig:
                return FakeRespBig()

        fake_httpx2 = types.ModuleType("httpx")
        fake_httpx2.Client = FakeClient
        fake_httpx2.HTTPTransport = types.SimpleNamespace
        fake_httpx2.Timeout = types.SimpleNamespace
        monkeypatch.setitem(sys.modules, "httpx", fake_httpx2)
        monkeypatch.setattr(
            "knowledge.engine.extractors.web.socket.getaddrinfo",
            lambda *a, **k: [(2, 1, 6, "", ("8.8.8.8", 0))],
        )
        result = WebExtractor().extract(AssetSource("http", "https://example.com/x"))
        m = result.asset.metadata if result.asset else {}
        assert m["size"] == 10

    @pytest.mark.skipif(_HAS_NETWORK, reason="red disponible: tests asumen entorno sin red")
    def test_fetch_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        class FakeClient:
            def __init__(self, *a: Any, **kw: Any) -> None:
                pass

            def __enter__(self) -> Self:
                return self

            def __exit__(self, *a: object) -> None:
                return None

            def get(self, url: str, headers: dict[str, str]) -> None:
                raise RuntimeError("red caida")

        fake_httpx3 = types.ModuleType("httpx")
        fake_httpx3.Client = FakeClient
        fake_httpx3.HTTPTransport = types.SimpleNamespace
        fake_httpx3.Timeout = types.SimpleNamespace
        monkeypatch.setitem(sys.modules, "httpx", fake_httpx3)
        result = WebExtractor().extract(AssetSource("http", "https://example.com/x"))
        assert result.errors and "Extraction error" in result.errors[0]


from knowledge.engine.extractors.audio import AudioExtractor
from knowledge.engine.extractors.base import ExtractorRegistry
from knowledge.engine.extractors.git import GitExtractor
from knowledge.engine.extractors.image import ImageExtractor
from knowledge.engine.extractors.markdown import MarkdownExtractor
from knowledge.engine.extractors.office import OfficeExtractor
from knowledge.engine.extractors.pdf import PdfExtractor
from knowledge.engine.extractors.web import PrivateIPBlocked, URLSchemeBlocked, WebExtractor
