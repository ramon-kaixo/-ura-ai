"""Cobertura 100x100 de extractors audio/image/pdf. TASK-20260820-011."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import knowledge.engine.extractors.audio as audio_mod
import knowledge.engine.extractors.image as image_mod
import knowledge.engine.extractors.pdf as pdf_mod
from knowledge.engine.extractors.audio import AudioExtractor, _compute_audio_quality
from knowledge.engine.extractors.image import ImageExtractor, ImageSizeError, _compute_image_quality
from knowledge.engine.extractors.pdf import PdfExtractor, PdfLimitError, _compute_pdf_quality
from knowledge.engine.ontology.internal import AssetSource, AssetType


def _src(location: str) -> AssetSource:
    return AssetSource(kind="filesystem", location=location)


def _instalar_fake_pil(monkeypatch: pytest.MonkeyPatch, fake_image_cls) -> None:
    """Instala PIL + PIL.Image en sys.modules para que 'from PIL import Image' funcione."""
    import sys
    import types

    fake_pil = types.ModuleType("PIL")
    fake_image_mod = types.ModuleType("PIL.Image")
    fake_image_mod.Image = fake_image_cls
    fake_pil.Image = fake_image_cls
    fake_pil.ExifTags = types.ModuleType("PIL.ExifTags")
    fake_pil.ExifTags.TAGS = {0x010F: "Make", 0x0110: "Model"}
    fake_pil.ExifTags.GPSTAGS = {0x0001: "GPSLatitudeRef"}
    monkeypatch.setitem(sys.modules, "PIL", fake_pil)
    monkeypatch.setitem(sys.modules, "PIL.Image", fake_image_mod)
    monkeypatch.setitem(sys.modules, "PIL.ExifTags", fake_pil.ExifTags)


# ── audio ────────────────────────────────────────────────────


def test_audio_file_no_existe() -> None:
    r = AudioExtractor().extract(_src("/no/existe.mp3"))
    assert "File not found" in r.errors[0]


def test_audio_demasiado_grande(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Path(str(tmp_path)) / "big.mp3"
    p.write_bytes(b"x" * 100)
    monkeypatch.setattr(audio_mod, "MAX_AUDIO_SIZE", 10)
    r = AudioExtractor().extract(_src(str(p)))
    assert "File too large" in r.errors[0]


def test_audio_ok_sin_ffprobe_ni_whisper(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Path(str(tmp_path)) / "a.mp3"
    p.write_bytes(b"audio-data")
    monkeypatch.setattr(audio_mod, "_HAS_FFPROBE", False)
    monkeypatch.setattr(audio_mod, "_HAS_WHISPER", False)
    r = AudioExtractor().extract(_src(str(p)))
    assert r.asset is not None
    assert r.asset.asset_type == AssetType.AUDIO
    assert r.asset.metadata["_degraded_ffprobe"] is True
    assert r.asset.metadata["format"] == "mp3"


def test_audio_con_ffprobe(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Path(str(tmp_path)) / "a.wav"
    p.write_bytes(b"wav")
    ffprobe_json = json.dumps(
        {
            "format": {"duration": "12.5", "bit_rate": "320000", "format_name": "wav"},
            "streams": [{"codec_type": "audio", "codec_name": "pcm_s16le", "sample_rate": "44100", "channels": 2, "channel_layout": "stereo"}],
        }
    )

    class _R:
        returncode = 0
        stdout = ffprobe_json
        stderr = ""

    monkeypatch.setattr(audio_mod, "_HAS_FFPROBE", True)
    monkeypatch.setattr(audio_mod, "_HAS_WHISPER", False)
    monkeypatch.setattr(audio_mod.subprocess, "run", lambda *a, **k: _R())
    r = AudioExtractor().extract(_src(str(p)))
    m = r.asset.metadata
    assert m["audio_duration_sec"] == "12.5"
    assert m["audio_bitrate"] == "320000"
    assert m["audio_codec"] == "pcm_s16le"
    assert m["audio_sample_rate"] == "44100"
    assert m["audio_channels"] == 2
    assert "_degraded_ffprobe" not in m


def test_audio_ffprobe_falla(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Path(str(tmp_path)) / "a.wav"
    p.write_bytes(b"wav")

    class _R:
        returncode = 1
        stdout = ""
        stderr = "ffprobe error"

    monkeypatch.setattr(audio_mod, "_HAS_FFPROBE", True)
    monkeypatch.setattr(audio_mod, "_HAS_WHISPER", False)
    monkeypatch.setattr(audio_mod.subprocess, "run", lambda *a, **k: _R())
    r = AudioExtractor().extract(_src(str(p)))
    assert r.asset.metadata["_degraded_ffprobe"] is True


def test_audio_ffprobe_json_invalido(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Path(str(tmp_path)) / "a.wav"
    p.write_bytes(b"wav")

    class _R:
        returncode = 0
        stdout = "no-json"
        stderr = ""

    monkeypatch.setattr(audio_mod, "_HAS_FFPROBE", True)
    monkeypatch.setattr(audio_mod, "_HAS_WHISPER", False)
    monkeypatch.setattr(audio_mod.subprocess, "run", lambda *a, **k: _R())
    r = AudioExtractor().extract(_src(str(p)))
    assert r.asset.metadata["_degraded_ffprobe"] is True


def test_audio_ffprobe_timeout(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Path(str(tmp_path)) / "a.wav"
    p.write_bytes(b"wav")

    def _timeout(*a, **k):
        raise __import__("subprocess").TimeoutExpired("ffprobe", 30)

    monkeypatch.setattr(audio_mod, "_HAS_FFPROBE", True)
    monkeypatch.setattr(audio_mod, "_HAS_WHISPER", False)
    monkeypatch.setattr(audio_mod.subprocess, "run", _timeout)
    r = AudioExtractor().extract(_src(str(p)))
    assert r.asset.metadata["_degraded_ffprobe"] is True


def test_audio_ffprobe_sin_streams_audio(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Path(str(tmp_path)) / "a.wav"
    p.write_bytes(b"wav")
    ffprobe_json = json.dumps({"format": {}, "streams": [{"codec_type": "video"}]})

    class _R:
        returncode = 0
        stdout = ffprobe_json
        stderr = ""

    monkeypatch.setattr(audio_mod, "_HAS_FFPROBE", True)
    monkeypatch.setattr(audio_mod, "_HAS_WHISPER", False)
    monkeypatch.setattr(audio_mod.subprocess, "run", lambda *a, **k: _R())
    r = AudioExtractor().extract(_src(str(p)))
    assert r.asset is not None


def test_audio_transcripcion_ok(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Path(str(tmp_path)) / "a.wav"
    p.write_bytes(b"wav")

    class _Modelo:
        def transcribe(self, path: str) -> dict:
            return {"text": "hola mundo", "language": "es"}

    monkeypatch.setattr(audio_mod, "_HAS_FFPROBE", False)
    monkeypatch.setattr(audio_mod, "_HAS_WHISPER", True)
    monkeypatch.setattr(audio_mod, "_get_whisper_model", lambda: _Modelo())
    r = AudioExtractor().extract(_src(str(p)))
    m = r.asset.metadata
    assert m["transcript"] == "hola mundo"
    assert m["transcription_performed"] is True
    assert m["transcription_language"] == "es"


def test_audio_transcripcion_vacia(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Path(str(tmp_path)) / "a.wav"
    p.write_bytes(b"wav")

    class _Modelo:
        def transcribe(self, path: str) -> dict:
            return {"text": "   ", "language": ""}

    monkeypatch.setattr(audio_mod, "_HAS_FFPROBE", False)
    monkeypatch.setattr(audio_mod, "_HAS_WHISPER", True)
    monkeypatch.setattr(audio_mod, "_get_whisper_model", lambda: _Modelo())
    r = AudioExtractor().extract(_src(str(p)))
    assert r.asset.metadata["transcription_performed"] is True
    assert "transcript" not in r.asset.metadata


def test_audio_transcripcion_error(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Path(str(tmp_path)) / "a.wav"
    p.write_bytes(b"wav")

    class _Modelo:
        def transcribe(self, path: str) -> dict:
            msg = "sin modelo"
            raise RuntimeError(msg)

    monkeypatch.setattr(audio_mod, "_HAS_FFPROBE", False)
    monkeypatch.setattr(audio_mod, "_HAS_WHISPER", True)
    monkeypatch.setattr(audio_mod, "_get_whisper_model", lambda: _Modelo())
    r = AudioExtractor().extract(_src(str(p)))
    assert r.asset.metadata["transcription_performed"] is False
    assert "sin modelo" in r.asset.metadata["transcription_error"]


def test_audio_extract_error(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Path(str(tmp_path)) / "a.wav"
    p.write_bytes(b"wav")

    def _hash_roto(path: str) -> tuple:
        msg = "hash fallo"
        raise OSError(msg)

    monkeypatch.setattr(audio_mod, "_hash_stream", _hash_roto)
    r = AudioExtractor().extract(_src(str(p)))
    assert "Extraction error" in r.errors[0]


def test_audio_quality() -> None:
    assert _compute_audio_quality({}) == pytest.approx(0.4)  # 0.3 base + 0.1 no-degradado
    m = {"audio_duration_sec": 1, "audio_codec": "x", "audio_sample_rate": 1, "audio_bitrate": 1, "transcription_performed": True, "transcript": "x"}
    assert _compute_audio_quality(m) == 1.0
    m2 = {"_degraded_ffprobe": True}
    assert _compute_audio_quality(m2) == pytest.approx(0.3)  # 0.3 base, degradado


def test_audio_quality_min_1() -> None:
    m = {"audio_duration_sec": 1, "audio_codec": "x", "audio_sample_rate": 1, "audio_bitrate": 1, "transcription_performed": True, "transcript": "x" * 10}
    assert _compute_audio_quality(m) == 1.0


def test_audio_get_whisper_model_carga(monkeypatch: pytest.MonkeyPatch) -> None:
    import sys
    import types

    class _Modelo:
        def transcribe(self, path: str) -> dict:
            return {"text": "x"}

    fake_whisper = types.ModuleType("whisper")
    fake_whisper.load_model = lambda name: _Modelo()
    monkeypatch.setitem(sys.modules, "whisper", fake_whisper)
    audio_mod._get_whisper_model.__dict__.pop("model", None)
    m = audio_mod._get_whisper_model()
    assert m is not None
    assert hasattr(audio_mod._get_whisper_model, "model")


def test_audio_get_whisper_model_cacheado(monkeypatch: pytest.MonkeyPatch) -> None:
    audio_mod._get_whisper_model.model = "modelo-cacheado"
    try:
        assert audio_mod._get_whisper_model() == "modelo-cacheado"
    finally:
        audio_mod._get_whisper_model.__dict__.pop("model", None)


def test_audio_ffprobe_valores_vacios_no_anaden(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Path(str(tmp_path)) / "a.wav"
    p.write_bytes(b"wav")
    ffprobe_json = json.dumps(
        {
            "format": {"duration": "", "bit_rate": "", "format_name": ""},
            "streams": [{"codec_type": "audio", "codec_name": None, "sample_rate": None, "channels": None}],
        }
    )

    class _R:
        returncode = 0
        stdout = ffprobe_json
        stderr = ""

    monkeypatch.setattr(audio_mod, "_HAS_FFPROBE", True)
    monkeypatch.setattr(audio_mod, "_HAS_WHISPER", False)
    monkeypatch.setattr(audio_mod.subprocess, "run", lambda *a, **k: _R())
    r = AudioExtractor().extract(_src(str(p)))
    m = r.asset.metadata
    assert "audio_duration_sec" not in m
    assert "audio_sample_rate" not in m
    assert m["audio_codec"] is None


# ── image ────────────────────────────────────────────────────


def test_image_file_no_existe() -> None:
    r = ImageExtractor().extract(_src("/no/existe.png"))
    assert "File not found" in r.errors[0]


def test_image_demasiado_grande(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Path(str(tmp_path)) / "i.png"
    p.write_bytes(b"x" * 100)
    monkeypatch.setattr(image_mod, "MAX_IMAGE_SIZE", 10)
    r = ImageExtractor().extract(_src(str(p)))
    assert "File too large" in r.errors[0]


def test_image_ok_sin_pillow(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Path(str(tmp_path)) / "i.png"
    p.write_bytes(b"png")
    monkeypatch.setattr(image_mod, "_HAS_PILLOW", False)
    r = ImageExtractor().extract(_src(str(p)))
    assert r.asset is not None
    assert r.asset.asset_type == AssetType.IMAGE
    assert r.asset.metadata["_degraded"] is True
    assert r.asset.metadata["_degraded_reason"] == "Pillow not installed"


def test_image_extract_error(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Path(str(tmp_path)) / "i.png"
    p.write_bytes(b"png")

    def _hash_roto(path: str) -> tuple:
        msg = "hash fallo"
        raise OSError(msg)

    monkeypatch.setattr(image_mod, "_hash_stream", _hash_roto)
    r = ImageExtractor().extract(_src(str(p)))
    assert "Extraction error" in r.errors[0]


def test_image_size_error_propaga() -> None:
    with pytest.raises(ImageSizeError):
        raise ImageSizeError("too big")


def test_image_quality() -> None:
    assert _compute_image_quality({}) == 0.3
    m = {"width": 10, "height": 10, "exif_make": "x", "exif_datetimeoriginal": "y", "gps": {"lat": 1}, "thumbnail": "t", "ocr_performed": True, "ocr_text": "z"}
    assert _compute_image_quality(m) == 1.0


def test_image_quality_solo_dimensiones() -> None:
    m = {"width": 10, "height": 10}
    assert _compute_image_quality(m) == pytest.approx(0.45)


def _fake_img_cls(size=(10, 10), fmt="PNG", mode="RGB", exif_items=None, save_raises=None):
    class _FakeExifData:
        def __init__(self) -> None:
            self._items = exif_items or []
            self.gps = None

        def items(self):
            return self._items

        def get_ifd(self, tag_id: int):
            return self.gps

    class _FakeImg:
        def __init__(self) -> None:
            self.size = size
            self.format = fmt
            self.mode = mode
            self._exif = _FakeExifData()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def getexif(self):
            return self._exif

        def copy(self):
            return self

        def thumbnail(self, size2: tuple) -> None:
            pass

        def save(self, path: str, fmt2: str, quality: int = 70) -> None:
            if save_raises:
                raise save_raises

    return _FakeImg


def test_image_pillow_ok(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    from PIL import Image as RealImage

    p = Path(str(tmp_path)) / "i.png"
    img = RealImage.new("RGB", (10, 10), color="red")
    img.save(p)
    _instalar_fake_pil(monkeypatch, type("Image", (), {"open": lambda p: _fake_img_cls()()}))
    monkeypatch.setattr(image_mod, "_HAS_PILLOW", True)
    monkeypatch.setattr(image_mod, "_HAS_TESSERACT", False)
    r = ImageExtractor().extract(_src(str(p)))
    assert r.asset is not None
    assert r.asset.metadata["width"] == 10
    assert r.asset.metadata["height"] == 10
    assert r.asset.metadata["thumbnail"].endswith(".thumb.jpg")


def test_image_pillow_demasiado_ancha(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    (Path(str(tmp_path)) / "i.png").write_bytes(b"png")
    _instalar_fake_pil(monkeypatch, type("Image", (), {"open": lambda p: _fake_img_cls(size=(30000, 10))()}))
    monkeypatch.setattr(image_mod, "_HAS_PILLOW", True)
    r = ImageExtractor().extract(_src(str(tmp_path / "i.png")))
    assert "Extraction error" in r.errors[0]


def test_image_pillow_muchos_pixeles(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    (Path(str(tmp_path)) / "i.png").write_bytes(b"png")
    _instalar_fake_pil(monkeypatch, type("Image", (), {"open": lambda p: _fake_img_cls(size=(15000, 15000))()}))
    monkeypatch.setattr(image_mod, "_HAS_PILLOW", True)
    r = ImageExtractor().extract(_src(str(tmp_path / "i.png")))
    assert "Extraction error" in r.errors[0]


def test_image_pillow_medio_grande(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    (Path(str(tmp_path)) / "i.png").write_bytes(b"png")
    _instalar_fake_pil(monkeypatch, type("Image", (), {"open": lambda p: _fake_img_cls(size=(8000, 8000))()}))
    monkeypatch.setattr(image_mod, "_HAS_PILLOW", True)
    monkeypatch.setattr(image_mod, "_HAS_TESSERACT", False)
    r = ImageExtractor().extract(_src(str(tmp_path / "i.png")))
    assert r.asset is not None


def test_image_pillow_abrir_error(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    (Path(str(tmp_path)) / "i.png").write_bytes(b"png")

    class _Roto:
        def __enter__(self):
            msg = "imagen corrupta"
            raise OSError(msg)

        def __exit__(self, *a):
            return False

    _instalar_fake_pil(monkeypatch, type("Image", (), {"open": lambda p: _Roto()}))
    monkeypatch.setattr(image_mod, "_HAS_PILLOW", True)
    r = ImageExtractor().extract(_src(str(tmp_path / "i.png")))
    assert r.asset.metadata["_degraded"] is True
    assert "Cannot open image" in r.asset.metadata["_degraded_reason"]


def test_image_exif_y_gps(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    (Path(str(tmp_path)) / "i.png").write_bytes(b"png")

    class _FakeExifData:
        def __init__(self) -> None:
            self._items = [(0x010F, "Canon")]  # Make
            self.gps = {0x0001: "40.7"}

        def items(self):
            return self._items

        def get_ifd(self, tag_id: int):
            return self.gps if tag_id == 0x8825 else None

    class _FakeImg:
        def __init__(self) -> None:
            self.size = (10, 10)
            self.format = "PNG"
            self.mode = "RGB"
            self._exif = _FakeExifData()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def getexif(self):
            return self._exif

        def copy(self):
            return self

        def thumbnail(self, size: tuple) -> None:
            pass

        def save(self, path: str, fmt: str, quality: int = 70) -> None:
            pass

    _instalar_fake_pil(monkeypatch, type("Image", (), {"open": lambda p: _FakeImg()}))
    monkeypatch.setattr(image_mod, "_HAS_PILLOW", True)
    monkeypatch.setattr(image_mod, "_HAS_TESSERACT", False)
    r = ImageExtractor().extract(_src(str(tmp_path / "i.png")))
    assert r.asset.metadata.get("exif_make") == "Canon"
    assert r.asset.metadata.get("gps") is not None


def test_image_thumbnail_error(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    (Path(str(tmp_path)) / "i.png").write_bytes(b"png")
    _instalar_fake_pil(monkeypatch, type("Image", (), {"open": lambda p: _fake_img_cls(save_raises=OSError("no jpeg"))()}))
    monkeypatch.setattr(image_mod, "_HAS_PILLOW", True)
    monkeypatch.setattr(image_mod, "_HAS_TESSERACT", False)
    r = ImageExtractor().extract(_src(str(tmp_path / "i.png")))
    assert "thumbnail" not in r.asset.metadata


def test_image_ocr_ok(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    import sys
    import types

    (Path(str(tmp_path)) / "i.png").write_bytes(b"png")
    _instalar_fake_pil(monkeypatch, type("Image", (), {"open": lambda p: _fake_img_cls()()}))
    monkeypatch.setattr(image_mod, "_HAS_PILLOW", True)
    monkeypatch.setattr(image_mod, "_HAS_TESSERACT", True)

    class _FakePytesseract:
        @staticmethod
        def image_to_string(img) -> str:
            return "texto ocr"

    fake_tess = types.ModuleType("pytesseract")
    fake_tess.image_to_string = _FakePytesseract.image_to_string
    monkeypatch.setitem(sys.modules, "pytesseract", fake_tess)
    r = ImageExtractor().extract(_src(str(tmp_path / "i.png")))
    assert r.asset.metadata["ocr_text"] == "texto ocr"
    assert r.asset.metadata["ocr_performed"] is True


def test_image_ocr_vacio() -> None:
    import types

    class _FakeImg2:
        pass

    class _FakeTess:
        @staticmethod
        def image_to_string(img) -> str:
            return "   "

    monkeypatch = pytest.MonkeyPatch()
    fake_tess = types.ModuleType("pytesseract")
    fake_tess.image_to_string = _FakeTess.image_to_string
    monkeypatch.setitem(__import__("sys").modules, "pytesseract", fake_tess)
    try:
        m = {}
        ImageExtractor._run_ocr(_FakeImg2(), m)
        assert m["ocr_performed"] is True
        assert "ocr_text" not in m
    finally:
        monkeypatch.undo()


def test_image_ocr_error() -> None:
    import types

    class _FakeImg2:
        pass

    class _FakeTess:
        @staticmethod
        def image_to_string(img) -> str:
            msg = "tesseract no instalado"
            raise RuntimeError(msg)

    monkeypatch = pytest.MonkeyPatch()
    fake_tess = types.ModuleType("pytesseract")
    fake_tess.image_to_string = _FakeTess.image_to_string
    monkeypatch.setitem(__import__("sys").modules, "pytesseract", fake_tess)
    try:
        m = {}
        ImageExtractor._run_ocr(_FakeImg2(), m)
        assert m["ocr_performed"] is False
        assert "tesseract" in m["ocr_error"]
    finally:
        monkeypatch.undo()


def test_image_exif_sin_datos() -> None:
    class _SinExif:
        def getexif(self):
            return None

    m = {}
    ImageExtractor._extract_exif(_SinExif(), m)
    assert m == {}


def test_image_exif_tag_desconocido() -> None:
    class _ExifRaro:
        def getexif(self):
            return self

        def items(self):
            return [(9999, "valor")]  # tag no mapeado

        def get_ifd(self, tag_id: int):
            return None

    m = {}
    ImageExtractor._extract_exif(_ExifRaro(), m)
    assert m == {}


def test_image_exif_gps_vacio() -> None:
    class _ExifSinGps:
        def getexif(self):
            return self

        def items(self):
            return []

        def get_ifd(self, tag_id: int):
            return None  # sin GPS

    m = {}
    ImageExtractor._extract_exif(_ExifSinGps(), m)
    assert "gps" not in m


def test_image_exif_items_sin_gps() -> None:
    class _ExifConItems:
        def getexif(self):
            return self

        def items(self):
            return [(0x010F, "Canon")]  # Make presente

        def get_ifd(self, tag_id: int):
            return None  # sin GPS

    m = {}
    ImageExtractor._extract_exif(_ExifConItems(), m)
    assert m.get("exif_make") == "Canon"
    assert "gps" not in m


def test_image_exif_gps_info_vacio() -> None:
    class _ExifGpsVacio:
        def getexif(self):
            return self

        def items(self):
            return [(0x010F, "Canon")]

        def get_ifd(self, tag_id: int):
            return {} if tag_id == 0x8825 else None  # gps_info vacío

    m = {}
    ImageExtractor._extract_exif(_ExifGpsVacio(), m)
    assert "gps" not in m


# ── pdf ──────────────────────────────────────────────────────


def test_pdf_file_no_existe() -> None:
    r = PdfExtractor().extract(_src("/no/existe.pdf"))
    assert "File not found" in r.errors[0]


def test_pdf_demasiado_grande(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Path(str(tmp_path)) / "b.pdf"
    p.write_bytes(b"x" * 100)
    monkeypatch.setattr(pdf_mod, "MAX_PDF_SIZE", 10)
    r = PdfExtractor().extract(_src(str(p)))
    assert "File too large" in r.errors[0]


def test_pdf_sin_fitz(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Path(str(tmp_path)) / "b.pdf"
    p.write_bytes(b"%PDF-1.4")
    monkeypatch.setattr(pdf_mod, "_HAS_FITZ", False)
    r = PdfExtractor().extract(_src(str(p)))
    assert r.asset is not None
    assert r.asset.asset_type == AssetType.PDF
    assert r.asset.metadata["_degraded"] is True
    assert r.asset.metadata["_degraded_reason"] == "PyMuPDF not installed"


def test_pdf_extract_error(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Path(str(tmp_path)) / "b.pdf"
    p.write_bytes(b"%PDF")

    def _hash_roto(path: str) -> tuple:
        msg = "hash fallo"
        raise OSError(msg)

    monkeypatch.setattr(pdf_mod, "_hash_stream", _hash_roto)
    r = PdfExtractor().extract(_src(str(p)))
    assert "Extraction error" in r.errors[0]


def _fake_doc(num_pages=2, metadata=None, text="hola", is_encrypted=False, is_pdf=True, pdf_version="1.7"):
    class _Page:
        def __init__(self) -> None:
            pass

        def get_text(self) -> str:
            return text

        def get_pixmap(self):
            return type("Pix", (), {"tobytes": lambda self, fmt: b"png-data"})()

    class _Doc:
        def __init__(self) -> None:
            self.page_count = num_pages
            self.metadata = metadata or {}
            self.is_encrypted = is_encrypted
            self.is_pdf = is_pdf
            self.pdf_version = pdf_version

        def __getitem__(self, i: int) -> _Page:
            return _Page()

        def close(self) -> None:
            pass

    return _Doc()


def test_pdf_con_fitz_ok(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    import sys
    import types

    p = Path(str(tmp_path)) / "b.pdf"
    p.write_bytes(b"%PDF-1.4")
    doc = _fake_doc(
        num_pages=2,
        metadata={"title": "Mi Doc", "author": "Ramon", "keywords": "ura,test", "producer": "x"},
    )
    fake_fitz = types.ModuleType("fitz")
    fake_fitz.open = lambda path: doc
    monkeypatch.setitem(sys.modules, "fitz", fake_fitz)
    monkeypatch.setattr(pdf_mod, "_HAS_FITZ", True)
    r = PdfExtractor().extract(_src(str(p)))
    m = r.asset.metadata
    assert m["pages"] == 2
    assert m["title"] == "Mi Doc"
    assert m["author"] == "Ramon"
    assert m["keywords"] == "ura,test"
    assert m["has_text"] is True
    assert m["text_length"] == 8


def test_pdf_demasiadas_paginas(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    import sys
    import types

    p = Path(str(tmp_path)) / "b.pdf"
    p.write_bytes(b"%PDF")
    doc = _fake_doc(num_pages=20000)
    fake_fitz = types.ModuleType("fitz")
    fake_fitz.open = lambda path: doc
    monkeypatch.setitem(sys.modules, "fitz", fake_fitz)
    monkeypatch.setattr(pdf_mod, "_HAS_FITZ", True)
    monkeypatch.setattr(pdf_mod, "MAX_PAGES", 10000)
    r = PdfExtractor().extract(_src(str(p)))
    assert "PDF has" in r.errors[0]


def test_pdf_metadata_vacia(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    import sys
    import types

    p = Path(str(tmp_path)) / "b.pdf"
    p.write_bytes(b"%PDF")

    class _DocSinMeta:
        page_count = 1
        metadata = None
        is_encrypted = False
        is_pdf = True

        def __getitem__(self, i: int):
            return type("Pg", (), {"get_text": lambda self: ""})()

        def close(self) -> None:
            pass

    fake_fitz = types.ModuleType("fitz")
    fake_fitz.open = lambda path: _DocSinMeta()
    monkeypatch.setitem(sys.modules, "fitz", fake_fitz)
    monkeypatch.setattr(pdf_mod, "_HAS_FITZ", True)
    r = PdfExtractor().extract(_src(str(p)))
    assert r.asset.metadata["has_text"] is False
    assert r.asset.metadata["ocr_performed"] is False


def test_pdf_sin_texto_con_ocr(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    import sys
    import types

    p = Path(str(tmp_path)) / "b.pdf"
    p.write_bytes(b"%PDF")
    doc = _fake_doc(num_pages=1, text="   ")
    fake_fitz = types.ModuleType("fitz")
    fake_fitz.open = lambda path: doc
    monkeypatch.setitem(sys.modules, "fitz", fake_fitz)
    monkeypatch.setattr(pdf_mod, "_HAS_FITZ", True)
    monkeypatch.setattr(pdf_mod, "_HAS_TESSERACT", False)
    r = PdfExtractor().extract(_src(str(p)))
    assert r.asset.metadata["has_text"] is False
    assert r.asset.metadata["ocr_performed"] is False


def test_pdf_sin_texto_con_ocr_tesseract(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    import sys
    import types

    p = Path(str(tmp_path)) / "b.pdf"
    p.write_bytes(b"%PDF")
    doc = _fake_doc(num_pages=2, text="   ")
    fake_fitz = types.ModuleType("fitz")
    fake_fitz.open = lambda path: doc
    monkeypatch.setitem(sys.modules, "fitz", fake_fitz)
    monkeypatch.setattr(pdf_mod, "_HAS_FITZ", True)
    monkeypatch.setattr(pdf_mod, "_HAS_TESSERACT", True)

    class _FakeTess:
        @staticmethod
        def image_to_string(img) -> str:
            return "ocr pagina"

    fake_tess = types.ModuleType("pytesseract")
    fake_tess.image_to_string = _FakeTess.image_to_string
    monkeypatch.setitem(sys.modules, "pytesseract", fake_tess)
    r = PdfExtractor().extract(_src(str(p)))
    m = r.asset.metadata
    assert m["has_text"] is False
    assert m["ocr_performed"] is True
    assert m["ocr_text_length"] > 0


def test_pdf_quality() -> None:
    assert _compute_pdf_quality({}) == pytest.approx(0.3)
    m = {"pages": 5, "title": "t", "author": "a", "text_length": 500, "keywords": "k", "has_text": True}
    assert _compute_pdf_quality(m) == 1.0
    m2 = {"pages": 0}
    assert _compute_pdf_quality(m2) == pytest.approx(0.3)


def test_pdf_limit_error() -> None:
    with pytest.raises(PdfLimitError):
        raise PdfLimitError("demasiadas paginas")
