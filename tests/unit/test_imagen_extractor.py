"""Tests para core/memoria/extractores/imagen_extractor.py."""

from pathlib import Path

import pytest
from PIL import Image

from core.memoria.extractores import imagen_extractor as ie


@pytest.fixture(scope="module")
def imagen_jpg(tmp_path_factory) -> Path:
    ruta = tmp_path_factory.mktemp("img") / "test_image.jpg"
    Image.new("RGB", (100, 100), "red").save(ruta, "JPEG")
    return ruta


@pytest.fixture(scope="module")
def imagen_png(tmp_path_factory) -> Path:
    ruta = tmp_path_factory.mktemp("img") / "test_image.png"
    Image.new("RGB", (50, 50), "blue").save(ruta, "PNG")
    return ruta


class TestExtraerImagen:
    def test_extraer_jpg(self, imagen_jpg: Path) -> None:
        result = ie.extraer_imagen(imagen_jpg)
        assert result["tipo"] == "imagen"
        assert result["metadatos"]["formato"] == "JPEG"
        assert result["metadatos"]["dimensiones"] == "100x100"
        assert "tamano_bytes" in result["metadatos"]
        assert result["ruta"] == str(imagen_jpg)

    def test_extraer_png(self, imagen_png: Path) -> None:
        result = ie.extraer_imagen(imagen_png)
        assert result["tipo"] == "imagen"
        assert result["metadatos"]["formato"] == "PNG"
        assert result["metadatos"]["dimensiones"] == "50x50"

    def test_paleta_colores(self, imagen_jpg: Path) -> None:
        paleta = ie._paleta_colores(imagen_jpg, k=3)
        assert isinstance(paleta, list)
        assert len(paleta) <= 3
        for color in paleta:
            assert color.startswith("#")
            assert len(color) == 7

    def test_exif_pillow_sin_exif(self, imagen_png: Path) -> None:
        exif = ie._exif_pillow(imagen_png)
        assert exif["fecha"] == ""
        assert exif["camara"] == ""
        assert exif["gps"] is None
        assert isinstance(exif["exif_raw"], dict)


@pytest.mark.asyncio
class TestExtraerCaracteristicasImagen:
    async def test_archivo_no_existe(self) -> None:
        result = await ie.extraer_caracteristicas_imagen("/tmp/no_existe_12345.jpg")
        assert result["status"] == "error"
        assert result["reason"] == "file_not_found"

    async def test_jpg_ok(self, imagen_jpg: Path) -> None:
        result = await ie.extraer_caracteristicas_imagen(str(imagen_jpg))
        assert result["status"] == "success"
        assert result["tipo"] == "imagen"
