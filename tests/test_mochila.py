"""Test mochila_engine."""

from pathlib import Path

import pytest

from mochila_engine import FaseID, MochilaEngine, TipoPipeline

m = MochilaEngine.nueva("https://ejemplo.com/img.jpg", TipoPipeline.IMAGEN, "p")


@pytest.mark.asyncio
async def test_crear():
    assert m.url == "https://ejemplo.com/img.jpg"
    assert m.tipo == TipoPipeline.IMAGEN


@pytest.mark.asyncio
async def test_red():
    m.reg_r(motor_id="m1", latencia_ms=120.5)
    assert m.red["motor_id"] == "m1"


@pytest.mark.asyncio
async def test_hashes():
    m.reg_h(sha256="abc123")
    assert m.hashes["sha256"] == "abc123"


@pytest.mark.asyncio
async def test_guardar():
    p = Path("/tmp/pm/m.json")
    m.guardar(p)
    assert p.exists()


@pytest.mark.asyncio
async def test_cargar():
    p = Path("/tmp/pm/m.json")
    m2 = MochilaEngine.cargar(p)
    assert m2.id == m.id


@pytest.mark.asyncio
async def test_fase():
    async with m.fase(FaseID.F1_ROUTER) as c:
        c.dt["r"] = "ok"
    assert m.fc(FaseID.F1_ROUTER)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
