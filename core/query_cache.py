"""Shim temporal — query_cache se ha movido a motor.core.query_cache."""
from motor.core.query_cache import AsyncQueryCache  # noqa: F401
