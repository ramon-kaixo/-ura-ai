import os
import time
from collections import defaultdict


class RateLimiter:
    def __init__(self) -> None:
        self._ventanas: dict[str, list[float]] = defaultdict(list)
        self._por_defecto = int(os.environ.get("MOCHILA_RATE_LIMIT_DEFAULT", "30"))
        self._limites: dict[str, int] = {}

    def _cargar_config(self, config_file: str | None = None) -> None:
        import json
        import os

        path = config_file or os.path.expanduser("~/.nervioso/rate_limits.json")
        try:
            with open(path) as f:
                data = json.load(f)
            for provider, limit in data.items():
                if isinstance(limit, int):
                    self._limites[provider] = limit
        except (FileNotFoundError, json.JSONDecodeError):
            pass

    def configurar(self, provider: str, max_requests: int) -> None:
        self._limites[provider] = max_requests

    def _limite(self, provider: str) -> int:
        return self._limites.get(provider, self._por_defecto)

    def puede_pasar(self, provider: str) -> tuple[bool, int, int]:
        ahora = time.time()
        ventana = 60.0
        cola = self._ventanas[provider]
        while cola and cola[0] < ahora - ventana:
            cola.pop(0)
        limite = self._limite(provider)
        puede = len(cola) < limite
        return puede, len(cola), limite

    def registrar(self, provider: str) -> None:
        self._ventanas[provider].append(time.time())

    def estado(self, provider: str) -> dict:
        puede, actual, limite = self.puede_pasar(provider)
        return {
            "provider": provider,
            "can_pass": puede,
            "current_requests": actual,
            "max_requests": limite,
            "window_seconds": 60,
        }
