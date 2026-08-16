"""Cobertura 100x100 de knowledge/engine/extractors/video.py (TASK-20260815-003).

Cubre VideoExtractor (extract, _enrich_metadata, _probe_format, _probe_streams,
_extract_ffprobe, _extract_thumbnails, _detect_scenes, _transcribe_video),
_get_whisper_model y _compute_video_quality con mocks de ffprobe/ffmpeg
(subprocess.run), cv2 (sys.modules), whisper (sys.modules) y de los flags de
disponibilidad de herramientas. El registro en el registry se cubre con la
importación del módulo.
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from knowledge.engine.extractors import video
from knowledge.engine.extractors.base import get_registry
from knowledge.engine.extractors.video import VideoExtractor, _compute_video_quality
from knowledge.engine.ontology.internal import AssetSource, AssetType

_OK_FLAGS = ("_HAS_FFPROBE", "_HAS_FFMPEG", "_HAS_OPENCV", "_HAS_WHISPER")


def _disable_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    """Desactiva los 4 flags de disponibilidad de herramientas."""
    for flag in _OK_FLAGS:
        monkeypatch.setattr(video, flag, False)


class FakeRun:
    """Simula subprocess.run con respuestas secuenciales (resultado o excepción)."""

    def __init__(self, results: list[Any] | None = None) -> None:
        self.results = list(results or [])
        self.calls: list[list[str]] = []

    def run(self, cmd: list[str], *args: Any, **kwargs: Any) -> Any:
        self.calls.append(cmd)
        if self.results:
            result = self.results.pop(0)
            if isinstance(result, BaseException):
                raise result
            return result
        return SimpleNamespace(returncode=0, stdout="", stderr="")


class FakeFrame:
    """Frame simulado; diff_out alimenta absdiff(...).mean()."""

    def __init__(self, diff_out: float = 0.0) -> None:
        self.diff_out = diff_out


class FakeMeanResult:
    """Resultado simulado de absdiff(...).mean()."""

    def __init__(self, value: float) -> None:
        self.value = value

    def mean(self) -> float:
        return self.value


class FakeCap:
    """VideoCapture simulado: get/set/read/release sobre una lista de reads."""

    def __init__(self, reads: list[tuple[bool, FakeFrame | None]], fps: float = 30.0, total_frames: int | None = None) -> None:
        self._reads = list(reads)
        self._fps = fps
        self._total = total_frames if total_frames is not None else len(self._reads)
        self.released = False

    def get(self, prop: int) -> Any:
        if prop == FakeCv2.CAP_PROP_FPS:
            return self._fps
        if prop == FakeCv2.CAP_PROP_FRAME_COUNT:
            return self._total
        return 0

    def set(self, prop: int, value: Any) -> None:
        return None

    def read(self) -> tuple[bool, FakeFrame | None]:
        if self._reads:
            return self._reads.pop(0)
        return False, None

    def release(self) -> None:
        self.released = True


class FakeCv2:
    """Módulo cv2 simulado con constantes, VideoCapture, cvtColor y absdiff."""

    CAP_PROP_FPS = 5
    CAP_PROP_FRAME_COUNT = 6
    CAP_PROP_POS_FRAMES = 7
    COLOR_BGR2GRAY = 8

    def __init__(self, cap: FakeCap | None = None, capture_error: Exception | None = None) -> None:
        self.cap = cap
        self.capture_error = capture_error
        self.last_capture_path: str | None = None

    def VideoCapture(self, path_str: str) -> FakeCap:
        self.last_capture_path = path_str
        if self.capture_error is not None:
            raise self.capture_error
        return self.cap or FakeCap([])

    def cvtColor(self, frame: FakeFrame, code: int) -> FakeFrame:
        return frame

    def absdiff(self, frame_a: FakeFrame, frame_b: FakeFrame) -> FakeMeanResult:
        return FakeMeanResult(frame_a.diff_out)


class FakeWhisperModel:
    """Modelo whisper simulado con transcribe(path) -> dict."""

    def __init__(self, text: str, language: str = "es") -> None:
        self.result = {"text": text, "language": language}
        self.transcribed_paths: list[str] = []

    def transcribe(self, path_str: str) -> dict[str, Any]:
        self.transcribed_paths.append(path_str)
        return self.result


class FakeWhisper:
    """Módulo whisper simulado con load_model(name)."""

    def __init__(self) -> None:
        self.loaded: list[str] = []
        self.model: Any = None

    def load_model(self, name: str) -> Any:
        self.loaded.append(name)
        self.model = FakeWhisperModel("hola")
        return self.model


def _install_cv2(monkeypatch: pytest.MonkeyPatch, fake: FakeCv2) -> None:
    monkeypatch.setitem(sys.modules, "cv2", fake)


def _install_whisper(monkeypatch: pytest.MonkeyPatch, fake: FakeWhisper) -> None:
    monkeypatch.setitem(sys.modules, "whisper", fake)


def _make_video_file(tmp_path: Path, name: str = "clip.mp4", content: bytes = b"fake-video") -> Path:
    path = tmp_path / name
    path.write_bytes(content)
    return path


class TestVideoExtractor:
    """Tests de VideoExtractor.extract."""

    def test_extract_file_missing(self, tmp_path: Path) -> None:
        missing = str(tmp_path / "missing.mp4")
        result = VideoExtractor().extract(AssetSource(kind="filesystem", location=missing))
        assert result.errors == [f"File not found: {missing}"]
        assert result.asset is None
        assert result.duration_ms >= 0

    def test_extract_success_without_tools(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        path = _make_video_file(tmp_path)
        _disable_tools(monkeypatch)
        source = AssetSource(kind="filesystem", location=str(path))
        result = VideoExtractor().extract(source)
        assert result.errors == []
        assert result.asset is not None
        assert result.asset.asset_type == AssetType.VIDEO
        assert result.asset.source is source
        assert result.asset.metadata["size"] == len(b"fake-video")
        assert result.asset.metadata["format"] == "mp4"
        assert result.asset.metadata["_extractor"] == "video"
        assert result.asset.metadata["_extractor_version"] == "1.0.0"
        assert result.asset.metadata["wraps"] == f"source:{path}"
        assert result.asset.metadata["_degraded_ffprobe"] is True
        assert result.asset.metadata["content_sha256"][:16] == result.asset.asset_id
        assert result.asset.quality == 0.3
        assert result.duration_ms >= 0

    def test_extract_file_too_large(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        path = _make_video_file(tmp_path, name="big.mp4")
        monkeypatch.setattr(video, "_hash_stream", lambda p: ("sha", video.MAX_VIDEO_SIZE + 1))
        result = VideoExtractor().extract(AssetSource(kind="filesystem", location=str(path)))
        assert result.errors == [f"File too large: {video.MAX_VIDEO_SIZE + 1} bytes (max {video.MAX_VIDEO_SIZE})"]
        assert result.asset is None

    def test_extract_exception_propagated_as_errors(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        path = _make_video_file(tmp_path, name="err.mp4")
        _disable_tools(monkeypatch)

        def boom(p: Any) -> tuple[str, int]:
            raise OSError("disk error")

        monkeypatch.setattr(video, "_hash_stream", boom)
        result = VideoExtractor().extract(AssetSource(kind="filesystem", location=str(path)))
        assert result.errors == ["Extraction error: disk error"]
        assert result.asset is None

    def test_extract_ffprobe_invalid_json_propagates(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        path = _make_video_file(tmp_path, name="badprobe.mp4")
        monkeypatch.setattr(video, "_HAS_FFPROBE", True)
        monkeypatch.setattr(video, "_HAS_FFMPEG", False)
        monkeypatch.setattr(video, "_HAS_OPENCV", False)
        monkeypatch.setattr(video, "_HAS_WHISPER", False)
        fake_run = FakeRun([SimpleNamespace(returncode=0, stdout="not-json", stderr="")])
        monkeypatch.setattr(video.subprocess, "run", fake_run.run)
        result = VideoExtractor().extract(AssetSource(kind="filesystem", location=str(path)))
        assert len(result.errors) == 1
        assert result.errors[0].startswith("Extraction error: ")
        assert "Expecting value" in result.errors[0]
        assert result.asset is None


class TestEnrichMetadata:
    """Tests de VideoExtractor._enrich_metadata según flags de herramientas."""

    def test_all_tools_called_when_available(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for flag in _OK_FLAGS:
            monkeypatch.setattr(video, flag, True)
        calls: list[str] = []

        def fake_ffprobe(_self: Any, _path: str, metadata: dict[str, Any]) -> None:
            calls.append("ffprobe")
            metadata["_ffprobe_called"] = True

        def fake_thumbnails(_self: Any, _path: str, metadata: dict[str, Any]) -> None:
            calls.append("thumbnails")
            metadata["_thumbnails_called"] = True

        def fake_scenes(_self: Any, _path: str, metadata: dict[str, Any]) -> None:
            calls.append("scenes")
            metadata["_scenes_called"] = True

        def fake_transcribe(_self: Any, _path: str, metadata: dict[str, Any]) -> None:
            calls.append("transcribe")
            metadata["_transcribe_called"] = True

        monkeypatch.setattr(VideoExtractor, "_extract_ffprobe", fake_ffprobe)
        monkeypatch.setattr(VideoExtractor, "_extract_thumbnails", fake_thumbnails)
        monkeypatch.setattr(VideoExtractor, "_detect_scenes", fake_scenes)
        monkeypatch.setattr(VideoExtractor, "_transcribe_video", fake_transcribe)
        metadata: dict[str, Any] = {}
        VideoExtractor()._enrich_metadata("/tmp/v.mp4", metadata)
        assert calls == ["ffprobe", "thumbnails", "scenes", "transcribe"]
        assert metadata["_ffprobe_called"] is True
        assert metadata["_thumbnails_called"] is True
        assert metadata["_scenes_called"] is True
        assert metadata["_transcribe_called"] is True

    def test_none_called_when_unavailable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _disable_tools(monkeypatch)
        calls: list[str] = []

        def spy(_self: Any, _path: str, _metadata: dict[str, Any]) -> None:
            calls.append("called")

        monkeypatch.setattr(VideoExtractor, "_extract_ffprobe", spy)
        monkeypatch.setattr(VideoExtractor, "_extract_thumbnails", spy)
        monkeypatch.setattr(VideoExtractor, "_detect_scenes", spy)
        monkeypatch.setattr(VideoExtractor, "_transcribe_video", spy)
        metadata: dict[str, Any] = {}
        VideoExtractor()._enrich_metadata("/tmp/v.mp4", metadata)
        assert calls == []
        assert metadata["_degraded_ffprobe"] is True

    def test_partial_tools(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(video, "_HAS_FFPROBE", True)
        monkeypatch.setattr(video, "_HAS_FFMPEG", False)
        monkeypatch.setattr(video, "_HAS_OPENCV", True)
        monkeypatch.setattr(video, "_HAS_WHISPER", False)
        calls: list[str] = []

        def fake_ffprobe(_self: Any, _path: str, metadata: dict[str, Any]) -> None:
            calls.append("ffprobe")
            metadata["_ffprobe_called"] = True

        def fake_scenes(_self: Any, _path: str, metadata: dict[str, Any]) -> None:
            calls.append("scenes")
            metadata["_scenes_called"] = True

        def spy(_self: Any, _path: str, _metadata: dict[str, Any]) -> None:
            calls.append("spy")

        monkeypatch.setattr(VideoExtractor, "_extract_ffprobe", fake_ffprobe)
        monkeypatch.setattr(VideoExtractor, "_extract_thumbnails", spy)
        monkeypatch.setattr(VideoExtractor, "_detect_scenes", fake_scenes)
        monkeypatch.setattr(VideoExtractor, "_transcribe_video", spy)
        metadata: dict[str, Any] = {}
        VideoExtractor()._enrich_metadata("/tmp/v.mp4", metadata)
        assert calls == ["ffprobe", "scenes"]
        assert metadata["_ffprobe_called"] is True
        assert metadata["_scenes_called"] is True
        assert "_degraded_ffprobe" not in metadata


class TestProbeFormat:
    """Tests de VideoExtractor._probe_format."""

    def test_maps_format_keys(self) -> None:
        metadata: dict[str, Any] = {}
        fmt = {"duration": "10.5", "bit_rate": "1000", "format_name": "mp4", "size": "123"}
        VideoExtractor._probe_format(metadata, fmt)
        assert metadata["video_duration_sec"] == "10.5"
        assert metadata["video_bitrate"] == "1000"
        assert metadata["video_container"] == "mp4"
        assert metadata["video_size_bytes"] == "123"

    def test_skips_missing_or_none_values(self) -> None:
        metadata: dict[str, Any] = {}
        VideoExtractor._probe_format(metadata, {"duration": None, "bit_rate": None, "format_name": None, "size": None})
        assert metadata == {}

        metadata2: dict[str, Any] = {"video_container": "keep"}
        VideoExtractor._probe_format(metadata2, {})
        assert metadata2 == {"video_container": "keep"}


class TestProbeStreams:
    """Tests de VideoExtractor._probe_streams."""

    def test_video_and_audio_streams(self) -> None:
        metadata: dict[str, Any] = {}
        streams = [
            {"codec_type": "video", "codec_name": "h264", "width": 1920, "height": 1080, "r_frame_rate": "30/1", "bit_rate": "5000"},
            {"codec_type": "audio", "codec_name": "aac", "sample_rate": "48000", "channels": 2},
        ]
        VideoExtractor._probe_streams(metadata, streams)
        assert metadata["video_video_codec"] == "h264"
        assert metadata["video_width"] == 1920
        assert metadata["video_height"] == 1080
        assert metadata["video_fps"] == "30/1"
        assert metadata["video_video_bitrate"] == "5000"
        assert metadata["video_audio_codec"] == "aac"
        assert metadata["video_audio_sample_rate"] == "48000"
        assert metadata["video_audio_channels"] == 2

    def test_other_streams_and_none_values_ignored(self) -> None:
        metadata: dict[str, Any] = {}
        streams = [
            {"codec_type": "data", "codec_name": "x"},
            {"codec_type": "video", "codec_name": None, "width": None},
            {"codec_type": "audio", "codec_name": None},
        ]
        VideoExtractor._probe_streams(metadata, streams)
        assert metadata == {}


class TestExtractFfprobe:
    """Tests de VideoExtractor._extract_ffprobe."""

    def test_success(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
        path = _make_video_file(tmp_path, name="probe.mp4")
        stdout = json.dumps(
            {
                "format": {"duration": "10.5", "format_name": "mp4"},
                "streams": [{"codec_type": "video", "codec_name": "h264", "width": 640, "height": 480}],
            }
        )
        fake_run = FakeRun([SimpleNamespace(returncode=0, stdout=stdout, stderr="")])
        monkeypatch.setattr(video.subprocess, "run", fake_run.run)
        metadata: dict[str, Any] = {}
        with caplog.at_level(logging.INFO, logger=video.log.name):
            VideoExtractor._extract_ffprobe(str(path), metadata)
        assert fake_run.calls == [["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", str(path)]]
        assert metadata["video_duration_sec"] == "10.5"
        assert metadata["video_container"] == "mp4"
        assert metadata["video_video_codec"] == "h264"
        assert "Extracted video metadata" in caplog.text

    def test_nonzero_returncode(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
        path = _make_video_file(tmp_path, name="fail.mp4")
        fake_run = FakeRun([SimpleNamespace(returncode=1, stdout="", stderr="boom\n")])
        monkeypatch.setattr(video.subprocess, "run", fake_run.run)
        metadata: dict[str, Any] = {}
        with caplog.at_level(logging.WARNING, logger=video.log.name):
            VideoExtractor._extract_ffprobe(str(path), metadata)
        assert metadata["_degraded_ffprobe"] is True
        assert "ffprobe failed" in caplog.text

    def test_timeout(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
        path = _make_video_file(tmp_path, name="slow.mp4")
        fake_run = FakeRun([subprocess.TimeoutExpired("ffprobe", 60)])
        monkeypatch.setattr(video.subprocess, "run", fake_run.run)
        metadata: dict[str, Any] = {}
        with caplog.at_level(logging.WARNING, logger=video.log.name):
            VideoExtractor._extract_ffprobe(str(path), metadata)
        assert metadata["_degraded_ffprobe"] is True
        assert "ffprobe timed out" in caplog.text

    def test_invalid_json_raises(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        path = _make_video_file(tmp_path, name="bad.mp4")
        fake_run = FakeRun([SimpleNamespace(returncode=0, stdout="not-json", stderr="")])
        monkeypatch.setattr(video.subprocess, "run", fake_run.run)
        with pytest.raises(json.JSONDecodeError):
            VideoExtractor._extract_ffprobe(str(path), {})

    def test_empty_format_and_streams(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
        path = _make_video_file(tmp_path, name="empty.mp4")
        fake_run = FakeRun([SimpleNamespace(returncode=0, stdout=json.dumps({"format": {}, "streams": []}), stderr="")])
        monkeypatch.setattr(video.subprocess, "run", fake_run.run)
        metadata: dict[str, Any] = {}
        with caplog.at_level(logging.INFO, logger=video.log.name):
            VideoExtractor._extract_ffprobe(str(path), metadata)
        assert metadata == {}
        assert "Extracted video metadata" in caplog.text


class TestExtractThumbnails:
    """Tests de VideoExtractor._extract_thumbnails."""

    def test_no_duration_does_nothing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake_run = FakeRun()
        monkeypatch.setattr(video.subprocess, "run", fake_run.run)
        metadata: dict[str, Any] = {}
        VideoExtractor._extract_thumbnails("/tmp/v.mp4", metadata)
        assert fake_run.calls == []
        assert "thumbnails" not in metadata

    def test_success_generates_thumbnails(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
        path = _make_video_file(tmp_path, name="clip.mp4")
        thumb_dir = Path(path).parent / "thumbs"
        thumb_dir.mkdir()
        for pct in video.THUMBNAIL_TIMES:
            (thumb_dir / f"clip_{int(pct * 100)}.jpg").write_bytes(b"jpg")
        fake_run = FakeRun()
        monkeypatch.setattr(video.subprocess, "run", fake_run.run)
        metadata: dict[str, Any] = {"video_duration_sec": "30.0"}
        with caplog.at_level(logging.INFO, logger=video.log.name):
            VideoExtractor._extract_thumbnails(str(path), metadata)
        assert len(fake_run.calls) == 3
        assert fake_run.calls[0][3] == "3.0"
        assert fake_run.calls[1][3] == "15.0"
        assert fake_run.calls[2][3] == "27.0"
        assert metadata["thumbnails"] == [str(thumb_dir / "clip_10.jpg"), str(thumb_dir / "clip_50.jpg"), str(thumb_dir / "clip_90.jpg")]
        assert "Generated 3 thumbnails" in caplog.text

    def test_timeout_skips_thumbnail(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
        path = _make_video_file(tmp_path, name="clip.mp4")
        thumb_dir = Path(path).parent / "thumbs"
        thumb_dir.mkdir()
        for pct in video.THUMBNAIL_TIMES:
            (thumb_dir / f"clip_{int(pct * 100)}.jpg").write_bytes(b"jpg")
        fake_run = FakeRun([subprocess.TimeoutExpired("ffmpeg", 30)])
        monkeypatch.setattr(video.subprocess, "run", fake_run.run)
        metadata: dict[str, Any] = {"video_duration_sec": "30.0"}
        with caplog.at_level(logging.WARNING, logger=video.log.name):
            VideoExtractor._extract_thumbnails(str(path), metadata)
        assert metadata["thumbnails"] == [str(thumb_dir / "clip_50.jpg"), str(thumb_dir / "clip_90.jpg")]
        assert "Thumbnail generation timed out" in caplog.text

    def test_no_output_files_keeps_no_thumbnails(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        path = _make_video_file(tmp_path, name="clip.mp4")
        fake_run = FakeRun()
        monkeypatch.setattr(video.subprocess, "run", fake_run.run)
        metadata: dict[str, Any] = {"video_duration_sec": "30.0"}
        VideoExtractor._extract_thumbnails(str(path), metadata)
        assert "thumbnails" not in metadata


class TestDetectScenes:
    """Tests de VideoExtractor._detect_scenes."""

    def test_no_frames_returns_early(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_cv2(monkeypatch, FakeCv2(cap=FakeCap([])))
        metadata: dict[str, Any] = {}
        VideoExtractor._detect_scenes("/tmp/v.mp4", metadata)
        assert metadata == {}

    def test_detects_scene_change(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake_cv2 = FakeCv2(
            cap=FakeCap(
                reads=[(True, FakeFrame(0.0)), (True, FakeFrame(50.0))],
                fps=30.0,
                total_frames=61,
            )
        )
        _install_cv2(monkeypatch, fake_cv2)
        metadata: dict[str, Any] = {}
        VideoExtractor._detect_scenes("/tmp/v.mp4", metadata)
        assert metadata["video_total_frames"] == 61
        assert metadata["video_fps_calculated"] == 30
        assert metadata["video_scene_count"] == 1

    def test_no_diff_no_scene_count(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_cv2(
            monkeypatch,
            FakeCv2(
                cap=FakeCap(
                    reads=[(True, FakeFrame(0.0)), (True, FakeFrame(30.0))],
                    fps=30.0,
                    total_frames=61,
                )
            ),
        )
        metadata: dict[str, Any] = {}
        VideoExtractor._detect_scenes("/tmp/v.mp4", metadata)
        assert metadata["video_total_frames"] == 61
        assert metadata["video_fps_calculated"] == 30
        assert "video_scene_count" not in metadata

    def test_read_failure_breaks_loop(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_cv2(
            monkeypatch,
            FakeCv2(
                cap=FakeCap(
                    reads=[(True, FakeFrame(0.0)), (False, None)],
                    fps=30.0,
                    total_frames=61,
                )
            ),
        )
        metadata: dict[str, Any] = {}
        VideoExtractor._detect_scenes("/tmp/v.mp4", metadata)
        assert metadata["video_total_frames"] == 61
        assert "video_scene_count" not in metadata

    def test_zero_fps_skips_calculated(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_cv2(
            monkeypatch,
            FakeCv2(
                cap=FakeCap(
                    reads=[(True, FakeFrame(0.0)), (True, FakeFrame(50.0))],
                    fps=0.0,
                    total_frames=61,
                )
            ),
        )
        metadata: dict[str, Any] = {}
        VideoExtractor._detect_scenes("/tmp/v.mp4", metadata)
        assert metadata["video_total_frames"] == 61
        assert "video_fps_calculated" not in metadata
        assert metadata["video_scene_count"] == 1

    def test_capture_error_logs_warning(self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
        _install_cv2(monkeypatch, FakeCv2(capture_error=RuntimeError("no camera")))
        metadata: dict[str, Any] = {"video_total_frames": 1}
        with caplog.at_level(logging.WARNING, logger=video.log.name):
            VideoExtractor._detect_scenes("/tmp/v.mp4", metadata)
        assert "Scene detection failed" in caplog.text
        assert metadata == {"video_total_frames": 1}


class TestTranscribeVideo:
    """Tests de VideoExtractor._transcribe_video."""

    def test_transcribes_text(self, monkeypatch: pytest.MonkeyPatch) -> None:
        model = FakeWhisperModel("  hola mundo  ", language="es")
        monkeypatch.setattr(video, "_get_whisper_model", lambda: model)
        metadata: dict[str, Any] = {}
        VideoExtractor._transcribe_video("/tmp/v.mp4", metadata)
        assert model.transcribed_paths == ["/tmp/v.mp4"]
        assert metadata["transcript"] == "hola mundo"
        assert metadata["transcript_length"] == len("hola mundo")
        assert metadata["transcription_performed"] is True
        assert metadata["transcription_language"] == "es"

    def test_empty_text_skips_transcript(self, monkeypatch: pytest.MonkeyPatch) -> None:
        model = FakeWhisperModel("   ", language="en")
        monkeypatch.setattr(video, "_get_whisper_model", lambda: model)
        metadata: dict[str, Any] = {}
        VideoExtractor._transcribe_video("/tmp/v.mp4", metadata)
        assert "transcript" not in metadata
        assert "transcript_length" not in metadata
        assert metadata["transcription_performed"] is True
        assert metadata["transcription_language"] == "en"

    def test_transcription_error(self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
        def error_transcribe(path_str: str) -> dict[str, Any]:
            raise RuntimeError("no model")

        monkeypatch.setattr(video, "_get_whisper_model", lambda: SimpleNamespace(transcribe=error_transcribe))
        metadata: dict[str, Any] = {}
        with caplog.at_level(logging.WARNING, logger=video.log.name):
            VideoExtractor._transcribe_video("/tmp/v.mp4", metadata)
        assert metadata["transcription_performed"] is False
        assert metadata["transcription_error"] == "no model"
        assert "Transcription failed" in caplog.text


class TestGetWhisperModel:
    """Tests de _get_whisper_model (carga lazy + caché en atributo de función)."""

    def test_loads_and_caches_model(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake_whisper = FakeWhisper()
        _install_whisper(monkeypatch, fake_whisper)
        monkeypatch.delattr(video._get_whisper_model, "model", raising=False)
        first = video._get_whisper_model()
        second = video._get_whisper_model()
        assert fake_whisper.loaded == ["base"]
        assert first is second
        assert fake_whisper.model is first


class TestComputeVideoQuality:
    """Tests de _compute_video_quality."""

    def test_minimal_quality(self) -> None:
        assert _compute_video_quality({}) == pytest.approx(0.4)

    def test_degraded_quality(self) -> None:
        assert _compute_video_quality({"_degraded_ffprobe": True}) == pytest.approx(0.3)
        assert _compute_video_quality({"video_duration_sec": "10", "_degraded_ffprobe": True}) == pytest.approx(0.45)

    def test_partial_quality_without_width(self) -> None:
        metadata: dict[str, Any] = {
            "video_duration_sec": "10",
            "video_video_codec": "h264",
            "video_width": 0,
            "video_fps": "30/1",
            "thumbnails": ["t.jpg"],
            "transcription_performed": True,
            "transcript": "abc",
        }
        assert _compute_video_quality(metadata) == pytest.approx(1.0)

    def test_transcription_without_text(self) -> None:
        metadata: dict[str, Any] = {
            "video_duration_sec": "10",
            "video_video_codec": "h264",
            "video_width": 1920,
            "video_fps": "30/1",
            "transcription_performed": True,
        }
        assert _compute_video_quality(metadata) == pytest.approx(0.9)

    def test_full_quality_capped_at_one(self) -> None:
        metadata: dict[str, Any] = {
            "video_duration_sec": "10",
            "video_video_codec": "h264",
            "video_width": 1920,
            "video_fps": "30/1",
            "thumbnails": ["t.jpg"],
            "transcription_performed": True,
            "transcript": "abc",
        }
        assert _compute_video_quality(metadata) == 1.0


class TestModuleRegistration:
    """Tests del registro del extractor en el registry (import del módulo)."""

    def test_video_extractor_registered(self) -> None:
        registered = get_registry().get("video")
        assert registered is not None
        assert registered.id == "video"
        assert registered.version == "1.0.0"
        assert registered.supported_mime_types == video._VIDEO_MIMES
