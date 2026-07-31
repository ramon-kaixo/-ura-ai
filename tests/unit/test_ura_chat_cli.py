"""Unit tests para ura_chat.py — CLI interactivo del asistente."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

if TYPE_CHECKING:
    import pytest


class TestChatLoop:
    def test_quit_breaks_loop(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        import ura_chat

        post_mock = MagicMock()
        monkeypatch.setattr(ura_chat.httpx, "post", post_mock)
        monkeypatch.setattr("builtins.input", lambda _prompt: ":q")
        ura_chat.chat_loop()
        post_mock.assert_not_called()
        out = capsys.readouterr().out
        assert "¡Hasta luego!" in out

    def test_eof_breaks_loop(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        import ura_chat

        monkeypatch.setattr(ura_chat.httpx, "post", MagicMock())

        def raise_eof(_prompt: str) -> str:
            raise EOFError

        monkeypatch.setattr("builtins.input", raise_eof)
        ura_chat.chat_loop()
        assert "¡Hasta luego!" in capsys.readouterr().out

    def test_keyboard_interrupt_breaks(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import ura_chat

        monkeypatch.setattr(ura_chat.httpx, "post", MagicMock())

        def raise_ki(_prompt: str) -> str:
            raise KeyboardInterrupt

        monkeypatch.setattr("builtins.input", raise_ki)
        ura_chat.chat_loop()

    def test_mode_switch(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        import ura_chat

        monkeypatch.setattr(ura_chat.httpx, "post", MagicMock())
        inputs = iter([":m tecnico", ":q"])
        monkeypatch.setattr("builtins.input", lambda _prompt: next(inputs))
        ura_chat.chat_loop()
        assert "Modo cambiado a: tecnico" in capsys.readouterr().out

    def test_empty_message_skips_http(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import ura_chat

        post_mock = MagicMock()
        monkeypatch.setattr(ura_chat.httpx, "post", post_mock)
        inputs = iter(["", ":q"])
        monkeypatch.setattr("builtins.input", lambda _prompt: next(inputs))
        ura_chat.chat_loop()
        post_mock.assert_not_called()

    def test_post_success_updates_cid_and_prints_reply(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        import ura_chat

        seen: list[dict] = []

        def fake_post(url: str, json: dict, timeout: float) -> MagicMock:
            assert url == "http://localhost:8003/api/v1/chat"
            assert json["message"] in ("hola", "adiós")
            assert json["mode"] == "conversacion"
            assert json["stream"] is False
            seen.append(json)
            response = MagicMock()
            response.status_code = 200
            response.json.return_value = {
                "conversation_id": "abc-123",
                "intent": "question",
                "reply": "respuesta",
            }
            return response

        monkeypatch.setattr(ura_chat.httpx, "post", fake_post)
        inputs = iter(["hola", "adiós", ":q"])
        monkeypatch.setattr("builtins.input", lambda _prompt: next(inputs))
        ura_chat.chat_loop()
        out = capsys.readouterr().out
        assert "respuesta" in out
        assert seen[0]["conversation_id"] == ""
        assert seen[1]["conversation_id"] == "abc-123"

    def test_post_error_prints_error(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        import ura_chat

        response = MagicMock()
        response.status_code = 500
        response.text = "boom"

        monkeypatch.setattr(ura_chat.httpx, "post", lambda *a, **k: response)
        inputs = iter(["hola", ":q"])
        monkeypatch.setattr("builtins.input", lambda _prompt: next(inputs))
        ura_chat.chat_loop()
        out = capsys.readouterr().out
        assert "Error: 500" in out
