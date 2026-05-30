import logging
from typing import Any

import requests

logger = logging.getLogger("APIConnector")


class APIConnector:
    def __init__(self, base_url: str, api_key: str | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.headers: dict[str, str] = {"Content-Type": "application/json"}
        if api_key:
            self.headers["Authorization"] = f"Bearer {api_key}"

    def get(self, endpoint: str, params: dict[str, Any] | None = None) -> dict[str, Any] | None:
        try:
            resp = requests.get(
                f"{self.base_url}/{endpoint}", headers=self.headers, params=params, timeout=10
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            logger.error("API GET error: %s", exc)
            return None

    def post(self, endpoint: str, data: dict[str, Any]) -> dict[str, Any] | None:
        try:
            resp = requests.post(
                f"{self.base_url}/{endpoint}", headers=self.headers, json=data, timeout=10
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            logger.error("API POST error: %s", exc)
            return None
