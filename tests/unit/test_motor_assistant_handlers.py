"""Tests de motor/assistant/api/handlers.py — lógica de negocio del chat API."""

from __future__ import annotations

from types import SimpleNamespace
from unittest import mock

import pytest

from motor.assistant.api.handlers import (
    _add_context_sections,
    _build_system_prompt,
    _detect_tool_name,
    _EngineHolder,
    _enrich_prompt,
    _execute_command,
    _format_git_status,
    _get_conversation_summary,
    _hours_since_last_message,
    _process,
    get_engine,
    get_llm,
)
from motor.assistant.models import ConversationMode, UserIntent


def _conv(messages: list | None = None, state: object | None = None) -> SimpleNamespace:
    return SimpleNamespace(messages=messages or [], state=state)


def _msg(content: str, timestamp: str = "") -> SimpleNamespace:
    return SimpleNamespace(content=content, timestamp=timestamp)


class TestHoursSinceLastMessage:
    def test_vacio(self) -> None:
        assert _hours_since_last_message(None) == 0
        assert _hours_since_last_message(_conv([])) == 0

    def test_sin_timestamp(self) -> None:
        assert _hours_since_last_message(_conv([_msg("hola", "")])) == 0

    def test_hace_horas(self) -> None:
        from datetime import UTC, datetime, timedelta

        ts = (datetime.now(UTC) - timedelta(hours=5)).isoformat()
        h = _hours_since_last_message(_conv([_msg("hola", ts)]))
        assert 4.5 < h < 5.5

    def test_timestamp_naive(self) -> None:
        from datetime import UTC, datetime, timedelta

        ts = (datetime.now(UTC) - timedelta(hours=2)).isoformat().replace("+00:00", "")
        h = _hours_since_last_message(_conv([_msg("hola", ts)]))
        assert 1.5 < h < 2.5

    def test_timestamp_invalido(self) -> None:
        h = _hours_since_last_message(_conv([_msg("hola", "no-es-fecha")]))
        assert h == 0


class TestGetConversationSummary:
    def test_vacio(self) -> None:
        assert _get_conversation_summary(None) == ""
        assert _get_conversation_summary(_conv([])) == ""

    def test_temas(self) -> None:
        conv = _conv([_msg("me gusta el aprendizaje profundo"), _msg("y las redes neuronales")])
        out = _get_conversation_summary(conv)
        assert out.startswith("Se hablaba de:")

    def test_solo_palabras_cortas(self) -> None:
        conv = _conv([_msg("hola que tal")])
        assert _get_conversation_summary(conv) == ""


class TestAddContextSections:
    def _base(self) -> str:
        return "BASE"

    def test_sentiment_es(self) -> None:
        out = _add_context_sections(self._base(), {"sentiment_action": "disculparse", "sentiment": "frustrado"}, "es")
        assert "frustrado" in out and "disculparse" in out

    def test_sentiment_en(self) -> None:
        out = _add_context_sections(self._base(), {"sentiment_action": "apologize", "sentiment": "frustrated"}, "en")
        assert "frustrated" in out and "apologize" in out

    def test_contextos(self) -> None:
        analysis = {
            "interruption_context": "interrumpido",
            "episodic_context": "episodios",
            "rag_context": "docs",
            "semantic_context": "semantica",
        }
        out = _add_context_sections(self._base(), analysis, "es")
        assert "interrumpido" in out and "episodios" in out and "docs" in out and "semantica" in out

    def test_sin_contexto(self) -> None:
        out = _add_context_sections(self._base(), {}, "es")
        assert out.endswith("sugiere 1 pregunta de seguimiento breve.")


class TestBuildSystemPrompt:
    def test_modo_desconocido(self) -> None:
        out = _build_system_prompt("raro", {}, "es")
        assert "URA" in out

    def test_lang_no_disponible(self) -> None:
        out = _build_system_prompt("trabajo", {}, "fr")
        assert "URA" in out  # fallback a es

    def test_user_intent_str(self) -> None:
        out = _build_system_prompt("conversacion", {"intent": "PROFESIONAL"}, "es")
        assert "URA" in out

    def test_language_changed(self) -> None:
        out = _build_system_prompt("conversacion", {"language_changed": True, "language": "en"}, "es")
        assert "cambió de idioma" in out

    def test_conv_retorno(self) -> None:
        from datetime import UTC, datetime, timedelta

        conv = _conv(
            [_msg("hola"), _msg("temas interesantes", (datetime.now(UTC) - timedelta(hours=3)).isoformat())],
            state=SimpleNamespace(turn_count=2),
        )
        out = _build_system_prompt("conversacion", {"_conv": conv}, "es")
        assert "vuelve tras 3h" in out

    def test_correcciones(self) -> None:
        out = _build_system_prompt("conversacion", {"relevant_corrections": 2}, "es")
        assert "corregido información" in out

    def test_user_id_prefs_short(self) -> None:
        with mock.patch(
            "motor.assistant.preferences.UserPreferenceLearning.get_preferences",
            return_value={"preferred_length": "short"},
        ):
            out = _build_system_prompt("conversacion", {"user_id": "u1"}, "es")
        assert "breve" in out

    def test_user_id_prefs_long(self) -> None:
        with mock.patch(
            "motor.assistant.preferences.UserPreferenceLearning.get_preferences",
            return_value={"preferred_length": "long"},
        ):
            out = _build_system_prompt("conversacion", {"user_id": "u1"}, "es")
        assert "extenderte" in out

    def test_proactive_suggestion(self) -> None:
        out = _build_system_prompt("conversacion", {"proactive_suggestion": "sugerencia"}, "es")
        assert "sugerencia" in out

    def test_adjustments(self) -> None:
        out = _build_system_prompt(
            "conversacion",
            {"response_adjustments": {"apologize": True, "shorten": True, "clarify": True}},
            "es",
        )
        assert "frustrado" in out and "muy breve" in out and "aclaración" in out


class TestDetectToolName:
    @pytest.fixture(autouse=True)
    def _plugins(self) -> None:
        import motor.assistant.api.handlers as h

        self._orig = h._tool_manager._plugins
        h._tool_manager._plugins = {}

    @pytest.fixture(autouse=True)
    def _restore(self) -> None:
        yield
        import motor.assistant.api.handlers as h

        h._tool_manager._plugins = self._orig

    def test_known(self) -> None:
        assert _detect_tool_name("muéstrame el status") == "git_status"
        assert _detect_tool_name("ejecuta python") == "python"
        assert _detect_tool_name("cuánto es 2+2") == "calculator"
        assert _detect_tool_name("weather hoy") == "weather"

    def test_plugin(self) -> None:
        import motor.assistant.api.handlers as h

        h._tool_manager._plugins = {"mi_plugin": SimpleNamespace(keywords=["sueldo"])}
        assert _detect_tool_name("cómo va el sueldo") == "mi_plugin"

    def test_none(self) -> None:
        assert _detect_tool_name("hola que tal") is None


class TestFormatGitStatus:
    def test_vacio(self) -> None:
        assert _format_git_status("") == ""
        assert _format_git_status("   ") == "   "  # raw sin partes -> se devuelve

    def test_lineas(self) -> None:
        raw = "M  a.py\n M b.py\nA  c.py\n?? d.txt\nD  e.py\nR  f.py\nlibre"
        out = _format_git_status(raw)
        assert "MODIFICADO (sin commit): a.py" in out
        assert "MODIFICADO (sin commit): b.py" in out  # strip quita el espacio inicial
        assert "AÑADIDO (staged): c.py" in out
        assert "SIN RASTREAR (untracked): d.txt" in out
        assert "ELIMINADO: e.py" in out
        assert "RENOMBRADO: f.py" in out
        assert "libre" in out

    def test_lineas_vacias(self) -> None:
        assert _format_git_status("M  a.py\n\n  \nM  b.py") == "MODIFICADO (sin commit): a.py\nMODIFICADO (sin commit): b.py"

    def test_raw_unicamente(self) -> None:
        assert _format_git_status("xyz") == "xyz"


class TestExecuteCommand:
    async def test_sin_tool(self) -> None:
        assert await _execute_command("hola", {}) == ""

    async def test_git_status_formateado(self) -> None:
        import motor.assistant.api.handlers as h

        with mock.patch.object(
            h._tool_manager, "execute", mock.AsyncMock(return_value=SimpleNamespace(success=True, output="M  x.py"))
        ):
            out = await _execute_command("status", {})
        assert "MODIFICADO" in out

    async def test_output_error(self) -> None:
        import motor.assistant.api.handlers as h

        with mock.patch.object(
            h._tool_manager, "execute", mock.AsyncMock(return_value=SimpleNamespace(success=False, error="boom"))
        ):
            out = await _execute_command("python", {})
        assert out == "boom"


class TestEnrichPrompt:
    @pytest.fixture
    def engine(self) -> mock.MagicMock:
        eng = mock.MagicMock()
        eng._web.search = mock.AsyncMock(return_value="resultado web")
        eng._rag.is_available = mock.Mock(return_value=True)
        eng._rag.retrieve = mock.AsyncMock(return_value="contexto rag")
        return eng

    async def test_needs_web(self, engine: mock.MagicMock) -> None:
        with mock.patch("motor.assistant.api.handlers.get_assistant_health"):
            out = await _enrich_prompt("PROMPT", {"needs_web_search": True}, engine, "query")
        assert "resultado web" in out

    async def test_web_error(self, engine: mock.MagicMock) -> None:
        engine._web.search = mock.AsyncMock(side_effect=OSError("web down"))
        engine._rag.is_available = mock.Mock(return_value=False)
        with mock.patch("motor.assistant.api.handlers.get_assistant_health"):
            out = await _enrich_prompt("PROMPT", {"needs_web_search": True}, engine, "q")
        assert out == "PROMPT"

    async def test_rag_disponible(self, engine: mock.MagicMock) -> None:
        health = mock.MagicMock()
        with mock.patch("motor.assistant.api.handlers.get_assistant_health", return_value=health):
            out = await _enrich_prompt("PROMPT", {}, engine, "q")
        assert "contexto rag" in out
        health.set_healthy.assert_called_with("rag", "available")

    async def test_rag_sin_ctx(self, engine: mock.MagicMock) -> None:
        engine._rag.retrieve = mock.AsyncMock(return_value="")
        with mock.patch("motor.assistant.api.handlers.get_assistant_health"):
            out = await _enrich_prompt("PROMPT", {}, engine, "q")
        assert out == "PROMPT"

    async def test_rag_no_disponible(self, engine: mock.MagicMock) -> None:
        engine._rag.is_available = mock.Mock(return_value=False)
        health = mock.MagicMock()
        with mock.patch("motor.assistant.api.handlers.get_assistant_health", return_value=health):
            out = await _enrich_prompt("PROMPT", {}, engine, "q")
        assert out == "PROMPT"
        health.set_degraded.assert_called_with("rag", "not available")

    async def test_rag_error(self, engine: mock.MagicMock) -> None:
        engine._rag.is_available = mock.Mock(side_effect=OSError("rag down"))
        health = mock.MagicMock()
        with mock.patch("motor.assistant.api.handlers.get_assistant_health", return_value=health):
            out = await _enrich_prompt("PROMPT", {}, engine, "q")
        assert out == "PROMPT"
        health.set_unhealthy.assert_called_with("rag", "error")


class TestGetEngine:
    def test_lazy_init(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(_EngineHolder, "engine", None)
        with mock.patch("motor.assistant.api.handlers.ConversationEngine") as m_ce, mock.patch(
            "motor.assistant.api.handlers.init_assistant_health"
        ) as m_init, mock.patch(
            "motor.assistant.api.handlers.get_assistant_health", return_value=mock.MagicMock()
        ) as m_health:
            engine = get_engine()
        m_ce.assert_called_once()
        m_init.assert_called_once()
        m_health.return_value.set_healthy.assert_called_with("memory", "loaded")
        assert engine is not None
        monkeypatch.setattr(_EngineHolder, "engine", None)

    def test_cached(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake = mock.MagicMock()
        monkeypatch.setattr(_EngineHolder, "engine", fake)
        assert get_engine() is fake


class TestGetLlm:
    def test_con_router(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(_EngineHolder, "llm", None)
        monkeypatch.setattr(_EngineHolder, "engine", mock.MagicMock())
        with mock.patch("motor.core.llm.router.LLMRouter") as m_router, mock.patch(
            "motor.assistant.api.handlers.LLMBridge"
        ) as m_bridge, mock.patch(
            "motor.assistant.api.handlers.get_assistant_health", return_value=mock.MagicMock()
        ) as m_health:
            llm = get_llm()
        m_bridge.assert_called_once()
        assert m_bridge.call_args.kwargs["router"] is m_router.return_value
        m_health.return_value.set_healthy.assert_called_with("llm", "loaded")
        assert llm is not None
        monkeypatch.setattr(_EngineHolder, "llm", None)

    def test_sin_router(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(_EngineHolder, "llm", None)
        monkeypatch.setattr(_EngineHolder, "engine", mock.MagicMock())
        with mock.patch(
            "motor.core.llm.router.LLMRouter", side_effect=ImportError("no router")
        ), mock.patch("motor.assistant.api.handlers.LLMBridge") as m_bridge, mock.patch(
            "motor.assistant.api.handlers.get_assistant_health", return_value=mock.MagicMock()
        ):
            llm = get_llm()
        assert "router" not in m_bridge.call_args.kwargs
        assert llm is not None
        monkeypatch.setattr(_EngineHolder, "llm", None)


class TestProcess:
    @pytest.fixture
    def engine(self) -> mock.MagicMock:
        eng = mock.MagicMock()
        conv = mock.MagicMock()
        conv.state.turn_count = 0
        eng.get_or_create.return_value = conv
        eng.process_user_message.return_value = {
            "intent": UserIntent.CHAT,
            "mode": ConversationMode.CONVERSATION,
            "resolved_message": "mensaje resuelto",
            "language": "es",
        }
        return eng

    def test_ok(self, engine: mock.MagicMock) -> None:
        intent, mode, resolved, _prompt, conv, lang, analysis = _process(engine, None, "c1", "hola", "")
        assert intent == UserIntent.CHAT
        assert mode == ConversationMode.CONVERSATION
        assert resolved == "mensaje resuelto"
        assert lang == "es"
        assert analysis["_conv"] is conv
        engine.add_message.assert_called_with("c1", "user", "mensaje resuelto")

    def test_con_user_id(self, engine: mock.MagicMock) -> None:
        _process(engine, None, "c1", "hola", "", user_id="u7")
        assert True
        analysis = engine.process_user_message.return_value
        assert analysis["user_id"] == "u7"

    def test_modo_valido(self, engine: mock.MagicMock) -> None:
        _process(engine, None, "c1", "hola", "trabajo")
        conv = engine.get_or_create.return_value
        conv.state.mode = ConversationMode.WORK
        assert conv.state.mode == ConversationMode.WORK

    def test_modo_invalido(self, engine: mock.MagicMock) -> None:
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc:
            _process(engine, None, "c1", "hola", "no_existe")
        assert exc.value.status_code == 400
