"""NotifierPlugin — notificaciones reales (webhook + log)."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from scripts.pro.tuneladora.engine import PipelineEngine

log = logging.getLogger("ura.tuneladora.notifier")


class NotifierPlugin:
    """Notificaciones via webhook a Slack/Telegram/Discord."""

    def __init__(self, engine: PipelineEngine) -> None:
        self.engine = engine
        self.webhook_url = self._load_webhook()

    def _load_webhook(self) -> str | None:
        config_file = Path("config/notifications.json")
        if config_file.exists():
            try:
                data = json.loads(config_file.read_text())
                return data.get("webhook_url")
            except Exception:
                log.debug("config/notifications.json no valido")
        env = __import__("os").environ.get("URA_WEBHOOK_URL")
        if env:
            return env
        return None

    def notify(self, severity: str, title: str, message: str) -> dict[str, Any]:
        if severity == "critical":
            self._send_webhook(title, message)
        self.engine.log.info(f"[{severity.upper()}] {title}: {message}")
        return {"sent": True, "severity": severity, "title": title}

    def _send_webhook(self, title: str, message: str) -> None:
        if not self.webhook_url:
            return
        try:
            import httpx
            httpx.post(self.webhook_url, json={"title": title, "message": message}, timeout=10)
            log.info("Webhook enviado: %s", title)
        except Exception as e:
            log.warning("Webhook fallo: %s", e)
