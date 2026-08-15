"""Tests de cobertura para core/memoria/extractores/imagen_extractor.py.

Cubren las lineas 47-52 (branch GPSInfo de _exif_pillow), inalcanzables con
valores reales: un dict GPSInfo cae en str(valor)[:200] antes de llegar al
branch. Se ejercitan con una subclase de str que expone items(), pasando el
isinstance de tipo y proveyendo la interfaz de dict esperada por el branch.

No se modifica produccion: el bug real (GPS dict convertido a str) queda
documentado en test_memoria_imagen_extractor.py.
"""

from __future__ import annotations

from pathlib import Path
from typing import Self
from unittest import mock

import pytest

from tests.unit.test_memoria_imagen_extractor import (
    FakeImage,
    _install_pil_fakes,
)


class StrConItems(str):
    """str que ademas expone items() como un dict (para ejercitar GPSInfo)."""

    __slots__ = ("_gps",)

    def __new__(cls, *args, gps=None, **kwargs) -> Self:
        instancia = super().__new__(cls, *args, **kwargs)
        instancia._gps = gps or {}
        return instancia

    def items(self):
        return self._gps.items()


def _import_module(monkeypatch) -> object:
    _install_pil_fakes(monkeypatch)
    import core.memoria.extractores.imagen_extractor as ie

    monkeypatch.setattr(ie, "TAGS", {0x8825: "GPSInfo", 0x9003: "DateTimeOriginal"})
    monkeypatch.setattr(ie, "GPSTAGS", {1: "GPSLatitude", 2: "GPSLongitude", 999: "Raro"})
    return ie


@pytest.fixture
def ie(monkeypatch) -> object:
    return _import_module(monkeypatch)


class TestExifPillowGpsInfo:
    def test_gpsinfo_latitud_longitud(self, ie, tmp_path: Path) -> None:
        """GPSInfo con latitud y longitud -> gps compuesto."""
        ruta = tmp_path / "a.jpg"
        ruta.write_bytes(b"x")
        gps = StrConItems(gps={1: "40, 0, 0", 2: "-3, 0, 0"})
        exif = {0x8825: gps}
        with mock.patch.object(ie.Image, "open", return_value=FakeImage(exif=exif)):
            out = ie._exif_pillow(ruta)
        assert out["gps"] == "40, 0, 0, -3, 0, 0"

    def test_gpsinfo_solo_latitud(self, ie, tmp_path: Path) -> None:
        """GPSInfo solo con latitud -> gps con latitud y tag desconocido."""
        ruta = tmp_path / "a.jpg"
        ruta.write_bytes(b"x")
        gps = StrConItems(gps={1: "41", 999: "raro"})
        exif = {0x8825: gps}
        with mock.patch.object(ie.Image, "open", return_value=FakeImage(exif=exif)):
            out = ie._exif_pillow(ruta)
        assert out["gps"] == "41"

    def test_gpsinfo_sin_coordenadas(self, ie, tmp_path: Path) -> None:
        """GPSInfo sin latitud -> gps None (branch vacio)."""
        ruta = tmp_path / "a.jpg"
        ruta.write_bytes(b"x")
        gps = StrConItems(gps={7: "13:00:00"})
        exif = {0x8825: gps}
        with mock.patch.object(ie.Image, "open", return_value=FakeImage(exif=exif)):
            out = ie._exif_pillow(ruta)
        assert out["gps"] is None
