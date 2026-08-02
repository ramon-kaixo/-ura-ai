"""Tests para core/memoria/extractores/imagen_extractor.py.

Pillow no esta instalado en el entorno: se inyectan fakes de PIL/Image y
PIL/ExifTags en sys.modules antes de importar el modulo (mismo patron que
blake3 en test_memoria_bridge_vigilante).
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest


class FakeImage:
    open = mock.Mock(return_value=None)

    def __init__(self, fmt="JPEG", width=100, height=50, mode="RGB", exif=None):
        self.format = fmt
        self.width = width
        self.height = height
        self.mode = mode
        self._exif_data = exif
        self.converted = None
        self.resized = None

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def _getexif(self):
        return self._exif_data

    def convert(self, *a, **k):
        self.converted = self
        return self

    def resize(self, *a, **k):
        self.resized = self
        return self


def _install_pil_fakes(monkeypatch):
    fake_exiftags = SimpleNamespace(TAGS={0x9003: "DateTimeOriginal", 0x010F: "Make", 0x0110: "Model", 0x8825: "GPSInfo"}, GPSTAGS={1: "GPSLatitude", 2: "GPSLongitude"})
    pil_module = SimpleNamespace(Image=FakeImage, ExifTags=fake_exiftags)
    monkeypatch.setitem(sys.modules, "PIL", pil_module)
    monkeypatch.setitem(sys.modules, "PIL.ExifTags", fake_exiftags)
    return fake_exiftags


def _import_module(monkeypatch):
    _install_pil_fakes(monkeypatch)
    import core.memoria.extractores.imagen_extractor as ie

    return ie


@pytest.fixture
def ie(monkeypatch):
    return _import_module(monkeypatch)


class TestExifPillow:
    def test_sin_exif(self, ie, monkeypatch, tmp_path) -> None:
        ruta = tmp_path / "a.jpg"
        ruta.write_bytes(b"x")
        with mock.patch.object(ie.Image, "open", return_value=FakeImage(exif=None)):
            out = ie._exif_pillow(ruta)
        assert out == {"fecha": "", "camara": "", "gps": None, "exif_raw": {}}

    def test_exif_completo_gps(self, ie, monkeypatch, tmp_path) -> None:
        """Documenta bug real: GPSInfo dict se convierte a str por el else
        antes de iterar -> el branch GPSInfo (linea 46) es inalcanzable."""
        ruta = tmp_path / "a.jpg"
        ruta.write_bytes(b"x")
        exif = {
            0x9003: b"2026:01:02 10:00:00",
            0x010F: "Nikon",
            0x0110: "D850",
            0x8825: {1: "40, 0, 0", 2: "-3, 0, 0"},
        }
        with mock.patch.object(ie.Image, "open", return_value=FakeImage(exif=exif)):
            out = ie._exif_pillow(ruta)
        assert out["fecha"] == "2026:01:02 10:00:00"
        assert out["camara"] == "Nikon D850"
        # GPS se pierde: el dict cae en str(valor)[:200]
        assert out["gps"] is None
        assert "GPSInfo" in out["exif_raw"]

    def test_exif_bytes_y_otros(self, ie, tmp_path) -> None:
        ruta = tmp_path / "a.jpg"
        ruta.write_bytes(b"x")
        exif = {0x0100: bytes([1, 2, 3]), 0x0102: 100, 0x0103: (1, 2)}
        with mock.patch.object(ie.Image, "open", return_value=FakeImage(exif=exif)):
            out = ie._exif_pillow(ruta)
        assert out["exif_raw"]

    def test_error_lectura(self, ie, tmp_path) -> None:
        ruta = tmp_path / "a.jpg"
        with mock.patch.object(ie.Image, "open", side_effect=OSError("corrupto")):
            out = ie._exif_pillow(ruta)
        assert out["fecha"] == ""


class TestExifExiftool:
    def test_ok(self, ie, monkeypatch) -> None:
        import json

        json_dumps = json.dumps([{"SourceFile": "x", "DateTimeOriginal": "2026:01:01", "Make": "Canon", "Model": "EOS", "GPSLatitude": "40", "GPSLongitude": "-3", "ImageWidth": 100}])
        with mock.patch.object(ie.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout=json_dumps)):
            out = ie._exif_exiftool(Path("/tmp/x.jpg"))
        assert out["fecha"] == "2026:01:01"
        assert out["camara"] == "Canon EOS"
        assert out["gps"] == "40, -3"
        assert "SourceFile" not in out["exif_raw"]

    def test_returncode_error(self, ie) -> None:
        with mock.patch.object(ie.subprocess, "run", return_value=SimpleNamespace(returncode=1, stdout="")):
            out = ie._exif_exiftool(Path("/tmp/x.jpg"))
        assert out == {"fecha": "", "camara": "", "gps": None, "exif_raw": {}}

    def test_solo_latitud(self, ie) -> None:
        import json

        datos = json.dumps([{"GPSLatitude": "40"}])
        with mock.patch.object(ie.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout=datos)):
            out = ie._exif_exiftool(Path("/tmp/x.jpg"))
        assert out["gps"] == "40"

    def test_excepcion(self, ie) -> None:
        with mock.patch.object(ie.subprocess, "run", side_effect=OSError("no exiftool")):
            out = ie._exif_exiftool(Path("/tmp/x.jpg"))
        assert out["gps"] is None


class TestPaletaColores:
    def test_ok(self, ie, monkeypatch) -> None:
        import numpy as np

        arr = np.zeros((3, 3, 3), dtype=np.uint8)
        img = FakeImage()
        monkeypatch.setitem(sys.modules, "numpy", SimpleNamespace(array=lambda *a, **k: arr))
        with mock.patch.object(ie.Image, "open", return_value=img):
            out = ie._paleta_colores(Path("/tmp/x.jpg"), k=2)
        assert len(out) == 1  # todos los pixeles iguales -> 1 color
        assert out[0] == "#000000"

    def test_error(self, ie) -> None:
        with mock.patch.object(ie.Image, "open", side_effect=OSError("no")):
            assert ie._paleta_colores(Path("/tmp/x.jpg")) == []


class TestDescribirImagen:
    def test_ok(self, ie, monkeypatch, tmp_path) -> None:
        ruta = tmp_path / "a.jpg"
        ruta.write_bytes(b"img")
        resp = SimpleNamespace(is_error=False, json=lambda: {"message": {"content": "una foto"}})
        with mock.patch.object(ie.httpx, "post", return_value=resp):
            out = ie._describir_imagen(ruta)
        assert out["descripcion"] == "una foto"
        assert out["modelo"] == "llama3.2-vision:11b"

    def test_error_http(self, ie, tmp_path) -> None:
        ruta = tmp_path / "a.jpg"
        ruta.write_bytes(b"x")
        resp = SimpleNamespace(is_error=True, status_code=500)
        with mock.patch.object(ie.httpx, "post", return_value=resp):
            out = ie._describir_imagen(ruta)
        assert out["error"] == "Ollama 500"

    def test_excepcion(self, ie, tmp_path) -> None:
        ruta = tmp_path / "a.jpg"
        ruta.write_bytes(b"x")
        with mock.patch.object(ie.httpx, "post", side_effect=OSError("net")):
            out = ie._describir_imagen(ruta)
        assert "error" in out


class TestExtraerIptc:
    def test_ok(self, ie) -> None:
        data = {5: b"titulo", 120: b"desc", 80: b"autor", 25: [b"k1", b"k2"], 90: b"ciudad", 101: b"pais", 116: b"(c)"}
        info = SimpleNamespace(_data=data)
        with mock.patch.dict(sys.modules, {"iptcinfo3": SimpleNamespace(IPTCInfo=lambda *a: info)}):
            out = ie._extraer_iptc(Path("/tmp/x.jpg"))
        assert out["titulo"] == "titulo"
        assert out["keywords"] == ["k1", "k2"]
        assert out["ciudad"] == "ciudad"

    def test_error(self, ie) -> None:
        with mock.patch.dict(sys.modules, {"iptcinfo3": SimpleNamespace(IPTCInfo=lambda *a: (_ for _ in ()).throw(OSError("no")))}):
            out = ie._extraer_iptc(Path("/tmp/x.jpg"))
        assert out == {}


class TestExtraerImagen:
    def test_extraer_imagen_completo(self, ie, monkeypatch, tmp_path) -> None:
        ruta = tmp_path / "a.jpg"
        ruta.write_bytes(b"img")
        with mock.patch.object(ie.Image, "open", return_value=FakeImage()):
            monkeypatch.setattr(ie, "_exif_pillow", mock.Mock(return_value={"fecha": "f", "camara": "c", "gps": None, "exif_raw": {}}))
            monkeypatch.setattr(ie, "_extraer_iptc", mock.Mock(return_value={"titulo": "t"}))
            monkeypatch.setattr(ie, "_describir_imagen", mock.Mock(return_value={"descripcion": "d"}))
            monkeypatch.setattr(ie, "_paleta_colores", mock.Mock(return_value=["#fff"]))
            out = ie.extraer_imagen(ruta)
        assert out["tipo"] == "imagen"
        assert out["metadatos"]["formato"] == "JPEG"
        assert out["metadatos"]["dimensiones"] == "100x50"
        assert out["metadatos"]["tamano_bytes"] == 3
        assert out["resumen_visual"] == "d"
        assert out["paleta"] == ["#fff"]

    def test_extraer_imagen_fallback_exiftool(self, ie, monkeypatch, tmp_path) -> None:
        ruta = tmp_path / "a.jpg"
        ruta.write_bytes(b"img")
        with mock.patch.object(ie.Image, "open", return_value=FakeImage()):
            monkeypatch.setattr(ie, "_exif_pillow", mock.Mock(return_value={"fecha": "", "camara": "", "gps": None, "exif_raw": {}}))
            monkeypatch.setattr(ie, "_exif_exiftool", mock.Mock(return_value={"fecha": "exif", "camara": "cam", "gps": "g", "exif_raw": {"k": "v"}}))
            monkeypatch.setattr(ie, "_extraer_iptc", mock.Mock(return_value={}))
            monkeypatch.setattr(ie, "_describir_imagen", mock.Mock(return_value={"descripcion": ""}))
            monkeypatch.setattr(ie, "_paleta_colores", mock.Mock(return_value=[]))
            out = ie.extraer_imagen(ruta)
        assert out["metadatos"]["fecha"] == "exif"
        assert out["metadatos"]["camara"] == "cam"
        assert out["metadatos"]["gps"] == "g"


class TestExtraerCaracteristicas:
    @pytest.mark.asyncio
    async def test_file_not_found(self, ie, tmp_path) -> None:
        out = await ie.extraer_caracteristicas_imagen(str(tmp_path / "nope.jpg"))
        assert out == {"status": "error", "reason": "file_not_found"}

    @pytest.mark.asyncio
    async def test_success(self, ie, monkeypatch, tmp_path) -> None:
        ruta = tmp_path / "a.jpg"
        ruta.write_bytes(b"img")
        with mock.patch.object(ie.Image, "open", return_value=FakeImage()):
            monkeypatch.setattr(ie, "_exif_pillow", mock.Mock(return_value={"fecha": "", "camara": "", "gps": None, "exif_raw": {}}))
            monkeypatch.setattr(ie, "_exif_exiftool", mock.Mock(return_value={}))
            monkeypatch.setattr(ie, "_extraer_iptc", mock.Mock(return_value={}))
            monkeypatch.setattr(ie, "_describir_imagen", mock.Mock(return_value={"descripcion": ""}))
            monkeypatch.setattr(ie, "_paleta_colores", mock.Mock(return_value=[]))
            out = await ie.extraer_caracteristicas_imagen(str(ruta))
        assert out["status"] == "success"
        assert out["tipo"] == "imagen"

    @pytest.mark.asyncio
    async def test_error_interno(self, ie, monkeypatch, tmp_path) -> None:
        ruta = tmp_path / "a.jpg"
        ruta.write_bytes(b"img")
        with mock.patch.object(ie.Image, "open", side_effect=OSError("corrupt")):
            out = await ie.extraer_caracteristicas_imagen(str(ruta))
        assert out["status"] == "error"
