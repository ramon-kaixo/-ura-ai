"""VideoExtractor — extrae metadatos de archivos de vídeo.

Dependencias opcionales:
  - ffprobe (metadatos técnicos)
  - ffmpeg (thumbnails)
  - opencv-python (scene detection)
  - whisper (transcripción)

Extrae:
  - duración, resolución, fps, bitrate, codec video/audio
  - 3 thumbnails (10%, 50%, 90%) con ffmpeg
  - scene detection con opencv
  - transcripción con whisper
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

log = logging.getLogger("ura.knowledge.extractors.video")

_VIDEO_MIMES = ["video/mp4", "video/webm", "video/avi", "video/mov"]

MAX_VIDEO_SIZE = 4 * 1024 * 1024 * 1024
THUMBNAIL_TIMES = [0.1, 0.5, 0.9]

_HAS_FFPROBE = shutil.which("ffprobe") is not None
_HAS_FFMPEG = shutil.which("ffmpeg") is not None
_HAS_OPENCV = _check_import("cv2", "opencv-python")
_HAS_WHISPER = _check_import("whisper", "openai-whisper")


def _get_whisper_model() -> Any:
    if not hasattr(_get_whisper_model, "model"):
        import whisper

        _get_whisper_model.model = whisper.load_model("base")
    return _get_whisper_model.model


class VideoExtractor:
    """Extractor para archivos de vídeo.

    Uso:
        extractor = VideoExtractor()
        result = extractor.extract(source)
    """

    id: str = "video"
    version: str = "1.0.0"
    supported_mime_types: list[str] = _VIDEO_MIMES
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

            if size > MAX_VIDEO_SIZE:
                return ExtractionResult(
                    errors=[f"File too large: {size} bytes (max {MAX_VIDEO_SIZE})"],
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
                metadata["_degraded_ffprobe"] = True

            if _HAS_FFMPEG:
                self._extract_thumbnails(path_str, metadata)

            if _HAS_OPENCV:
                self._detect_scenes(path_str, metadata)

            if _HAS_WHISPER:
                self._transcribe_video(path_str, metadata)

            asset = KnowledgeAsset(
                asset_id=content_sha256[:16],
                asset_type=AssetType.VIDEO,
                metadata=metadata,
                source=source,
                quality=_compute_video_quality(metadata),
                created_at=now,
                updated_at=now,
            )

            return ExtractionResult(
                asset=asset,
                duration_ms=(time.monotonic() - t0) * 1000,
            )

        except Exception as exc:
            log.exception("Video extraction error for %s", path_str)
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
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60, check=False)
            if result.returncode != 0:
                log.warning("ffprobe failed for %s: %s", path_str, result.stderr.strip())
                metadata["_degraded_ffprobe"] = True
                return

            data = json.loads(result.stdout)
            fmt = data.get("format", {})
            streams = data.get("streams", [])

            if fmt:
                for key, mk in (
                    ("duration", "duration_sec"),
                    ("bit_rate", "bitrate"),
                    ("format_name", "container"),
                    ("size", "size_bytes"),
                ):
                    val = fmt.get(key)
                    if val is not None:
                        metadata[f"video_{mk}"] = val

            for stream in streams:
                codec_type = stream.get("codec_type")
                if codec_type == "video":
                    for key, mk in (
                        ("codec_name", "video_codec"),
                        ("width", "width"),
                        ("height", "height"),
                        ("r_frame_rate", "fps"),
                        ("bit_rate", "video_bitrate"),
                    ):
                        val = stream.get(key)
                        if val is not None:
                            metadata[f"video_{mk}"] = val
                elif codec_type == "audio":
                    for key, mk in (
                        ("codec_name", "audio_codec"),
                        ("sample_rate", "audio_sample_rate"),
                        ("channels", "audio_channels"),
                    ):
                        val = stream.get(key)
                        if val is not None:
                            metadata[f"video_{mk}"] = val

            log.info("Extracted video metadata for %s", path_str)

        except subprocess.TimeoutExpired:
            log.warning("ffprobe timed out for %s", path_str)
            metadata["_degraded_ffprobe"] = True

    @staticmethod
    def _extract_thumbnails(path_str: str, metadata: dict[str, Any]) -> None:
        duration = metadata.get("video_duration_sec")
        if not duration:
            return

        duration = float(duration)
        thumb_dir = Path(path_str).parent / "thumbs"
        thumb_dir.mkdir(exist_ok=True)
        base = Path(path_str).stem

        thumbnails: list[str] = []
        for pct in THUMBNAIL_TIMES:
            seek = duration * pct
            thumb_path = str(thumb_dir / f"{base}_{int(pct * 100)}.jpg")
            cmd = [
                "ffmpeg",
                "-y",
                "-ss",
                str(seek),
                "-i",
                path_str,
                "-vframes",
                "1",
                "-q:v",
                "2",
                thumb_path,
            ]
            try:
                subprocess.run(cmd, capture_output=True, timeout=30, check=False)
                if Path(thumb_path).exists():
                    thumbnails.append(thumb_path)
            except subprocess.TimeoutExpired:
                log.warning("Thumbnail generation timed out at %d%% for %s", int(pct * 100), path_str)

        if thumbnails:
            metadata["thumbnails"] = thumbnails
            log.info("Generated %d thumbnails for %s", len(thumbnails), path_str)

    @staticmethod
    def _detect_scenes(path_str: str, metadata: dict[str, Any]) -> None:
        try:
            import cv2

            cap = cv2.VideoCapture(path_str)
            try:
                fps = cap.get(cv2.CAP_PROP_FPS)
                total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                if total_frames <= 0:
                    return

                metadata["video_total_frames"] = total_frames
                if fps > 0:
                    metadata["video_fps_calculated"] = round(fps, 2)

                scene_count = 0
                prev_frame = None
                frame_interval = max(1, int(fps * 2))

                for frame_idx in range(0, total_frames, frame_interval):
                    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
                    ret, frame = cap.read()
                    if not ret:
                        break

                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    if prev_frame is not None:
                        diff = cv2.absdiff(gray, prev_frame).mean()
                        if diff > 30:
                            scene_count += 1
                    prev_frame = gray

                if scene_count > 0:
                    metadata["video_scene_count"] = scene_count

            finally:
                cap.release()

        except Exception as exc:
            log.warning("Scene detection failed for %s: %s", path_str, exc)

    @staticmethod
    def _transcribe_video(path_str: str, metadata: dict[str, Any]) -> None:
        try:
            model = _get_whisper_model()
            result = model.transcribe(path_str)
            text = result.get("text", "").strip()
            if text:
                metadata["transcript"] = text[:2000]
                metadata["transcript_length"] = len(text)
            metadata["transcription_performed"] = True
            metadata["transcription_language"] = result.get("language", "")
        except Exception as exc:
            log.warning("Transcription failed for %s: %s", path_str, exc)
            metadata["transcription_performed"] = False
            metadata["transcription_error"] = str(exc)


def _compute_video_quality(metadata: dict[str, Any]) -> float:
    q = 0.3
    if metadata.get("video_duration_sec"):
        q += 0.15
    if metadata.get("video_video_codec"):
        q += 0.15
    if metadata.get("video_width", 0) > 0:
        q += 0.1
    if metadata.get("video_fps"):
        q += 0.1
    if metadata.get("thumbnails"):
        q += 0.1
    if not metadata.get("_degraded_ffprobe", False):
        q += 0.1
    if metadata.get("transcription_performed") and metadata.get("transcript"):
        q += 0.2
    return min(q, 1.0)


_registry = get_registry()
_registry.register(VideoExtractor())
