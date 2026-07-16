"""ImageExtractor — extrae metadatos de imágenes.

Dependencias obligatorias:
  - Pillow (PIL)

Dependencias opcionales:
  - pytesseract (OCR para imágenes con texto)

Extrae:
  - EXIF, GPS, device, date_taken, dimensiones, formato
  - thumbnail (256px lado mayor)
  - orientación, modo de color, perfil ICC
  - texto vía OCR (opcional)

Protección:
  - Decompression bomb: MAX_IMAGE_PIXELS=100MP, validación previa
  - Límite de tamaño: MAX_IMAGE_SIZE=100MB
"""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from knowledge.engine.extractors.base import (
    ExtractionResult,
    _check_import,
    _hash_stream,
    get_registry,
)
from knowledge.engine.ontology.internal import AssetSource, AssetType, KnowledgeAsset

log = logging.getLogger("ura.knowledge.extractors.image")

_IMAGE_MIMES = ["image/jpeg", "image/png", "image/webp", "image/gif"]

MAX_IMAGE_PIXELS = 100 * 1024 * 1024
MAX_IMAGE_DIMENSION = 20_000
MAX_IMAGE_SIZE = 100 * 1024 * 1024
THUMBNAIL_SIZE = 256

_HAS_PILLOW = _check_import("PIL", "Pillow")
_HAS_TESSERACT = _check_import("pytesseract", "pytesseract")


class ImageExtractor:
    """Extractor para imágenes.

    Uso:
        extractor = ImageExtractor()
        result = extractor.extract(source)
    """

    id: str = "image"
    version: str = "1.0.0"
    supported_mime_types: list[str] = _IMAGE_MIMES
    cost: str = "O(n)"

    def extract(self, source: AssetSource) -> ExtractionResult:
        t0 = time.monotonic()
        path_str = source.location

        if not Path(path_str).exists():
            return ExtractionResult(
                errors=[f"File not found: {path_str}"],
                duration_ms=(time.monotonic() - t0) * 1000,
            )

        try:
            content_sha256, size = _hash_stream(path_str)

            if size > MAX_IMAGE_SIZE:
                return ExtractionResult(
                    errors=[f"File too large: {size} bytes (max {MAX_IMAGE_SIZE})"],
                    duration_ms=(time.monotonic() - t0) * 1000,
                )

            now = datetime.now(UTC).isoformat()
            metadata: dict[str, Any] = {
                "size": size,
                "content_sha256": content_sha256,
                "format": Path(path_str).suffix.lower().lstrip("."),
                "_extractor": self.id,
                "_extractor_version": self.version,
                "wraps": f"source:{path_str}",
                "extracted_at": now,
            }

            if _HAS_PILLOW:
                self._extract_with_pillow(path_str, metadata)
            else:
                log.warning("Pillow not available, extracting basic metadata for %s", path_str)
                metadata["_degraded"] = True
                metadata["_degraded_reason"] = "Pillow not installed"

            asset = KnowledgeAsset(
                asset_id=content_sha256[:16],
                asset_type=AssetType.IMAGE,
                metadata=metadata,
                source=source,
                quality=_compute_image_quality(metadata),
                created_at=now,
                updated_at=now,
            )

            return ExtractionResult(
                asset=asset,
                duration_ms=(time.monotonic() - t0) * 1000,
            )

        except Exception as exc:
            log.exception("Image extraction error for %s", path_str)
            return ExtractionResult(
                errors=[f"Extraction error: {exc}"],
                duration_ms=(time.monotonic() - t0) * 1000,
            )

    def _extract_with_pillow(self, path_str: str, metadata: dict[str, Any]) -> None:
        from PIL import Image

        try:
            with Image.open(path_str) as img:
                width, height = img.size
                if width > MAX_IMAGE_DIMENSION or height > MAX_IMAGE_DIMENSION:
                    raise ImageSizeError(
                        f"Image dimensions too large: {width}x{height} (max {MAX_IMAGE_DIMENSION}px per side)"
                    )

                if width * height > MAX_IMAGE_PIXELS:
                    raise ImageSizeError(
                        f"Image too large: {width}x{height} = {width * height}px (max {MAX_IMAGE_PIXELS}px)"
                    )

                if width * height >= MAX_IMAGE_PIXELS // 2:
                    log.warning("Large image: %s (%dx%d = %dpx)", path_str, width, height, width * height)

                metadata["width"] = width
                metadata["height"] = height
                metadata["format"] = img.format or metadata.get("format", "")
                metadata["mode"] = img.mode

                self._extract_exif(img, metadata)
                self._extract_thumbnail(img, path_str, metadata)

                if _HAS_TESSERACT:
                    self._run_ocr(img, metadata)
        except ImageSizeError:
            raise
        except Exception as exc:
            metadata["_degraded"] = True
            metadata["_degraded_reason"] = f"Cannot open image: {exc}"

    @staticmethod
    def _extract_exif(img: Any, metadata: dict[str, Any]) -> None:
        from PIL import ExifTags

        exif_data = img.getexif()
        if not exif_data:
            return

        for tag_id, value in exif_data.items():
            tag_name = ExifTags.TAGS.get(tag_id, "")
            if tag_name in (
                "Make",
                "Model",
                "DateTimeOriginal",
                "Orientation",
                "Software",
                "XResolution",
                "YResolution",
                "Flash",
                "ISOSpeedRatings",
                "FNumber",
                "ExposureTime",
                "FocalLength",
                "LensModel",
                "WhiteBalance",
            ):
                metadata[f"exif_{tag_name.lower()}"] = str(value)

        gps_info = exif_data.get_ifd(0x8825)
        if gps_info:
            gps_data = {}
            for tag_id, value in gps_info.items():
                tag_name = ExifTags.GPSTAGS.get(tag_id, f"gps_{tag_id}")
                gps_data[tag_name] = str(value)
            if gps_data:
                metadata["gps"] = gps_data

    @staticmethod
    def _extract_thumbnail(img: Any, path_str: str, metadata: dict[str, Any]) -> None:
        try:
            thumb = img.copy()
            thumb.thumbnail((THUMBNAIL_SIZE, THUMBNAIL_SIZE))
            thumb_path = f"{path_str}.thumb.jpg"
            thumb.save(thumb_path, "JPEG", quality=70)
            metadata["thumbnail"] = thumb_path
            metadata["thumbnail_size"] = Path(thumb_path).stat().st_size
        except Exception as exc:
            log.warning("Cannot create thumbnail for %s: %s", path_str, exc)

    @staticmethod
    def _run_ocr(img: Any, metadata: dict[str, Any]) -> None:
        try:
            import pytesseract

            text = pytesseract.image_to_string(img)
            if text.strip():
                metadata["ocr_text"] = text.strip()
                metadata["ocr_text_length"] = len(text.strip())
            metadata["ocr_performed"] = True
        except Exception as exc:
            log.warning("OCR failed for image: %s", exc)
            metadata["ocr_performed"] = False
            metadata["ocr_error"] = str(exc)


class ImageSizeError(ValueError):
    """La imagen excede los límites de tamaño permitidos."""


def _compute_image_quality(metadata: dict[str, Any]) -> float:
    q = 0.3
    if metadata.get("width", 0) > 0 and metadata.get("height", 0) > 0:
        q += 0.15
    if metadata.get("exif_make") or metadata.get("exif_model"):
        q += 0.15
    if metadata.get("exif_datetimeoriginal"):
        q += 0.1
    if metadata.get("gps"):
        q += 0.15
    if metadata.get("thumbnail"):
        q += 0.1
    if metadata.get("ocr_performed") and metadata.get("ocr_text"):
        q += 0.15
    return min(q, 1.0)


_registry = get_registry()
_registry.register(ImageExtractor())
