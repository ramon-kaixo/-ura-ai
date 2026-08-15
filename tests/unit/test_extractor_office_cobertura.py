"""Cobertura 100x100 de knowledge/engine/extractors/office.py (TASK-20260815-003).

Cubre OfficeExtractor.extract (archivo inexistente, límite de tamaño, error de
lectura, extensión no soportada, degradación por librería ausente) y los
extractores por extensión DOCX/XLSX/PPTX en todos sus caminos de parsing.

python-docx, openpyxl y python-pptx NO están instalados en el venv, así que el
camino "librería presente" se simula inyectando módulos fake en sys.modules y
activando _HAS_DOCX/_HAS_OPENPYXL/_HAS_PPTX; el comportamiento lógico real
(metadatos, recuentos, previews, cálculos de calidad) se cementa con aserciones
sobre los resultados de extract().
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from knowledge.engine.extractors import office
from knowledge.engine.extractors.base import ExtractionResult
from knowledge.engine.ontology.internal import AssetSource, AssetType, KnowledgeAsset


class EmptyStr:
    """Objeto con __bool__ True pero __str__ vacío (ramas de validación falsa)."""

    def __bool__(self) -> bool:
        return True

    def __str__(self) -> str:
        return ""


class FakeWorksheet:
    """Worksheet fake con max_row opcional (None ejercita el or 0)."""

    def __init__(self, max_row: int | None) -> None:
        self.max_row = max_row


class FakeWorkbook:
    """Workbook fake con propiedades, hojas y cierre verificable."""

    def __init__(self, sheets: dict[str, FakeWorksheet], properties: Any | None) -> None:
        self._sheets = sheets
        self.sheetnames = list(sheets)
        self.properties = properties
        self.closed = False

    def __getitem__(self, name: str) -> FakeWorksheet:
        return self._sheets[name]

    def close(self) -> None:
        self.closed = True


def _make_file(tmp_path: Path, name: str, data: bytes = b"dummy office content") -> Path:
    path = tmp_path / name
    path.write_bytes(data)
    return path


def _asset_of(result: ExtractionResult) -> KnowledgeAsset:
    assert result.asset is not None
    return result.asset


def _docx_core_props(extra: dict[str, Any] | None = None) -> SimpleNamespace:
    values: dict[str, Any] = {
        "title": "Doc Title",
        "author": "Ramon",
        "subject": "Subject",
        "category": "Cat",
        "comments": "Comments",
        "keywords": "kw1,kw2",
        "last_modified_by": "web",
        "created_at": "2026-01-01T00:00:00Z",
        "modified_at": "2026-01-02T00:00:00Z",
    }
    values.update(extra or {})
    return SimpleNamespace(**values)


class TestModuleRegistration:
    def test_registered_with_metadata(self) -> None:
        extractor = office._registry.get("office")
        assert extractor is not None
        assert extractor.id == "office"
        assert extractor.version == "1.0.0"
        assert extractor.cost == "O(n)"
        assert extractor.supported_mime_types == office._OFFICE_MIMES
        assert office.MAX_OFFICE_SIZE == 200 * 1024 * 1024


class TestExtract:
    def test_file_not_found(self, tmp_path: Path) -> None:
        result = office.OfficeExtractor().extract(AssetSource("filesystem", str(tmp_path / "no.docx")))
        assert result.asset is None
        assert result.errors == [f"File not found: {tmp_path / 'no.docx'}"]
        assert result.duration_ms >= 0

    def test_too_large(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        path = _make_file(tmp_path, "big.docx")
        monkeypatch.setattr(office, "MAX_OFFICE_SIZE", 0)
        result = office.OfficeExtractor().extract(AssetSource("filesystem", str(path)))
        assert result.asset is None
        assert result.errors == [f"File too large: {path.stat().st_size} bytes (max 0)"]

    def test_hash_error(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        path = _make_file(tmp_path, "doc.docx")

        def raise_read(path_str: str | Path) -> tuple[str, int]:
            raise OSError("disk error")

        monkeypatch.setattr(office, "_hash_stream", raise_read)
        result = office.OfficeExtractor().extract(AssetSource("filesystem", str(path)))
        assert result.asset is None
        assert result.errors == ["Extraction error: disk error"]


class TestUnsupportedExtension:
    def test_degrades_with_reason(self, tmp_path: Path) -> None:
        path = _make_file(tmp_path, "notes.txt")
        result = office.OfficeExtractor().extract(AssetSource("filesystem", str(path)))
        assert result.errors == []
        assert result.warnings == []
        asset = _asset_of(result)
        assert asset.asset_type == AssetType.OFFICE_DOC
        assert asset.metadata["_degraded"] is True
        assert asset.metadata["_degraded_reason"] == "Unsupported extension: .txt"
        assert asset.metadata["format"] == "txt"
        assert asset.quality == pytest.approx(0.3)


class TestDegradedNoLibraries:
    def test_docx_not_installed(self, tmp_path: Path) -> None:
        path = _make_file(tmp_path, "doc.docx")
        result = office.OfficeExtractor().extract(AssetSource("filesystem", str(path)))
        asset = _asset_of(result)
        assert asset.asset_type == AssetType.OFFICE_DOC
        assert asset.metadata["_degraded_reason"] == "python-docx not installed"
        assert asset.quality == pytest.approx(0.3)

    def test_xlsx_not_installed(self, tmp_path: Path) -> None:
        path = _make_file(tmp_path, "sheet.xlsx")
        result = office.OfficeExtractor().extract(AssetSource("filesystem", str(path)))
        asset = _asset_of(result)
        assert asset.asset_type == AssetType.OFFICE_SHEET
        assert asset.metadata["_degraded_reason"] == "openpyxl not installed"

    def test_pptx_not_installed(self, tmp_path: Path) -> None:
        path = _make_file(tmp_path, "slides.pptx")
        result = office.OfficeExtractor().extract(AssetSource("filesystem", str(path)))
        asset = _asset_of(result)
        assert asset.asset_type == AssetType.OFFICE_SLIDE
        assert asset.metadata["_degraded_reason"] == "python-pptx not installed"


class TestDocxExtraction:
    def test_full_metadata(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        path = _make_file(tmp_path, "doc.docx")
        paragraphs = [
            SimpleNamespace(text="Primer parrafo con varias palabras"),
            SimpleNamespace(text="   "),
            SimpleNamespace(text=""),
        ]
        doc = SimpleNamespace(
            core_properties=_docx_core_props(),
            paragraphs=paragraphs,
            tables=[SimpleNamespace(rows=[1, 2, 3], columns=[1, 2])],
            sections=[1, 2, 3],
        )
        monkeypatch.setitem(sys.modules, "docx", SimpleNamespace(Document=lambda p: doc))
        monkeypatch.setattr(office, "_HAS_DOCX", True)

        result = office.OfficeExtractor().extract(AssetSource("filesystem", str(path)))
        assert result.errors == []
        assert result.warnings == []
        asset = _asset_of(result)
        assert asset.asset_type == AssetType.OFFICE_DOC
        md = asset.metadata
        assert md["format"] == "docx"
        assert md["size"] == path.stat().st_size
        assert md["content_sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
        assert md["wraps"] == f"source:{path}"
        assert md["_extractor"] == "office"
        assert md["_extractor_version"] == "1.0.0"
        assert md["office_title"] == "Doc Title"
        assert md["office_author"] == "Ramon"
        assert md["office_subject"] == "Subject"
        assert md["office_category"] == "Cat"
        assert md["office_comments"] == "Comments"
        assert md["office_keywords"] == "kw1,kw2"
        assert md["office_last_modified_by"] == "web"
        assert md["office_created"] == "2026-01-01T00:00:00Z"
        assert md["office_modified"] == "2026-01-02T00:00:00Z"
        assert md["paragraph_count"] == 1
        assert md["word_count"] == 5
        assert md["text_preview"] == "Primer parrafo con varias palabras"
        assert md["tables_count"] == 1
        assert md["tables_rows_total"] == 3
        assert md["tables_cells_total"] == 6
        assert md["sections_count"] == 3
        assert asset.quality == pytest.approx(0.95)

    def test_minimal_doc(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        path = _make_file(tmp_path, "min.docx", b"small")
        doc = SimpleNamespace(
            core_properties=SimpleNamespace(
                title="",
                author=None,
                subject=EmptyStr(),
                category="",
                comments="",
                keywords="",
last_modified_by="",
            created_at=None,
            modified_at=None,
        ),
            paragraphs=[],
            tables=[],
            sections=[],
        )
        monkeypatch.setitem(sys.modules, "docx", SimpleNamespace(Document=lambda p: doc))
        monkeypatch.setattr(office, "_HAS_DOCX", True)

        result = office.OfficeExtractor().extract(AssetSource("filesystem", str(path)))
        asset = _asset_of(result)
        md = asset.metadata
        assert "office_title" not in md
        assert "office_author" not in md
        assert "office_subject" not in md
        assert md["paragraph_count"] == 0
        assert md["word_count"] == 0
        assert md["text_preview"] == ""
        assert md["tables_count"] == 0
        assert "tables_rows_total" not in md
        assert "tables_cells_total" not in md
        assert md["sections_count"] == 0
        assert asset.quality == pytest.approx(0.4)


class TestXlsxExtraction:
    def test_full_with_props(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        path = _make_file(tmp_path, "sheet.xlsx")
        sheets = {"Hoja1": FakeWorksheet(10), "Hoja2": FakeWorksheet(None)}
        wb = FakeWorkbook(
            sheets,
            SimpleNamespace(title="T", subject="", keywords="K", category="C", description="   ", creator="U"),
        )
        calls: list[dict[str, Any]] = []

        def fake_load(path_str: str, **kwargs: Any) -> FakeWorkbook:
            calls.append(kwargs)
            return wb

        monkeypatch.setitem(sys.modules, "openpyxl", SimpleNamespace(load_workbook=fake_load))
        monkeypatch.setattr(office, "_HAS_OPENPYXL", True)

        result = office.OfficeExtractor().extract(AssetSource("filesystem", str(path)))
        assert calls == [{"read_only": True, "data_only": True}]
        assert wb.closed
        asset = _asset_of(result)
        assert asset.asset_type == AssetType.OFFICE_SHEET
        md = asset.metadata
        assert md["office_title"] == "T"
        assert md["office_keywords"] == "K"
        assert md["office_category"] == "C"
        assert md["office_creator"] == "U"
        assert "office_subject" not in md
        assert "office_description" not in md
        assert md["sheet_names"] == ["Hoja1", "Hoja2"]
        assert md["sheet_count"] == 2
        assert md["rows_total"] == 10
        assert result.warnings == ["Row counts may be approximate (read_only mode)"]
        assert asset.quality == pytest.approx(0.7)

    def test_without_props(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        path = _make_file(tmp_path, "sheet.xlsx")
        wb = FakeWorkbook({"Hoja1": FakeWorksheet(3)}, None)
        monkeypatch.setitem(sys.modules, "openpyxl", SimpleNamespace(load_workbook=lambda p, **k: wb))
        monkeypatch.setattr(office, "_HAS_OPENPYXL", True)

        result = office.OfficeExtractor().extract(AssetSource("filesystem", str(path)))
        asset = _asset_of(result)
        assert "office_title" not in asset.metadata
        assert asset.metadata["sheet_count"] == 1
        assert asset.metadata["rows_total"] == 3
        assert asset.quality == pytest.approx(0.55)
        assert wb.closed


class TestPptxExtraction:
    def test_full_with_text_shapes(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        path = _make_file(tmp_path, "slides.pptx")
        slide1 = SimpleNamespace(
            shapes=[
                SimpleNamespace(text="Hola mundo"),
                SimpleNamespace(text=""),
                SimpleNamespace(text="   "),
                object(),
            ]
        )
        slide2 = SimpleNamespace(shapes=[])
        prs = SimpleNamespace(
            core_properties=SimpleNamespace(
                title="T",
                author="A",
                subject=EmptyStr(),
                keywords="",
                comments="",
                category="",
                last_modified_by="L",
                created="2026-01-01T00:00:00Z",
                modified="",
            ),
            slides=[slide1, slide2],
            slide_width=9144000,
            slide_height=6858000,
        )
        monkeypatch.setitem(sys.modules, "pptx", SimpleNamespace(Presentation=lambda p: prs))
        monkeypatch.setattr(office, "_HAS_PPTX", True)

        result = office.OfficeExtractor().extract(AssetSource("filesystem", str(path)))
        assert result.errors == []
        asset = _asset_of(result)
        assert asset.asset_type == AssetType.OFFICE_SLIDE
        md = asset.metadata
        assert md["office_title"] == "T"
        assert md["office_author"] == "A"
        assert md["office_last_modified_by"] == "L"
        assert md["office_created"] == "2026-01-01T00:00:00Z"
        assert "office_subject" not in md
        assert md["slide_count"] == 2
        assert md["slide_width"] == 9144000
        assert md["slide_height"] == 6858000
        assert md["shapes_total"] == 4
        assert md["text_preview"] == "Hola mundo"
        assert asset.quality == pytest.approx(0.8)

    def test_without_text_shapes(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        path = _make_file(tmp_path, "slides.pptx")
        prs = SimpleNamespace(
            core_properties=SimpleNamespace(
                title="",
                author="",
                subject="",
                keywords="",
                comments="",
                category="",
                last_modified_by="",
                created="",
                modified="",
            ),
            slides=[SimpleNamespace(shapes=[object()])],
            slide_width=100,
            slide_height=200,
        )
        monkeypatch.setitem(sys.modules, "pptx", SimpleNamespace(Presentation=lambda p: prs))
        monkeypatch.setattr(office, "_HAS_PPTX", True)

        result = office.OfficeExtractor().extract(AssetSource("filesystem", str(path)))
        asset = _asset_of(result)
        md = asset.metadata
        assert md["shapes_total"] == 1
        assert "office_title" not in md
        assert "text_preview" not in md
        assert asset.quality == pytest.approx(0.55)


class TestComputeOfficeQuality:
    def test_base_clean(self) -> None:
        assert office._compute_office_quality({}) == pytest.approx(0.4)

    def test_content_detection(self) -> None:
        assert office._compute_office_quality({"paragraph_count": 1}) == pytest.approx(0.55)
        assert office._compute_office_quality({"sheet_count": 2}) == pytest.approx(0.55)
        assert office._compute_office_quality({"slide_count": 3}) == pytest.approx(0.55)

    def test_title_and_author(self) -> None:
        assert office._compute_office_quality({"office_title": "T", "office_author": "A"}) == pytest.approx(0.65)

    def test_word_threshold(self) -> None:
        assert office._compute_office_quality({"word_count": 50}) == pytest.approx(0.4)
        assert office._compute_office_quality({"word_count": 51}) == pytest.approx(0.55)

    def test_tables(self) -> None:
        assert office._compute_office_quality({"tables_count": 1}) == pytest.approx(0.55)

    def test_degraded_loses_bonus(self) -> None:
        assert office._compute_office_quality({"_degraded": True}) == pytest.approx(0.3)

    def test_clamped_at_one(self) -> None:
        full = {
            "paragraph_count": 1,
            "office_title": "T",
            "office_author": "A",
            "word_count": 100,
            "tables_count": 2,
        }
        assert office._compute_office_quality(full) == pytest.approx(1.0)
        assert office._compute_office_quality({**full, "_degraded": True}) == pytest.approx(1.0)
