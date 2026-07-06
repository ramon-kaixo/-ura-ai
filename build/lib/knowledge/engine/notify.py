"""Notificaciones — sistema de integración con servicios externos.

Soporta:
  - Webhooks HTTP (POST JSON a URLs configuradas)
  - Slack (formatea mensajes para Slack webhooks)
  - Email (SMTP, configuración vía entorno)

Cada canal envía en su propio hilo (no bloquean entre sí).
Todos los HTTP tienen timeout explícito.
SSRF protegido: se bloquean IPs privadas para webhooks configurables por usuario.
Retry con backoff exponencial + jitter para errores transitorios.
Métricas Prometheus para cada canal.
"""

from __future__ import annotations

import ipaddress
import json
import logging
import os
import random
import smtplib
import socket
import ssl
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from email.message import EmailMessage
from typing import Any, Protocol
from urllib.request import Request, urlopen
from urllib.parse import urlparse

log = logging.getLogger("ura.knowledge.notify")

_TIMEOUT_S = 10
_MAX_RETRIES = 3
_BACKOFF_BASE_S = 1.0
_BACKOFF_MAX_S = 10.0
_PRIVATE_NETWORKS = [
    "127.0.0.0/8", "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16",
    "::1/128", "fc00::/7",
]


# ── SSRF protection ──────────────────────────────────────────────────────


class SSRFError(ValueError):
    """URL apunta a una red privada o localhost."""


def _validate_url(url: str) -> str:
    """Valida que la URL no apunte a una red privada (SSRF protection)."""
    parsed = urlparse(url)
    host = parsed.hostname or ""
    # Resolver DNS y verificar IP
    try:
        addrs = socket.getaddrinfo(host, None)
        for family, _, _, _, sockaddr in addrs:
            ip = sockaddr[0]
            for net in _PRIVATE_NETWORKS:
                if ipaddress.ip_address(ip) in ipaddress.ip_network(net):
                    raise SSRFError(f"URL {url[:60]} apunta a red privada {ip} ({net})")
    except socket.gaierror as exc:
        raise SSRFError(f"No se pudo resolver {host}: {exc}") from exc
    return url


# ── Retry helper ─────────────────────────────────────────────────────────


def _should_retry(exception: Exception) -> bool:
    """Determina si un error es transitorio y merece reintento."""
    # Verificar por tipo de excepción
    if isinstance(exception, (ConnectionRefusedError, ConnectionResetError, ConnectionAbortedError, TimeoutError, ConnectionError)):
        return True
    # Buscar palabras clave en el mensaje
    msg = str(exception).lower()
    transitorios = [
        "timeout", "timed out", "refused", "reset", "broken pipe",
        "temporarily unavailable", "connection refused",
        "429", "500", "502", "503", "504",
    ]
    if any(t in msg for t in transitorios):
        return True
    return False


def _backoff(attempt: int) -> None:
    """Backoff exponencial con jitter."""
    delay = min(_BACKOFF_BASE_S * (2 ** attempt) + random.uniform(0, 0.5), _BACKOFF_MAX_S)
    time.sleep(delay)


# ── Metric helpers ───────────────────────────────────────────────────────


def _record_metric(counter_name: str, channel: str, status: str, duration_ms: float = 0) -> None:
    """Registra métrica de notificación (best-effort)."""
    try:
        from prometheus_client import Counter, Histogram

        c = Counter(
            f"ke_notifications_{counter_name}_total",
            f"Notifications {counter_name}",
            ["channel"],
        )
        c.labels(channel=channel).inc()

        if duration_ms > 0:
            h = Histogram(
                "ke_notification_duration_seconds",
                "Notification duration",
                ["channel"],
                buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0),
            )
            h.labels(channel=channel).observe(duration_ms / 1000)
    except Exception:
        pass


# ── Event payloads ────────────────────────────────────────────────────────


@dataclass
class Notification:
    """Payload genérico de notificación."""

    title: str
    message: str
    severity: str = "info"
    fields: list[tuple[str, str]] = field(default_factory=list)
    timestamp: str = ""


def format_compile_event(reason: str, docs_changed: int, docs_total: int, errors: int) -> Notification:
    sev = "success" if errors == 0 else "error"
    return Notification(title=f"Compile: {reason}", message=f"{docs_changed} changed, {docs_total} total",
        severity=sev, fields=[("Changed", str(docs_changed)), ("Total", str(docs_total)), ("Errors", str(errors))])


def format_archive_event(kind: str, commit: str, files: int) -> Notification:
    return Notification(title=f"Archive: {kind}", message=f"Commit {commit[:12]}, {files} files",
        severity="info", fields=[("Kind", kind), ("Commit", commit[:12]), ("Files", str(files))])


def format_search_event(query: str, results: int, latency_ms: float) -> Notification:
    return Notification(title=f"Search: {query[:50]}", message=f"{results} results in {latency_ms:.0f}ms",
        severity="info", fields=[("Query", query[:50]), ("Results", str(results)), ("Latency", f"{latency_ms:.0f}ms")])


# ── Notifier Protocol ─────────────────────────────────────────────────────


class Notifier(Protocol):
    def send(self, notification: Notification) -> bool: ...


# ── WebhookNotifier ───────────────────────────────────────────────────────


class WebhookNotifier:
    def __init__(self, url: str, secret: str | None = None):
        self._url = url
        self._secret = secret

    def send(self, notification: Notification) -> bool:
        t0 = time.monotonic()
        try:
            _validate_url(self._url)
            payload = {
                "title": notification.title,
                "message": notification.message,
                "severity": notification.severity,
                "fields": {k: v for k, v in notification.fields},
            }
            headers = {"Content-Type": "application/json"}
            if self._secret:
                headers["X-Webhook-Secret"] = self._secret

            data = json.dumps(payload).encode()
            last_exc: Exception | None = None

            for attempt in range(_MAX_RETRIES):
                try:
                    req = Request(self._url, data=data, headers=headers, method="POST")
                    with urlopen(req, timeout=_TIMEOUT_S) as resp:
                        ok = resp.status < 300
                        _record_metric("sent", "webhook", "ok" if ok else "fail", (time.monotonic() - t0) * 1000)
                        if ok:
                            return True
                        log.warning("Webhook returned %d (attempt %d)", resp.status, attempt + 1)
                        if resp.status in (429, 500, 502, 503, 504):
                            _backoff(attempt)
                            continue
                        return False
                except Exception as e:
                    last_exc = e
                    if _should_retry(e) and attempt < _MAX_RETRIES - 1:
                        _backoff(attempt)
                        continue
                    raise

            if last_exc:
                raise last_exc
            return False
        except SSRFError:
            log.warning("Webhook blocked (SSRF): %s", self._url[:60])
            _record_metric("failed", "webhook", "ssrf")
            return False
        except Exception as exc:
            log.warning("Webhook failed: %s", str(exc)[:100])
            _record_metric("failed", "webhook", "error")
            return False


# ── SlackNotifier ─────────────────────────────────────────────────────────


class SlackNotifier:
    def __init__(self, webhook_url: str):
        self._url = webhook_url

    def send(self, notification: Notification) -> bool:
        t0 = time.monotonic()
        try:
            _validate_url(self._url)
            colors = {"info": "#2196F3", "warning": "#FF9800", "error": "#F44336", "success": "#4CAF50"}
            payload = {"attachments": [{
                "color": colors.get(notification.severity, "#2196F3"),
                "title": notification.title,
                "text": notification.message,
                "fields": [{"title": k, "value": v, "short": True} for k, v in notification.fields],
                "footer": "Knowledge Engine",
            }]}
            data = json.dumps(payload).encode()
            req = Request(self._url, data=data, headers={"Content-Type": "application/json"}, method="POST")
            with urlopen(req, timeout=_TIMEOUT_S) as resp:
                ok = resp.status < 300
                _record_metric("sent", "slack", "ok" if ok else "fail", (time.monotonic() - t0) * 1000)
                return ok
        except SSRFError:
            log.warning("Slack blocked (SSRF): %s", self._url[:60])
            _record_metric("failed", "slack", "ssrf")
            return False
        except Exception as exc:
            log.warning("Slack failed: %s", str(exc)[:100])
            _record_metric("failed", "slack", "error")
            return False


# ── EmailNotifier ─────────────────────────────────────────────────────────


class EmailNotifier:
    def __init__(self):
        self._host = os.environ.get("URA_SMTP_HOST", "")
        self._port = int(os.environ.get("URA_SMTP_PORT", "587"))
        self._user = os.environ.get("URA_SMTP_USER", "")
        self._password = os.environ.get("URA_SMTP_PASS", "")
        self._from = os.environ.get("URA_EMAIL_FROM", "ura@localhost")
        self._to = os.environ.get("URA_EMAIL_TO", "")
        # Sanitize for logging — nunca loguear password
        self._log_desc = f"smtp:{self._user}@{self._host}:{self._port}"

    @property
    def configured(self) -> bool:
        return bool(self._host and self._to)

    def send(self, notification: Notification) -> bool:
        if not self.configured:
            return False
        t0 = time.monotonic()
        try:
            msg = EmailMessage()
            msg["Subject"] = f"[URA] {notification.title}"
            msg["From"] = self._from
            msg["To"] = self._to
            body = f"{notification.title}\n{'=' * 40}\n{notification.message}\n\n"
            for k, v in notification.fields:
                body += f"  {k}: {v}\n"
            msg.set_content(body)

            context = ssl.create_default_context()
            with smtplib.SMTP(self._host, self._port, timeout=_TIMEOUT_S) as server:
                server.starttls(context=context)
                if self._user:
                    server.login(self._user, self._password)
                server.send_message(msg)
            log.info("Email sent: %s", notification.title)
            _record_metric("sent", "email", "ok", (time.monotonic() - t0) * 1000)
            return True
        except Exception as exc:
            log.warning("Email failed (%s): %s", self._log_desc, str(exc)[:100])
            _record_metric("failed", "email", "error")
            return False


# ── NotificationService (concurrente) ────────────────────────────────────


class NotificationService:
    """Envía notificaciones a todos los canales en paralelo.

    Cada canal se ejecuta en su propio hilo.
    Un canal lento no retrasa a los demás.
    Timeout total por canal: _TIMEOUT_S segundos.
    """

    def __init__(self, max_workers: int = 5):
        self._notifiers: list[Notifier] = []
        self._max_workers = max_workers

    def add_notifier(self, notifier: Notifier) -> None:
        self._notifiers.append(notifier)

    def send(self, notification: Notification) -> int:
        """Envía a todos los canales en paralelo.

        Returns:
            Número de canales que respondieron OK.
        """
        if not self._notifiers:
            return 0
        ok_count = 0
        with ThreadPoolExecutor(max_workers=min(len(self._notifiers), self._max_workers)) as pool:
            futures = {pool.submit(n.send, notification): n for n in self._notifiers}
            for future in as_completed(futures):
                try:
                    if future.result(timeout=_TIMEOUT_S + 5):
                        ok_count += 1
                except Exception:
                    pass
        return ok_count

    @property
    def notifier_count(self) -> int:
        return len(self._notifiers)


# ── Singleton global ─────────────────────────────────────────────────────

_NOTIFY_INSTANCE: NotificationService | None = None


def get_notifier() -> NotificationService:
    global _NOTIFY_INSTANCE
    if _NOTIFY_INSTANCE is not None:
        return _NOTIFY_INSTANCE
    _NOTIFY_INSTANCE = NotificationService()
    email = EmailNotifier()
    if email.configured:
        _NOTIFY_INSTANCE.add_notifier(email)
    return _NOTIFY_INSTANCE


def set_notifier(service: NotificationService) -> None:
    global _NOTIFY_INSTANCE
    _NOTIFY_INSTANCE = service
