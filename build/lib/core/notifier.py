"""notifier.py — Canal de alertas humano para URA.

Soporta Telegram y Pushover. Los tokens se cargan desde variables de entorno
(TELEGRAM_TOKEN, PUSHOVER_USER_KEY, PUSHOVER_APP_TOKEN).
"""

import logging
import os
from typing import Literal

import httpx

log = logging.getLogger("ura.notifier")

_TELEGRAM_TOKEN: str | None = None
_TELEGRAM_CHAT_ID: str | None = None

PUSHOVER_USER = os.environ.get("PUSHOVER_USER_KEY", "")
PUSHOVER_TOKEN = os.environ.get("PUSHOVER_APP_TOKEN", "")


def _get_telegram_token() -> str | None:
    global _TELEGRAM_TOKEN, _TELEGRAM_CHAT_ID
    if _TELEGRAM_TOKEN is None:
        _TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
        _TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
    return _TELEGRAM_TOKEN or None


def _send_telegram(message: str) -> bool:
    token = _get_telegram_token()
    if not token or not _TELEGRAM_CHAT_ID:
        log.debug("Telegram not configured (TELEGRAM_TOKEN or TELEGRAM_CHAT_ID missing)")
        return False
    try:
        r = httpx.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": _TELEGRAM_CHAT_ID, "text": message[:4096], "parse_mode": "HTML"},
            timeout=10,
        )
        return r.status_code == 200
    except Exception as e:
        log.warning("Telegram send failed: %s", e)
        return False


def _send_pushover(message: str) -> bool:
    if not PUSHOVER_TOKEN or not PUSHOVER_USER:
        log.debug("Pushover not configured")
        return False
    try:
        r = httpx.post(
            "https://api.pushover.net/1/messages.json",
            json={"token": PUSHOVER_TOKEN, "user": PUSHOVER_USER, "message": message[:1024]},
            timeout=10,
        )
        return r.status_code == 200
    except Exception as e:
        log.warning("Pushover send failed: %s", e)
        return False


def notify(
    message: str,
    level: Literal["info", "warning", "critical"] = "warning",
    channels: list[str] | None = None,
) -> bool:
    """Send alert via configured channels.

    Args:
        message: Alert text (plaintext, no HTML).
        level: Severity level — info, warning, critical.
        channels: Which channels to use (default: all configured).

    Returns:
        True if at least one channel delivered.

    """
    if channels is None:
        channels = ["telegram", "pushover"]

    tag = {"info": "ℹ️", "warning": "⚠️", "critical": "🚨"}.get(level, "⚠️")
    formatted = f"{tag} URA [{level.upper()}]: {message}"

    ok = False
    if "telegram" in channels and _send_telegram(formatted):
        ok = True
    if "pushover" in channels and _send_pushover(formatted):
        ok = True
    return ok
