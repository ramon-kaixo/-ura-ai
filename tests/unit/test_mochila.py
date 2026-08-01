"""Test mochila_engine."""

from pathlib import Path

import pytest

from mochila_engine import FaseID, MochilaEngine, TipoPipeline

m = MochilaEngine.nueva("https://ejemplo.com/img.jpg", TipoPipeline.IMAGEN, "p")


@pytest.mark.asyncio
async def test_crear() -> None:
    assert m.url == "https://ejemplo.com/img.jpg"
    assert m.tipo == TipoPipeline.IMAGEN


@pytest.mark.asyncio
async def test_red() -> None:
    m.reg_r(motor_id="m1", latencia_ms=120.5)
    assert m.red["motor_id"] == "m1"


@pytest.mark.asyncio
async def test_hashes() -> None:
    m.reg_h(sha256="abc123")
    assert m.hashes["sha256"] == "abc123"


@pytest.mark.asyncio
async def test_guardar() -> None:
    p = Path("/tmp/pm/m.json")
    m.guardar(p)
    assert p.exists()


@pytest.mark.asyncio
async def test_cargar() -> None:
    p = Path("/tmp/pm/m2.json")
    m2 = MochilaEngine.nueva("https://ejemplo.com/img.jpg", TipoPipeline.IMAGEN, "p2")
    m2.guardar(p)
    m3 = MochilaEngine.cargar(p)
    assert m3.id == m2.id


@pytest.mark.asyncio
async def test_fase() -> None:
    async with m.fase(FaseID.F1_ROUTER) as c:
        c.dt["r"] = "ok"
    assert m.fc(FaseID.F1_ROUTER)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
