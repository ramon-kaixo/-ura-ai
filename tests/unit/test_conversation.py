"""Tests para ConversationEngine (deps inyectadas, MessageStore real SQLite)."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, PropertyMock

import pytest

from motor.assistant.conversation import ConversationEngine
from motor.assistant.message_store import MessageStore
from motor.assistant.models import (
    ConversationMode,
    Message,
    MessageRole,
    UserIntent,
)
from motor.assistant.sentiment import Sentiment


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db_path(tmp_path: Path) -> str:
    return str(tmp_path / "test_conversations.db")


@pytest.fixture
def store(db_path: str) -> MessageStore:
    s = MessageStore(db_path=db_path)
    yield s
    try:
        s.close()
    except Exception:
        pass


@pytest.fixture
def mock_intent() -> MagicMock:
    m = MagicMock()
    m.classify.return_value.intent = UserIntent.CHAT
    return m


@pytest.fixture
def mock_auto_mode() -> MagicMock:
    m = MagicMock()
    m.detect_mode.return_value.mode = ConversationMode.CONVERSATION
    m.detect_mode.return_value.reason = "default"
    return m


@pytest.fixture
def mock_interruptions() -> MagicMock:
    m = MagicMock()
    m.detect_interruption.return_value = False
    m.auto_recover_context.return_value = ""
    return m


@pytest.fixture
def mock_episodic() -> MagicMock:
    m = MagicMock()
    m.get_relevant_context.return_value = ""
    return m


@pytest.fixture
def mock_trends() -> MagicMock:
    m = MagicMock()
    m.analyze_query.return_value = MagicMock(
        needs_update=False, reason="sin indicios",
    )
    return m


@pytest.fixture
def engine(
    store: MessageStore,
    mock_intent: MagicMock,
    mock_auto_mode: MagicMock,
    mock_interruptions: MagicMock,
    mock_episodic: MagicMock,
    mock_trends: MagicMock,
) -> ConversationEngine:
    return ConversationEngine(
        message_store=store,
        intent_engine=mock_intent,
        auto_mode=mock_auto_mode,
        interruption_system=mock_interruptions,
        episodic_memory=mock_episodic,
        trend_awareness=mock_trends,
        max_turns=5,
    )


# ---------------------------------------------------------------------------
# create_conversation
# ---------------------------------------------------------------------------

class TestCreateConversation:
    def test_without_id(self, engine: ConversationEngine) -> None:
        conv = engine.create_conversation()
        assert conv.conversation_id
        assert conv.state is not None
        assert conv.state.mode == ConversationMode.CONVERSATION

    def test_with_id_and_goal(self, engine: ConversationEngine) -> None:
        conv = engine.create_conversation(
            conversation_id="custom-1",
            mode=ConversationMode.WORK,
            goal="refactor modulo X",
        )
        assert conv.conversation_id == "custom-1"
        assert conv.state is not None
        assert conv.state.mode == ConversationMode.WORK
        assert conv.state.active_goal == "refactor modulo X"


# ---------------------------------------------------------------------------
# get_conversation
# ---------------------------------------------------------------------------

class TestGetConversation:
    def test_not_found(self, engine: ConversationEngine) -> None:
        assert engine.get_conversation("no-such") is None

    def test_from_cache(self, engine: ConversationEngine) -> None:
        engine.create_conversation(conversation_id="cached")
        conv = engine.get_conversation("cached")
        assert conv is not None
        assert conv.conversation_id == "cached"

    def test_from_store(self, engine: ConversationEngine, store: MessageStore) -> None:
        store.append("stored", Message(role="user", content="saved"))
        conv = engine.get_conversation("stored")
        assert conv is not None
        assert len(conv.messages) == 1
        assert conv.messages[0].content == "saved"


# ---------------------------------------------------------------------------
# add_message
# ---------------------------------------------------------------------------

class TestAddMessage:
    def test_adds_and_returns(self, engine: ConversationEngine) -> None:
        msg = engine.add_message("conv-a", "user", "test message")
        assert msg.role == "user"
        assert msg.content == "test message"

    def test_content_none_raises(self, engine: ConversationEngine) -> None:
        with pytest.raises(ValueError, match="content cannot be None"):
            engine.add_message("conv-b", "user", None)  # type: ignore[arg-type]

    def test_exceeds_max_turns(self, engine: ConversationEngine) -> None:
        engine.add_message("conv-c", "user", "msg1")
        engine.add_message("conv-c", "assistant", "r1")
        engine.add_message("conv-c", "user", "msg2")
        engine.add_message("conv-c", "assistant", "r2")
        engine.add_message("conv-c", "user", "msg3")
        with pytest.raises(RuntimeError, match="exceeded max turns"):
            engine.add_message("conv-c", "assistant", "r3")

    def test_stores_in_message_store(
        self, engine: ConversationEngine, store: MessageStore,
    ) -> None:
        engine.add_message("conv-d", "user", "persist me")
        msgs = store.get_conversation("conv-d")
        assert len(msgs) == 1
        assert msgs[0].content == "persist me"

    def test_content_empty_string_allowed(self, engine: ConversationEngine) -> None:
        msg = engine.add_message("conv-e", "user", "")
        assert msg.content == ""


# ---------------------------------------------------------------------------
# get_or_create
# ---------------------------------------------------------------------------

class TestGetOrCreate:
    def test_existing_in_cache(self, engine: ConversationEngine) -> None:
        engine.create_conversation(conversation_id="goc-cache")
        conv = engine.get_or_create("goc-cache")
        assert conv.conversation_id == "goc-cache"

    def test_existing_in_store(
        self, engine: ConversationEngine, store: MessageStore,
    ) -> None:
        store.append("goc-store", Message(role="user", content="from db"))
        conv = engine.get_or_create("goc-store")
        assert conv.conversation_id == "goc-store"
        assert len(conv.messages) == 1

    def test_new_conversation(self, engine: ConversationEngine) -> None:
        conv = engine.get_or_create("goc-new")
        assert conv.conversation_id == "goc-new"
        assert conv.messages == []


# ---------------------------------------------------------------------------
# detect_intent
# ---------------------------------------------------------------------------

class TestDetectIntent:
    def test_delegates_to_intent_engine(
        self, engine: ConversationEngine, mock_intent: MagicMock,
    ) -> None:
        mock_intent.classify.return_value.intent = UserIntent.QUESTION
        result = engine.detect_intent("what is X?")
        assert result == UserIntent.QUESTION
        mock_intent.classify.assert_called_once()


# ---------------------------------------------------------------------------
# resolve_reference
# ---------------------------------------------------------------------------

class TestResolveReference:
    def test_no_match(self, engine: ConversationEngine) -> None:
        result = engine.resolve_reference("nada que ver", "conv-ref")
        assert result == "nada que ver"

    def test_eso_replaced_with_context(
        self, engine: ConversationEngine,
    ) -> None:
        engine.add_message("conv-ref2", "user", "el código de la función X")
        result = engine.resolve_reference("hazlo de nuevo", "conv-ref2")
        assert "ejecuta" in result

    def test_el_anterior_replaced(
        self, engine: ConversationEngine,
    ) -> None:
        engine.add_message("conv-ref3", "user", "explica el concepto Y")
        result = engine.resolve_reference("eso", "conv-ref3")
        assert "explica" in result


# ---------------------------------------------------------------------------
# list_conversations
# ---------------------------------------------------------------------------

def test_list_conversations(engine: ConversationEngine) -> None:
    engine.add_message("l1", "user", "first")
    engine.add_message("l2", "user", "second")
    lst = engine.list_conversations()
    assert len(lst) >= 2


# ---------------------------------------------------------------------------
# delete_conversation
# ---------------------------------------------------------------------------

class TestDeleteConversation:
    def test_removes_from_cache_and_store(
        self, engine: ConversationEngine, store: MessageStore,
    ) -> None:
        engine.add_message("del-1", "user", "delete me")
        assert engine.delete_conversation("del-1") is True
        assert engine.get_conversation("del-1") is None
        assert store.get_conversation("del-1") == []

    def test_nonexistent(self, engine: ConversationEngine) -> None:
        assert engine.delete_conversation("no-such-del") is False


# ---------------------------------------------------------------------------
# process_user_message — coherent flow
# ---------------------------------------------------------------------------

class TestProcessUserMessage:
    def test_coherent_result_with_injected_deps(
        self, engine: ConversationEngine, mock_intent: MagicMock,
    ) -> None:
        mock_intent.classify.return_value.intent = UserIntent.GREETING
        result = engine.process_user_message("conv-pum", "Hola")
        assert result["intent"] == UserIntent.GREETING
        assert result["mode"] == ConversationMode.CONVERSATION
        assert isinstance(result["language"], str)
        assert isinstance(result["language_confidence"], float)
        assert isinstance(result["sentiment_score"], float)
        assert isinstance(result["resolved_message"], str)

    def test_interruption_detected(
        self, engine: ConversationEngine,
        mock_interruptions: MagicMock,
    ) -> None:
        mock_interruptions.detect_interruption.return_value = True
        mock_interruptions.auto_recover_context.return_value = "contexto anterior"
        result = engine.process_user_message("conv-int", "cambia de tema")
        assert result["is_interruption"] is True
        assert result["interruption_context"] == "contexto anterior"

    def test_sentiment_frustrated_triggers_apologize(
        self, engine: ConversationEngine,
    ) -> None:
        _original = engine._sentiment.detect
        engine._sentiment.detect = MagicMock(
            return_value=MagicMock(
                sentiment=Sentiment.FRUSTRATED,
                score=-0.5,
                suggested_action="disculparse",
            ),
        )
        result = engine.process_user_message("conv-frus", "esto no funciona!")
        adj = result["response_adjustments"]
        assert adj.get("apologize") is True

    def test_correction_intent(
        self, engine: ConversationEngine, mock_intent: MagicMock,
    ) -> None:
        mock_intent.classify.return_value.intent = UserIntent.CORRECT
        engine._corrections.record_correction = MagicMock(return_value=object())
        engine._corrections.get_relevant_corrections = MagicMock(return_value=["c1"])
        result = engine.process_user_message("conv-corr", "no es así, es al revés")
        assert result["correction_recorded"] is True
        assert result["relevant_corrections"] == 1

    def test_sanitizes_message(self, engine: ConversationEngine) -> None:
        engine._prompt_sanitizer.sanitize = MagicMock(return_value="limpio")
        result = engine.process_user_message("conv-san", "mensaje sucio")
        assert engine._prompt_sanitizer.sanitize.called

    def test_needs_web_search(
        self, engine: ConversationEngine, mock_trends: MagicMock,
    ) -> None:
        mock_trends.analyze_query.return_value = MagicMock(
            needs_update=True, reason="actualidad",
        )
        result = engine.process_user_message("conv-web", "últimas noticias")
        assert result["needs_web_search"] is True
        assert result["trend_reason"] == "actualidad"


# ---------------------------------------------------------------------------
# _build_adjustments
# ---------------------------------------------------------------------------

class TestBuildAdjustments:
    def test_frustrated_apologize(self, engine: ConversationEngine) -> None:
        sentiment = MagicMock(sentiment=Sentiment.FRUSTRATED, score=-0.8)
        adj = engine._build_adjustments(sentiment, {})
        assert adj == {"apologize": True}

    def test_impatient_shorten(self, engine: ConversationEngine) -> None:
        sentiment = MagicMock(sentiment=Sentiment.IMPATIENT, score=-0.3)
        adj = engine._build_adjustments(sentiment, {})
        assert adj == {"shorten": True}

    def test_unclear_feedback(self, engine: ConversationEngine) -> None:
        sentiment = MagicMock(sentiment=Sentiment.NEUTRAL, score=0.0)
        adj = engine._build_adjustments(sentiment, {"was_unclear": True})
        assert adj == {"clarify": True}

    def test_wrong_feedback(self, engine: ConversationEngine) -> None:
        sentiment = MagicMock(sentiment=Sentiment.NEUTRAL, score=0.0)
        adj = engine._build_adjustments(sentiment, {"was_wrong": True})
        assert adj == {"correct": True}
