"""Stub: CachedWeather — datos meteorológicos con caché."""

import logging

log = logging.getLogger(__name__)


class CachedWeather:
    """Obtiene datos meteorológicos con caché local."""

    def __init__(self, city: str = "Pamplona", **kwargs):
        self.city = city
        self.cache = {}
        log.info("CachedWeather inicializado (stub)")

    def get_current(self) -> dict:
        return {"city": self.city, "temp": None, "status": "stub"}

    def get_forecast(self, days: int = 3) -> list:
        return []
