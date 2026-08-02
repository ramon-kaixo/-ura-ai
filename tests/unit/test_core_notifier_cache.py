"""Tests para core/notifier.py y core/secretario_cache.py."""
from __future__ import annotations

import json
from unittest import mock

import pytest

from core import notifier
from core.secretario_cache import LRU_MAX, SecretarioCache


class FakeResp:
    def __init__(self, status_code=200, body=b"{}"):
        self.status_code = status_code
        self._body = body

    def read(self):
        return self._body


class FakeUrlopenCtx:
    def __init__(self, resp: FakeResp):
        self._resp = resp

    def __enter__(self):
        return self._resp

    def __exit__(self, *a):
        return False


@pytest.fixture(autouse=True)
def _reset_secrets():
    notifier._TELEGRAM_TOKEN = None
    notifier._TELEGRAM_CHAT_ID = None
    notifier._PUSHOVER_USER = ""
    notifier._PUSHOVER_TOKEN = ""
    yield
    notifier._TELEGRAM_TOKEN = None
    notifier._TELEGRAM_CHAT_ID = None
    notifier._PUSHOVER_USER = ""
    notifier._PUSHOVER_TOKEN = ""


class TestNotifierSecrets:
    def test_ensure_con_store(self) -> None:
        store = mock.Mock()
        store.get_secret.side_effect = lambda k, d="": {"TELEGRAM_TOKEN": "tok", "TELEGRAM_CHAT_ID": "123", "PUSHOVER_USER_KEY": "u", "PUSHOVER_APP_TOKEN": "a"}.get(k, "")
        notifier._ensure_secrets(store)
        assert notifier._TELEGRAM_TOKEN == "tok"
        assert notifier._TELEGRAM_CHAT_ID == "123"

    def test_ensure_sin_store(self, monkeypatch) -> None:
        getter = mock.Mock(side_effect=lambda k, d="": {"TELEGRAM_TOKEN": "t", "TELEGRAM_CHAT_ID": "c", "PUSHOVER_USER_KEY": "u", "PUSHOVER_APP_TOKEN": "p"}.get(k, ""))
        monkeypatch.setattr("motor.core.secrets.get_secret", getter)
        notifier._ensure_secrets(None)
        assert notifier._TELEGRAM_TOKEN == "t"

    def test_ensure_no_reinicializa(self) -> None:
        notifier._TELEGRAM_TOKEN = "ya"
        notifier._ensure_secrets(mock.Mock())
        assert notifier._TELEGRAM_TOKEN == "ya"


class TestNotifierEnvio:
    def test_telegram_no_configurado(self) -> None:
        assert notifier._send_telegram("msg") is False

    def test_telegram_ok(self, monkeypatch) -> None:
        notifier._TELEGRAM_TOKEN = "tok"  # noqa: S105
        notifier._TELEGRAM_CHAT_ID = "123"  # noqa: S105
        resp = FakeResp(status_code=200)
        post = mock.Mock(return_value=resp)
        monkeypatch.setattr(notifier.httpx, "post", post)
        assert notifier._send_telegram("hola") is True
        args = post.call_args
        assert args.args[0] == "https://api.telegram.org/bottok/sendMessage"
        assert args.kwargs["json"]["chat_id"] == "123"
        assert args.kwargs["json"]["text"] == "hola"

    def test_telegram_http_error(self, monkeypatch) -> None:
        notifier._TELEGRAM_TOKEN = "tok"  # noqa: S105
        notifier._TELEGRAM_CHAT_ID = "123"  # noqa: S105
        monkeypatch.setattr(notifier.httpx, "post", mock.Mock(return_value=FakeResp(status_code=500)))
        assert notifier._send_telegram("m") is False

    def test_telegram_excepcion(self, monkeypatch) -> None:
        notifier._TELEGRAM_TOKEN = "tok"  # noqa: S105
        notifier._TELEGRAM_CHAT_ID = "123"  # noqa: S105
        monkeypatch.setattr(notifier.httpx, "post", mock.Mock(side_effect=OSError("net")))
        assert notifier._send_telegram("m") is False

    def test_pushover_no_configurado(self) -> None:
        assert notifier._send_pushover("m") is False

    def test_pushover_ok(self, monkeypatch) -> None:
        notifier._PUSHOVER_USER = "u"  # noqa: S105
        notifier._PUSHOVER_TOKEN = "t"  # noqa: S105
        post = mock.Mock(return_value=FakeResp(status_code=200))
        monkeypatch.setattr(notifier.httpx, "post", post)
        assert notifier._send_pushover("hola") is True
        assert post.call_args.kwargs["json"]["user"] == "u"

    def test_pushover_error(self, monkeypatch) -> None:
        notifier._PUSHOVER_USER = "u"  # noqa: S105
        notifier._PUSHOVER_TOKEN = "t"  # noqa: S105
        monkeypatch.setattr(notifier.httpx, "post", mock.Mock(side_effect=OSError("net")))
        assert notifier._send_pushover("m") is False

    def test_notify_channels_default_sin_credenciales(self, monkeypatch) -> None:
        notifier._TELEGRAM_TOKEN = ""  # noqa: S105
        notifier._TELEGRAM_CHAT_ID = ""  # noqa: S105
        assert notifier.notify("m") is False

    def test_notify_levels(self, monkeypatch) -> None:
        notifier._TELEGRAM_TOKEN = "t"  # noqa: S105
        notifier._TELEGRAM_CHAT_ID = "c"  # noqa: S105
        post = mock.Mock(return_value=FakeResp(status_code=200))
        monkeypatch.setattr(notifier.httpx, "post", post)
        assert notifier.notify("m", level="critical") is True
        assert "🚨" in post.call_args.kwargs["json"]["text"]
        assert "CRITICAL" in post.call_args.kwargs["json"]["text"]

    def test_notify_channel_especifico(self, monkeypatch) -> None:
        notifier._TELEGRAM_TOKEN = "t"  # noqa: S105
        notifier._TELEGRAM_CHAT_ID = "c"  # noqa: S105
        post = mock.Mock(return_value=FakeResp(status_code=200))
        monkeypatch.setattr(notifier.httpx, "post", post)
        assert notifier.notify("m", channels=["telegram"]) is True
        post.assert_called_once()


class TestSecretarioCache:
    def test_interact_cachea(self, monkeypatch) -> None:
        sc = SecretarioCache()
        resp = FakeResp(body=json.dumps({"ok": True}).encode())
        urlopen = mock.Mock(return_value=FakeUrlopenCtx(resp))
        monkeypatch.setattr(notifier.urllib, "urlopen", urlopen) if False else None

        monkeypatch.setattr("core.secretario_cache.urllib.request.urlopen", urlopen)
        r1 = sc.interact("hola")
        r2 = sc.interact("hola")
        assert r1 == {"ok": True}
        assert r2 == {"ok": True}
        assert urlopen.call_count == 1  # segunda vez desde cache

    def test_interact_error(self, monkeypatch) -> None:
        sc = SecretarioCache()
        monkeypatch.setattr("core.secretario_cache.urllib.request.urlopen", mock.Mock(side_effect=OSError("net")))
        r = sc.interact("hola")
        assert r["validation"]["ok"] is False
        assert "error" in r

    def test_interact_structure_default(self, monkeypatch) -> None:
        sc = SecretarioCache()
        resp = FakeResp(body=b"{}")
        monkeypatch.setattr("core.secretario_cache.urllib.request.urlopen", mock.Mock(return_value=FakeUrlopenCtx(resp)))
        sc.interact("hola")
        # no debe explotar; cache contiene el resultado
        assert sc.estado()["cache_size"] == 1

    def test_put_cache_lru_eviction(self) -> None:
        sc = SecretarioCache()
        for i in range(LRU_MAX + 5):
            sc._put_cache(f"k{i}", {"i": i})
        assert len(sc._cache) == LRU_MAX
        assert "k0" not in sc._cache

    def test_limpiar_cache(self) -> None:
        sc = SecretarioCache()
        sc._put_cache("k", {"v": 1})
        sc.limpiar_cache()
        assert sc.estado()["cache_size"] == 0

    def test_estado(self, monkeypatch) -> None:
        monkeypatch.setattr("core.secretario_cache.ASUS_EXEC_URL", "http://x:1")
        sc = SecretarioCache()
        st = sc.estado()
        assert st["cache_max"] == LRU_MAX
        assert st["asus_url"] == "http://x:1"

    def test_buscar_qdrant_ok(self, monkeypatch) -> None:
        sc = SecretarioCache()
        body = json.dumps({"result": {"points": [{"payload": {"idea": "a"}}, {"payload": {"idea": "b"}}]}}).encode()
        monkeypatch.setattr("core.secretario_cache.urllib.request.urlopen", mock.Mock(return_value=FakeUrlopenCtx(FakeResp(body=body))))
        out = sc.buscar_qdrant("ideas")
        assert len(out) == 2
        assert out[0]["idea"] == "a"

    def test_buscar_qdrant_error(self, monkeypatch) -> None:
        sc = SecretarioCache()
        monkeypatch.setattr("core.secretario_cache.urllib.request.urlopen", mock.Mock(side_effect=OSError("net")))
        out = sc.buscar_qdrant("ideas")
        assert out == [{"error": mock.ANY}] or "error" in out[0]
