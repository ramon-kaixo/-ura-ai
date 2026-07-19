"""Tests for motor/assistant/ — motor conversacional."""

from __future__ import annotations

import tempfile
from pathlib import Path

from motor.assistant.context_window import ContextWindow
from motor.assistant.conversation import ConversationEngine
from motor.assistant.message_store import MessageStore
from motor.assistant.models import (
    Conversation,
    ConversationMode,
    Message,
    UserIntent,
)


class TestModels:
    def test_message_creation(self):
        msg = Message(role="user", content="hola")
        assert msg.role == "user"
        assert msg.content == "hola"
        assert msg.timestamp != ""

    def test_message_token_estimate(self):
        msg = Message(role="user", content="a" * 100)
        assert msg.token_estimate() == 25  # max(1, 100/4)

    def test_conversation_add_message(self):
        conv = Conversation(conversation_id="test1")
        conv.add_message("user", "hello")
        assert len(conv.messages) == 1
        assert conv.last_user_message is not None
        assert conv.last_user_message.content == "hello"

    def test_conversation_token_count(self):
        conv = Conversation(conversation_id="test2")
        conv.add_message("user", "hello")
        conv.add_message("assistant", "world")
        assert conv.token_count >= 2

    def test_conversation_mode_values(self):
        assert ConversationMode.CONVERSATION.value == "conversacion"
        assert ConversationMode.WORK.value == "trabajo"
        assert ConversationMode.EXPLANATION.value == "explicacion"

    def test_user_intent_values(self):
        assert UserIntent.GREETING.value == "greeting"
        assert UserIntent.FAREWELL.value == "farewell"
        assert UserIntent.CHAT.value == "chat"


class TestMessageStore:
    def setup_method(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            self.tmp = Path(f.name)
        self.store = MessageStore(db_path=str(self.tmp))

    def teardown_method(self):
        self.store.close()
        self.tmp.unlink(missing_ok=True)

    def test_append_and_retrieve(self):
        msg = Message(role="user", content="hola")
        self.store.append("conv1", msg)
        messages = self.store.get_conversation("conv1")
        assert len(messages) == 1
        assert messages[0].content == "hola"

    def test_multiple_messages(self):
        for i in range(5):
            self.store.append("conv1", Message(role="user", content=f"msg{i}"))
        messages = self.store.get_conversation("conv1")
        assert len(messages) == 5

    def test_list_conversations(self):
        self.store.append("c1", Message(role="user", content="a"))
        self.store.append("c2", Message(role="user", content="b"))
        convs = self.store.list_conversations()
        assert len(convs) == 2

    def test_delete_conversation(self):
        self.store.append("c1", Message(role="user", content="a"))
        assert self.store.delete_conversation("c1") is True
        assert len(self.store.get_conversation("c1")) == 0


class TestContextWindow:
    def test_build_context_respects_budget(self):
        window = ContextWindow(max_tokens=50, reserve_tokens=10)
        messages = [Message(role="user", content="x" * 80) for _ in range(10)]
        result = window.build_context(messages)
        assert len(result) < 10  # Not all fit

    def test_trim_to_budget(self):
        window = ContextWindow()
        messages = [Message(role="user", content="hello world") for _ in range(20)]
        result = window.trim_to_budget(messages, max_tokens=30)
        assert len(result) < 20


class TestConversationEngine:
    def setup_method(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            self.tmp = Path(f.name)
        self.engine = ConversationEngine(
            message_store=MessageStore(db_path=str(self.tmp)),
        )

    def teardown_method(self):
        self.tmp.unlink(missing_ok=True)

    def test_create_conversation(self):
        conv = self.engine.create_conversation()
        assert conv.conversation_id != ""
        assert conv.state is not None
        assert conv.state.turn_count == 0

    def test_get_or_create_existing(self):
        conv1 = self.engine.create_conversation("test_id")
        conv2 = self.engine.get_or_create("test_id")
        assert conv1 is conv2

    def test_get_or_create_new(self):
        conv = self.engine.get_or_create("new_id")
        assert conv.conversation_id == "new_id"

    def test_add_message(self):
        msg = self.engine.add_message("c1", "user", "hello")
        assert msg.content == "hello"
        conv = self.engine.get_conversation("c1")
        assert conv is not None
        assert len(conv.messages) == 1

    def test_get_context(self):
        self.engine.add_message("c1", "user", "message 1")
        self.engine.add_message("c1", "assistant", "response 1")
        self.engine.add_message("c1", "user", "message 2")
        ctx = self.engine.get_context("c1")
        assert len(ctx) == 3

    def test_detect_intent_greeting(self):
        assert self.engine.detect_intent("hola") == UserIntent.GREETING
        assert self.engine.detect_intent("hello") == UserIntent.GREETING

    def test_detect_intent_farewell(self):
        assert self.engine.detect_intent("adiós") == UserIntent.FAREWELL
        assert self.engine.detect_intent("gracias") == UserIntent.FAREWELL

    def test_detect_intent_confirm(self):
        assert self.engine.detect_intent("sí") == UserIntent.CONFIRM
        assert self.engine.detect_intent("ok") == UserIntent.CONFIRM

    def test_detect_intent_reject(self):
        assert self.engine.detect_intent("no") == UserIntent.REJECT

    def test_detect_intent_repeat(self):
        assert self.engine.detect_intent("repite") == UserIntent.REPEAT

    def test_detect_intent_question(self):
        assert self.engine.detect_intent("qué es esto?") == UserIntent.QUESTION

    def test_detect_intent_command(self):
        assert self.engine.detect_intent("busca python") == UserIntent.COMMAND
        assert self.engine.detect_intent("haz eso") == UserIntent.COMMAND

    def test_detect_intent_chat_default(self):
        assert self.engine.detect_intent("me gusta la música") == UserIntent.CHAT

    def test_resolve_reference(self):
        self.engine.add_message("c1", "user", "el proyecto de IA")
        resolved = self.engine.resolve_reference("hazlo", "c1")
        assert "ejecuta" in resolved or "proyecto" in resolved

    def test_list_conversations(self):
        self.engine.add_message("c1", "user", "a")
        self.engine.add_message("c2", "user", "b")
        convs = self.engine.list_conversations()
        assert len(convs) >= 2

    def test_delete_conversation(self):
        self.engine.add_message("c1", "user", "a")
        assert self.engine.delete_conversation("c1") is True
        assert self.engine.get_conversation("c1") is None

    def test_mode_persists(self):
        conv = self.engine.create_conversation("c1", mode=ConversationMode.WORK)
        assert conv.state is not None
        assert conv.state.mode == ConversationMode.WORK


class TestMessageStoreReal:
    def test_persistence(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            store1 = MessageStore(db_path=db_path)
            store1.append("c1", Message(role="user", content="persistent"))
            store1.close()

            store2 = MessageStore(db_path=db_path)
            msgs = store2.get_conversation("c1")
            assert len(msgs) == 1
            assert msgs[0].content == "persistent"
            store2.close()
        finally:
            Path(db_path).unlink(missing_ok=True)
