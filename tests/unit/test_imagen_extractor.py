"""Tests para core/memoria/extractores/imagen_extractor.py."""

from pathlib import Path

import pytest

from core.memoria.extractores import imagen_extractor as ie


class TestExtraerImagen:
    def test_extraer_jpg(self) -> None:
        ruta = Path("/tmp/test_image.jpg")
        result = ie.extraer_imagen(ruta)
        assert result["tipo"] == "imagen"
        assert result["metadatos"]["formato"] == "JPEG"
        assert result["metadatos"]["dimensiones"] == "100x100"
        assert "tamano_bytes" in result["metadatos"]
        assert result["ruta"] == str(ruta)

    def test_extraer_png(self) -> None:
        ruta = Path("/tmp/test_image.png")
        result = ie.extraer_imagen(ruta)
        assert result["tipo"] == "imagen"
        assert result["metadatos"]["formato"] == "PNG"
        assert result["metadatos"]["dimensiones"] == "50x50"

    def test_paleta_colores(self) -> None:
        ruta = Path("/tmp/test_image.jpg")
        paleta = ie._paleta_colores(ruta, k=3)
        assert isinstance(paleta, list)
        assert len(paleta) <= 3
        for color in paleta:
            assert color.startswith("#")
            assert len(color) == 7

    def test_exif_pillow_sin_exif(self) -> None:
        ruta = Path("/tmp/test_image.png")
        exif = ie._exif_pillow(ruta)
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

    async def test_jpg_ok(self) -> None:
        ruta = "/tmp/test_image.jpg"
        result = await ie.extraer_caracteristicas_imagen(ruta)
        assert result["status"] == "success"
        assert result["tipo"] == "imagen"
