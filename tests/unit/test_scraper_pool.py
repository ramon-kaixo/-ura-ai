"""Tests para core/scraper_pool.py — DomainDecoupledPool."""
from __future__ import annotations

import asyncio

import pytest

from core.scraper_pool import DomainDecoupledPool


class TestDomainDecoupledPool:
    @pytest.mark.asyncio
    async def test_procesa_urls_por_dominio(self) -> None:
        pool = DomainDecoupledPool(delay=0.001)
        scrapeados: list[str] = []

        async def scrape(url: str) -> None:
            scrapeados.append(url)

        await pool.run(
            ["https://a.com/1", "https://a.com/2", "https://b.com/1"],
            scrape,
            wait=True,
        )
        assert sorted(scrapeados) == ["https://a.com/1", "https://a.com/2", "https://b.com/1"]
        assert pool.queues == {}  # limpiadas tras join

    @pytest.mark.asyncio
    async def test_una_cola_por_dominio(self) -> None:
        pool = DomainDecoupledPool(delay=0.001)

        async def scrape(url: str) -> None:
            pass

        await pool.run(["https://a.com/1", "https://a.com/2"], scrape, wait=False)
        assert len(pool.queues) == 1
        assert len(pool._workers) == 1
        await pool.join()

    @pytest.mark.asyncio
    async def test_error_scrape_no_rompe(self) -> None:
        pool = DomainDecoupledPool(delay=0.001)
        llamadas = []

        async def scrape(url: str) -> None:
            llamadas.append(url)
            if url.endswith("fail"):
                raise RuntimeError("boom")

        await pool.run(["https://a.com/ok", "https://a.com/fail", "https://a.com/ok2"], scrape, wait=True)
        assert len(llamadas) == 3

    @pytest.mark.asyncio
    async def test_join_cancela_workers(self) -> None:
        pool = DomainDecoupledPool(delay=0.001)

        async def scrape(url: str) -> None:
            pass

        await pool.run(["https://a.com/1"], scrape, wait=False)
        await pool.join()
        assert pool._workers == set()
        assert pool.queues == {}

    @pytest.mark.asyncio
    async def test_run_sin_wait_retorna_inmediato(self) -> None:
        pool = DomainDecoupledPool(delay=1.0)

        async def scrape(url: str) -> None:
            pass

        await asyncio.wait_for(
            pool.run(["https://a.com/1"], scrape, wait=False),
            timeout=1.0,
        )
        # Si wait=False, run no espera a los workers (no tarda por delay 1s)
        assert "a.com" in pool.queues
        await pool.join()

    @pytest.mark.asyncio
    async def test_sin_urls(self) -> None:
        pool = DomainDecoupledPool(delay=0.001)

        async def scrape(url: str) -> None:
            pass

        await pool.run([], scrape, wait=True)
        assert pool.queues == {}

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_worker_cancelado_medio_scrape(self) -> None:
        pool = DomainDecoupledPool(delay=5.0)

        async def scrape(url: str) -> None:
            await asyncio.sleep(0.5)

        await pool.run(["https://a.com/1"], scrape, wait=False)
        worker = next(iter(pool._workers))
        worker.cancel()
        with pytest.raises(asyncio.CancelledError):
            await worker
