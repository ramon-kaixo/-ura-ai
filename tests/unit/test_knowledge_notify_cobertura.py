"""Cobertura 100x100 de knowledge/engine/notify.py (TASK-20260815-003, P2).

Notificaciones Slack/Email/Webhook con red mockeada: urlopen (HTTP),
smtplib.SMTP (email), socket.getaddrinfo (SSRF DNS) y time.sleep (backoff).
"""

from __future__ import annotations

import json
import socket
import sys
from typing import Any, Self

import pytest

from knowledge.engine import notify
from knowledge.engine.notify import (
    EmailNotifier,
    Notification,
    NotificationService,
    SlackNotifier,
    SSRFError,
    WebhookNotifier,
    _backoff,
    _record_metric,
    _should_retry,
    _validate_url,
    format_archive_event,
    format_compile_event,
    format_search_event,
    get_notifier,
    set_notifier,
)

_PUBLIC_ADDRS = [(2, 1, 6, "", ("93.184.216.34", 0))]
_PRIVATE_ADDRS = [(2, 1, 6, "", ("127.0.0.1", 0))]


class FakeHttpResponse:
    """Respuesta HTTP mínima usada como context manager por urlopen."""

    def __init__(self, status: int) -> None:
        self.status = status

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        return None


class FakeUrlopen:
    """Devuelve una secuencia de status HTTP o lanza la excepción indicada."""

    def __init__(self, outcomes: list[int | type[Exception]]) -> None:
        self._outcomes = list(outcomes)
        self.calls: list[tuple[Any, int | None]] = []

    def __call__(self, request: Any, timeout: int | None = None) -> FakeHttpResponse:
        self.calls.append((request, timeout))
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, int):
            return FakeHttpResponse(outcome)
        raise outcome()


class FakeRequest:
    """Captura los argumentos de urllib.request.Request."""

    def __init__(
        self,
        url: str,
        data: bytes | None = None,
        headers: dict[str, str] | None = None,
        method: str | None = None,
    ) -> None:
        self.url = url
        self.data = data
        self.headers = headers
        self.method = method


class FakeSMTP:
    """Stub de smtplib.SMTP que registra starttls/login/send_message."""

    def __init__(self, host: str, port: int, timeout: int | None = None) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self.tls_started = False
        self.login_called: tuple[str, str] | None = None
        self.sent_messages: list[Any] = []

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def starttls(self, context: Any = None) -> None:
        self.tls_started = True

    def login(self, user: str, password: str) -> None:
        self.login_called = (user, password)

    def send_message(self, msg: Any) -> None:
        self.sent_messages.append(msg)


class FailingSMTP(FakeSMTP):
    """FakeSMTP que falla al enviar (para cubrir la rama de error)."""

    def send_message(self, msg: Any) -> None:
        raise ConnectionError("connection refused")


class FakeNotifier:
    """Notifier de prueba con resultado o excepción fijos."""

    def __init__(self, result: bool = True, exc: type[Exception] | None = None) -> None:
        self._result = result
        self._exc = exc

    def send(self, notification: Notification) -> bool:
        if self._exc is not None:
            raise self._exc()
        return self._result


@pytest.fixture(autouse=True)
def _public_dns(monkeypatch: pytest.MonkeyPatch) -> None:
    """getaddrinfo público por defecto (evita DNS real en todos los sends)."""

    monkeypatch.setattr(socket, "getaddrinfo", lambda host, port=None: _PUBLIC_ADDRS)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Entorno SMTP limpio, secretos mockeados y sleep sin espera real."""

    for var in ("URA_SMTP_HOST", "URA_SMTP_PORT", "URA_SMTP_USER", "URA_EMAIL_FROM", "URA_EMAIL_TO"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(notify, "get_secret", lambda name, default="": default)
    monkeypatch.setattr(notify.time, "sleep", lambda _seconds: None)


@pytest.fixture(autouse=True)
def _reset_singleton(monkeypatch: pytest.MonkeyPatch) -> None:
    """Aísla el singleton global entre tests."""

    monkeypatch.setattr(notify, "_NOTIFY_INSTANCE", None)


class TestValidateUrl:
    def test_ok_public_ip(self) -> None:
        assert _validate_url("https://example.com/hook") == "https://example.com/hook"

    def test_ok_empty_addrs(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(socket, "getaddrinfo", lambda host, port=None: [])
        assert _validate_url("https://example.com/hook") == "https://example.com/hook"

    def test_ok_no_hostname(self) -> None:
        assert _validate_url("not-a-url") == "not-a-url"

    def test_private_ipv4(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(socket, "getaddrinfo", lambda host, port=None: _PRIVATE_ADDRS)
        with pytest.raises(SSRFError):
            _validate_url("http://localhost/hook")

    def test_private_ipv6(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(socket, "getaddrinfo", lambda host, port=None: [(10, 1, 6, "", ("::1", 0))])
        with pytest.raises(SSRFError):
            _validate_url("http://[::1]/hook")

    def test_gaierror(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def boom(host: str, port: int | None = None) -> list[Any]:
            raise socket.gaierror("no such host")

        monkeypatch.setattr(socket, "getaddrinfo", boom)
        with pytest.raises(SSRFError):
            _validate_url("http://nope.invalid/hook")


class TestShouldRetry:
    def test_connection_error_types(self) -> None:
        assert _should_retry(ConnectionRefusedError("refused"))
        assert _should_retry(ConnectionResetError("reset"))
        assert _should_retry(ConnectionAbortedError("aborted"))
        assert _should_retry(TimeoutError("timeout"))
        assert _should_retry(ConnectionError("conn"))

    def test_message_keywords(self) -> None:
        assert _should_retry(RuntimeError("request timed out"))
        assert _should_retry(ValueError("status 502 Bad Gateway"))
        assert _should_retry(ValueError("upstream temporarily unavailable"))

    def test_not_transient(self) -> None:
        assert not _should_retry(ValueError("bad request"))
        assert not _should_retry(ValueError(""))


class TestBackoff:
    def test_backoff_delays(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: list[float] = []
        monkeypatch.setattr(notify.random, "uniform", lambda a, b: 0.4)
        monkeypatch.setattr(notify.time, "sleep", lambda s: calls.append(s))
        _backoff(0)
        _backoff(4)
        assert calls == [1.4, 10.0]


class TestRecordMetric:
    def test_counter_only(self) -> None:
        _record_metric("sent", "webhook", "ok")

    def test_counter_and_histogram(self) -> None:
        _record_metric("sent", "webhook", "ok", duration_ms=123.4)

    def test_import_failure_best_effort(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setitem(sys.modules, "prometheus_client", None)
        _record_metric("sent", "webhook", "ok", duration_ms=1.0)


class TestFormatters:
    def test_compile_event_success(self) -> None:
        n = format_compile_event("done", 3, 10, 0)
        assert n.severity == "success"
        assert n.title == "Compile: done"
        assert n.message == "3 changed, 10 total"
        assert n.fields[2] == ("Errors", "0")

    def test_compile_event_error(self) -> None:
        n = format_compile_event("failed", 1, 10, 2)
        assert n.severity == "error"
        assert n.fields[2] == ("Errors", "2")

    def test_archive_event_truncates_commit(self) -> None:
        n = format_archive_event("snapshot", "abcdef0123456789", 4)
        assert n.title == "Archive: snapshot"
        assert n.message == "Commit abcdef012345, 4 files"
        assert n.severity == "info"
        assert n.fields == [("Kind", "snapshot"), ("Commit", "abcdef012345"), ("Files", "4")]

    def test_search_event_truncates_query(self) -> None:
        n = format_search_event("q" * 60, 7, 12.6)
        assert n.title == "Search: " + "q" * 50
        assert n.message == "7 results in 13ms"
        assert n.fields[1] == ("Results", "7")
        assert n.fields[2] == ("Latency", "13ms")

    def test_notification_defaults(self) -> None:
        n = Notification(title="t", message="m")
        assert n.severity == "info"
        assert n.fields == []
        assert n.timestamp == ""


class TestWebhookNotifier:
    def test_send_ok_with_secret(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake = FakeUrlopen([200])
        monkeypatch.setattr(notify, "Request", FakeRequest)
        monkeypatch.setattr(notify, "urlopen", fake)
        n = WebhookNotifier("https://example.com/hook", secret="sekret")  # noqa: S106
        ok = n.send(Notification(title="t", message="m", severity="error", fields=[("k", "v")]))
        assert ok is True
        assert fake.calls[0][1] == 10
        req = fake.calls[0][0]
        assert req.method == "POST"
        assert req.headers["Content-Type"] == "application/json"
        assert req.headers["X-Webhook-Secret"] == "sekret"
        payload = json.loads(req.data)
        assert payload["title"] == "t"
        assert payload["severity"] == "error"
        assert payload["fields"] == {"k": "v"}

    def test_send_ok_without_secret(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake = FakeUrlopen([200])
        monkeypatch.setattr(notify, "Request", FakeRequest)
        monkeypatch.setattr(notify, "urlopen", fake)
        n = WebhookNotifier("https://example.com/hook")
        assert n.send(Notification(title="t", message="m")) is True
        assert "X-Webhook-Secret" not in fake.calls[0][0].headers

    def test_send_http_4xx_no_retry(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake = FakeUrlopen([400])
        monkeypatch.setattr(notify, "Request", FakeRequest)
        monkeypatch.setattr(notify, "urlopen", fake)
        n = WebhookNotifier("https://example.com/hook")
        assert n.send(Notification(title="t", message="m")) is False
        assert len(fake.calls) == 1

    def test_send_retryable_status_then_ok(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake = FakeUrlopen([500, 503, 200])
        monkeypatch.setattr(notify, "Request", FakeRequest)
        monkeypatch.setattr(notify, "urlopen", fake)
        n = WebhookNotifier("https://example.com/hook")
        assert n.send(Notification(title="t", message="m")) is True
        assert len(fake.calls) == 3

    def test_send_retryable_status_exhausted(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake = FakeUrlopen([429, 429, 429])
        monkeypatch.setattr(notify, "Request", FakeRequest)
        monkeypatch.setattr(notify, "urlopen", fake)
        n = WebhookNotifier("https://example.com/hook")
        assert n.send(Notification(title="t", message="m")) is False
        assert len(fake.calls) == 3

    def test_send_transient_exception_then_ok(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake = FakeUrlopen([ConnectionResetError, ConnectionResetError, 200])
        monkeypatch.setattr(notify, "Request", FakeRequest)
        monkeypatch.setattr(notify, "urlopen", fake)
        n = WebhookNotifier("https://example.com/hook")
        assert n.send(Notification(title="t", message="m")) is True
        assert len(fake.calls) == 3

    def test_send_transient_exception_exhausted(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake = FakeUrlopen([ConnectionResetError, ConnectionResetError, ConnectionResetError])
        monkeypatch.setattr(notify, "Request", FakeRequest)
        monkeypatch.setattr(notify, "urlopen", fake)
        n = WebhookNotifier("https://example.com/hook")
        assert n.send(Notification(title="t", message="m")) is False
        assert len(fake.calls) == 3

    def test_send_hard_error_no_retry(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake = FakeUrlopen([ValueError])
        monkeypatch.setattr(notify, "Request", FakeRequest)
        monkeypatch.setattr(notify, "urlopen", fake)
        n = WebhookNotifier("https://example.com/hook")
        assert n.send(Notification(title="t", message="m")) is False
        assert len(fake.calls) == 1

    def test_send_ssrf_blocked(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(socket, "getaddrinfo", lambda host, port=None: _PRIVATE_ADDRS)
        n = WebhookNotifier("http://internal/hook")
        assert n.send(Notification(title="t", message="m")) is False


class TestSlackNotifier:
    def _send(self, monkeypatch: pytest.MonkeyPatch, outcomes: list[int | type[Exception]]) -> tuple[bool, FakeUrlopen]:
        fake = FakeUrlopen(outcomes)
        monkeypatch.setattr(notify, "Request", FakeRequest)
        monkeypatch.setattr(notify, "urlopen", fake)
        n = SlackNotifier("https://hooks.slack.com/services/xxx")
        ok = n.send(Notification(title="t", message="m", severity="warning", fields=[("k", "v")]))
        return ok, fake

    def test_send_ok_payload(self, monkeypatch: pytest.MonkeyPatch) -> None:
        ok, fake = self._send(monkeypatch, [200])
        assert ok is True
        payload = json.loads(fake.calls[0][0].data)
        att = payload["attachments"][0]
        assert att["color"] == "#FF9800"
        assert att["title"] == "t"
        assert att["text"] == "m"
        assert att["fields"] == [{"title": "k", "value": "v", "short": True}]
        assert att["footer"] == "Knowledge Engine"

    def test_send_ok_default_color(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake = FakeUrlopen([200])
        monkeypatch.setattr(notify, "Request", FakeRequest)
        monkeypatch.setattr(notify, "urlopen", fake)
        n = SlackNotifier("https://hooks.slack.com/services/xxx")
        assert n.send(Notification(title="t", message="m", severity="debug")) is True
        payload = json.loads(fake.calls[0][0].data)
        assert payload["attachments"][0]["color"] == "#2196F3"

    def test_send_http_fail(self, monkeypatch: pytest.MonkeyPatch) -> None:
        ok, fake = self._send(monkeypatch, [500])
        assert ok is False
        assert len(fake.calls) == 1

    def test_send_exception(self, monkeypatch: pytest.MonkeyPatch) -> None:
        ok, fake = self._send(monkeypatch, [TimeoutError])
        assert ok is False
        assert len(fake.calls) == 1

    def test_send_ssrf_blocked(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(socket, "getaddrinfo", lambda host, port=None: _PRIVATE_ADDRS)
        monkeypatch.setattr(notify, "Request", FakeRequest)
        monkeypatch.setattr(notify, "urlopen", FakeUrlopen([200]))
        n = SlackNotifier("http://internal/hook")
        assert n.send(Notification(title="t", message="m")) is False


class TestEmailNotifier:
    def test_not_configured(self) -> None:
        n = EmailNotifier()
        assert n.configured is False
        assert n.send(Notification(title="t", message="m")) is False

    def test_send_ok_with_login(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("URA_SMTP_HOST", "smtp.example.com")
        monkeypatch.setenv("URA_SMTP_PORT", "465")
        monkeypatch.setenv("URA_SMTP_USER", "bot")
        monkeypatch.setenv("URA_EMAIL_FROM", "ura@example.com")
        monkeypatch.setenv("URA_EMAIL_TO", "ramon@example.com")
        monkeypatch.setattr(notify, "get_secret", lambda name, default="": "pw123")
        monkeypatch.setattr(notify.ssl, "create_default_context", lambda: None)
        instances: list[FakeSMTP] = []

        class TrackingSMTP(FakeSMTP):
            def __init__(self, host: str, port: int, timeout: int | None = None) -> None:
                super().__init__(host, port, timeout)
                instances.append(self)

        monkeypatch.setattr(notify.smtplib, "SMTP", TrackingSMTP)
        n = EmailNotifier()
        assert n.configured is True
        assert n.send(Notification(title="hi", message="body", fields=[("k", "v")])) is True
        server = instances[0]
        assert server.host == "smtp.example.com"
        assert server.port == 465
        assert server.tls_started is True
        assert server.login_called == ("bot", "pw123")
        assert len(server.sent_messages) == 1
        msg = server.sent_messages[0]
        assert msg["Subject"] == "[URA] hi"
        assert msg["From"] == "ura@example.com"
        assert msg["To"] == "ramon@example.com"

    def test_send_ok_without_user(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("URA_SMTP_HOST", "smtp.example.com")
        monkeypatch.setenv("URA_EMAIL_TO", "ramon@example.com")
        monkeypatch.setattr(notify.ssl, "create_default_context", lambda: None)
        instances: list[FakeSMTP] = []

        class TrackingSMTP(FakeSMTP):
            def __init__(self, host: str, port: int, timeout: int | None = None) -> None:
                super().__init__(host, port, timeout)
                instances.append(self)

        monkeypatch.setattr(notify.smtplib, "SMTP", TrackingSMTP)
        n = EmailNotifier()
        assert n.send(Notification(title="hi", message="body")) is True
        assert instances[0].port == 587
        assert instances[0].login_called is None

    def test_send_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("URA_SMTP_HOST", "smtp.example.com")
        monkeypatch.setenv("URA_EMAIL_TO", "ramon@example.com")
        monkeypatch.setattr(notify.ssl, "create_default_context", lambda: None)
        monkeypatch.setattr(notify.smtplib, "SMTP", FailingSMTP)
        n = EmailNotifier()
        assert n.send(Notification(title="hi", message="body")) is False

    def test_send_failure_unconfigured_never_touches_smtp(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: list[tuple[str, int]] = []

        def fake_smtp(host: str, port: int, timeout: int | None = None) -> FailingSMTP:
            calls.append((host, port))
            return FailingSMTP(host, port, timeout)

        monkeypatch.setattr(notify.smtplib, "SMTP", fake_smtp)
        n = EmailNotifier()
        assert n.send(Notification(title="hi", message="body")) is False
        assert calls == []


class TestNotificationService:
    def test_send_empty(self) -> None:
        svc = NotificationService()
        assert svc.send(Notification(title="t", message="m")) == 0

    def test_send_mixed_results(self) -> None:
        svc = NotificationService(max_workers=2)
        svc.add_notifier(FakeNotifier(result=True))
        svc.add_notifier(FakeNotifier(result=False))
        svc.add_notifier(FakeNotifier(result=True))
        assert svc.notifier_count == 3
        assert svc.send(Notification(title="t", message="m")) == 2

    def test_send_exception_ignored(self) -> None:
        svc = NotificationService()
        svc.add_notifier(FakeNotifier(exc=RuntimeError))
        svc.add_notifier(FakeNotifier(result=True))
        assert svc.send(Notification(title="t", message="m")) == 1


class TestSingleton:
    def test_set_and_get(self) -> None:
        svc = NotificationService()
        set_notifier(svc)
        assert get_notifier() is svc

    def test_create_without_email(self) -> None:
        svc = get_notifier()
        assert isinstance(svc, NotificationService)
        assert svc.notifier_count == 0

    def test_create_with_email(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("URA_SMTP_HOST", "smtp.example.com")
        monkeypatch.setenv("URA_EMAIL_TO", "ramon@example.com")
        svc = get_notifier()
        assert svc.notifier_count == 1


class TestSSRFError:
    def test_is_value_error(self) -> None:
        assert issubclass(SSRFError, ValueError)
        exc = SSRFError("URL apunta a red privada")
        assert str(exc) == "URL apunta a red privada"
