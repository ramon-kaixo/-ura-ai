"""AudioExtractor — extrae metadatos de archivos de audio.

Dependencias opcionales:
  - ffprobe (metadatos técnicos: duración, bitrate, codec)
  - whisper (transcripción, semáforo 1)

Extrae:
  - duración, bitrate, codec, sample rate, canales
  - transcripción con whisper (opcional, background)
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
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

log = logging.getLogger("ura.knowledge.extractors.audio")

_AUDIO_MIMES = ["audio/mp3", "audio/wav", "audio/flac", "audio/ogg"]

MAX_AUDIO_SIZE = 500 * 1024 * 1024

_HAS_FFPROBE = shutil.which("ffprobe") is not None
_HAS_WHISPER = _check_import("whisper", "openai-whisper")


def _get_whisper_model() -> Any:
    if not hasattr(_get_whisper_model, "model"):
        import whisper

        _get_whisper_model.model = whisper.load_model("base")
    return _get_whisper_model.model


class AudioExtractor:
    """Extractor para archivos de audio.

    Uso:
        extractor = AudioExtractor()
        result = extractor.extract(source)
    """

    id: str = "audio"
    version: str = "1.0.0"
    supported_mime_types: list[str] = _AUDIO_MIMES
    cost: str = "O(1)"

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

            if size > MAX_AUDIO_SIZE:
                return ExtractionResult(
                    errors=[f"File too large: {size} bytes (max {MAX_AUDIO_SIZE})"],
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

            if _HAS_FFPROBE:
                self._extract_ffprobe(path_str, metadata)
            else:
                log.warning("ffprobe not available for %s", path_str)
                metadata["_degraded_ffprobe"] = True

            if _HAS_WHISPER:
                self._transcribe(path_str, metadata)

            asset = KnowledgeAsset(
                asset_id=content_sha256[:16],
                asset_type=AssetType.AUDIO,
                metadata=metadata,
                source=source,
                quality=_compute_audio_quality(metadata),
                created_at=now,
                updated_at=now,
            )

            return ExtractionResult(
                asset=asset,
                duration_ms=(time.monotonic() - t0) * 1000,
            )

        except Exception as exc:
            log.exception("Audio extraction error for %s", path_str)
            return ExtractionResult(
                errors=[f"Extraction error: {exc}"],
                duration_ms=(time.monotonic() - t0) * 1000,
            )

    @staticmethod
    def _extract_ffprobe(path_str: str, metadata: dict[str, Any]) -> None:
        cmd = [
            "ffprobe",
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            path_str,
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, check=False)
            if result.returncode != 0:
                log.warning("ffprobe failed for %s: %s", path_str, result.stderr.strip())
                metadata["_degraded_ffprobe"] = True
                return

            data = json.loads(result.stdout)
            fmt = data.get("format", {})
            streams = data.get("streams", [])

            if fmt:
                for key, meta_key in (
                    ("duration", "duration_sec"),
                    ("bit_rate", "bitrate"),
                    ("format_name", "container"),
                ):
                    val = fmt.get(key)
                    if val:
                        metadata[f"audio_{meta_key}"] = val

            for stream in streams:
                if stream.get("codec_type") == "audio":
                    for key, meta_key in (
                        ("codec_name", "codec"),
                        ("sample_rate", "sample_rate"),
                        ("channels", "channels"),
                        ("channel_layout", "channel_layout"),
                    ):
                        val = stream.get(key)
                        if val is not None:
                            metadata[f"audio_{meta_key}"] = val

                    metadata["audio_codec"] = stream.get("codec_name", "")
                    break

            log.info("Extracted audio metadata for %s", path_str)

        except subprocess.TimeoutExpired:
            log.warning("ffprobe timed out for %s", path_str)
            metadata["_degraded_ffprobe"] = True
        except json.JSONDecodeError as exc:
            log.warning("ffprobe output parse error for %s: %s", path_str, exc)
            metadata["_degraded_ffprobe"] = True

    @staticmethod
    def _transcribe(path_str: str, metadata: dict[str, Any]) -> None:
        try:
            model = _get_whisper_model()
            result = model.transcribe(path_str)
            text = result.get("text", "").strip()
            if text:
                metadata["transcript"] = text[:2000]
                metadata["transcript_length"] = len(text)
            metadata["transcription_performed"] = True
            metadata["transcription_language"] = result.get("language", "")
            log.info("Transcription completed for %s (%d chars)", path_str, len(text))
        except Exception as exc:
            log.warning("Transcription failed for %s: %s", path_str, exc)
            metadata["transcription_performed"] = False
            metadata["transcription_error"] = str(exc)


def _compute_audio_quality(metadata: dict[str, Any]) -> float:
    q = 0.3
    if metadata.get("audio_duration_sec"):
        q += 0.15
    if metadata.get("audio_codec"):
        q += 0.15
    if metadata.get("audio_sample_rate"):
        q += 0.1
    if metadata.get("audio_bitrate"):
        q += 0.1
    if metadata.get("transcription_performed") and metadata.get("transcript"):
        q += 0.2
    if not metadata.get("_degraded_ffprobe", False):
        q += 0.1
    return min(q, 1.0)


_registry = get_registry()
_registry.register(AudioExtractor())
