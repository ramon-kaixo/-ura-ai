"""Tests para ura_chat.py — CLI interactivo."""

import builtins
from unittest.mock import patch


class TestUraChatCli:
    def test_chat_quit_command(self, capsys):
        from ura_chat import chat_loop

        with patch.object(builtins, "input", side_effect=[":q"]):
            chat_loop()
            captured = capsys.readouterr()
            assert "Hasta luego" in captured.out

    def test_chat_eof_terminates(self, capsys):
        from ura_chat import chat_loop

        with patch.object(builtins, "input", side_effect=EOFError()):
            chat_loop()
            captured = capsys.readouterr()
            assert "Hasta luego" in captured.out

    def test_chat_empty_input_skipped(self):
        from ura_chat import chat_loop

        with patch.object(builtins, "input", side_effect=["", ":q"]), patch("ura_chat.httpx.post") as mock_post:
            chat_loop()
            mock_post.assert_not_called()

    def test_chat_mode_change(self, capsys):
        from ura_chat import chat_loop

        with patch.object(builtins, "input", side_effect=[":m test", ":q"]):
            chat_loop()
            captured = capsys.readouterr()
            assert "Modo cambiado a: test" in captured.out

    def test_chat_post_success(self, capsys):
        from ura_chat import chat_loop

        mock_resp = type(
            "Resp",
            (),
            {
                "status_code": 200,
                "json": lambda self: {
                    "conversation_id": "c1",
                    "intent": "question",
                    "reply": "respuesta test",
                },
                "text": "ok",
            },
        )()

        with patch.object(builtins, "input", side_effect=["hola", ":q"]):
            with patch("ura_chat.httpx.post", return_value=mock_resp) as mock_post:
                chat_loop()
                captured = capsys.readouterr()
                assert "respuesta test" in captured.out
                mock_post.assert_called_once()

    def test_chat_post_error(self, capsys):
        from ura_chat import chat_loop

        mock_resp = type(
            "Resp",
            (),
            {"status_code": 500, "text": "server error"},
        )()

        with patch.object(builtins, "input", side_effect=["hola", ":q"]):
            with patch("ura_chat.httpx.post", return_value=mock_resp):
                chat_loop()
                captured = capsys.readouterr()
                assert "Error: 500" in captured.out
