"""Tests para core/memoria/rastreadores/ — stubs de fases comprar/hacer/saber."""
from __future__ import annotations

import pytest

from core.memoria.rastreadores.comprar import fase_comprar
from core.memoria.rastreadores.hacer import fase_hacer
from core.memoria.rastreadores.saber import fase_saber


class TestFaseComprar:
    @pytest.mark.asyncio
    async def test_stub(self) -> None:
        out = await fase_comprar("SEO local")
        assert out == {"status": "stub", "fase": "comprar", "keywords": "SEO local", "resultados": []}

    @pytest.mark.asyncio
    async def test_keywords_vacias(self) -> None:
        out = await fase_comprar("")
        assert out["fase"] == "comprar"
        assert out["keywords"] == ""


class TestFaseHacer:
    @pytest.mark.asyncio
    async def test_stub(self) -> None:
        out = await fase_hacer("herramientas gratis")
        assert out == {"status": "stub", "fase": "hacer", "keywords": "herramientas gratis", "resultados": []}

    @pytest.mark.asyncio
    async def test_keywords_vacias(self) -> None:
        out = await fase_hacer("")
        assert out["fase"] == "hacer"


class TestFaseSaber:
    @pytest.mark.asyncio
    async def test_stub(self) -> None:
        out = await fase_saber("teoria")
        assert out == {"status": "stub", "fase": "saber", "keywords": "teoria", "resultados": []}

    @pytest.mark.asyncio
    async def test_keywords_vacias(self) -> None:
        out = await fase_saber("")
        assert out["fase"] == "saber"
