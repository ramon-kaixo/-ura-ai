"""notifier.py — Canal de alertas humano para URA.

Soporta Telegram y Pushover. Los tokens se cargan desde variables de entorno
(TELEGRAM_TOKEN, PUSHOVER_USER_KEY, PUSHOVER_APP_TOKEN).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Literal

import httpx

if TYPE_CHECKING:
    from core.interfaces import ISecretStore

log = logging.getLogger("ura.notifier")

_TELEGRAM_TOKEN: str | None = None
_TELEGRAM_CHAT_ID: str | None = None
_PUSHOVER_USER: str = ""
_PUSHOVER_TOKEN: str = ""


def _ensure_secrets(store: ISecretStore | None = None) -> None:
    global _TELEGRAM_TOKEN, _TELEGRAM_CHAT_ID, _PUSHOVER_USER, _PUSHOVER_TOKEN  # noqa: PLW0603
    if _TELEGRAM_TOKEN is not None:
        return
    _TELEGRAM_TOKEN = ""
    _TELEGRAM_CHAT_ID = ""
    if store is not None:
        _TELEGRAM_TOKEN = store.get_secret("TELEGRAM_TOKEN", "") or ""
        _TELEGRAM_CHAT_ID = store.get_secret("TELEGRAM_CHAT_ID", "") or ""
        _PUSHOVER_USER = store.get_secret("PUSHOVER_USER_KEY", "") or ""
        _PUSHOVER_TOKEN = store.get_secret("PUSHOVER_APP_TOKEN", "") or ""
    else:
        from motor.core.secrets import get_secret as _get

        _TELEGRAM_TOKEN = _get("TELEGRAM_TOKEN", "")
        _TELEGRAM_CHAT_ID = _get("TELEGRAM_CHAT_ID", "")
        _PUSHOVER_USER = _get("PUSHOVER_USER_KEY", "")
        _PUSHOVER_TOKEN = _get("PUSHOVER_APP_TOKEN", "")


def _send_telegram(message: str) -> bool:
    if not _TELEGRAM_TOKEN or not _TELEGRAM_CHAT_ID:
        log.debug("Telegram not configured (TELEGRAM_TOKEN or TELEGRAM_CHAT_ID missing)")
        return False
    try:
        r = httpx.post(
            f"https://api.telegram.org/bot{_TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": _TELEGRAM_CHAT_ID, "text": message[:4096], "parse_mode": "HTML"},
            timeout=10,
        )
        return r.status_code == 200
    except Exception as e:
        log.warning("Telegram send failed: %s", e)
        return False


def _send_pushover(message: str) -> bool:
    if not _PUSHOVER_TOKEN or not _PUSHOVER_USER:
        log.debug("Pushover not configured")
        return False
    try:
        r = httpx.post(
            "https://api.pushover.net/1/messages.json",
            json={"token": _PUSHOVER_TOKEN, "user": _PUSHOVER_USER, "message": message[:1024]},
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
    store: ISecretStore | None = None,
) -> bool:
    _ensure_secrets(store)

    if channels is None:
        channels = ["telegram", "pushover"]

    tag = {"info": "ℹ️", "warning": "⚠️", "critical": "🚨"}.get(level, "⚠️")  # noqa: RUF001
    formatted = f"{tag} URA [{level.upper()}]: {message}"

    ok = False
    if "telegram" in channels and _send_telegram(formatted):
        ok = True
    if "pushover" in channels and _send_pushover(formatted):
        ok = True
    return ok
