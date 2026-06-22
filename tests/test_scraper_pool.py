
"""Tests de scraper_pool."""
from core.scraper_pool import DomainDecoupledPool


def test_pool_creates():
    pool = DomainDecoupledPool(delay=0.1)
    assert pool is not None
    assert pool.delay == 0.1
    assert pool.queues == {}
