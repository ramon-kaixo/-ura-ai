"""Tests for F29 B7-B9: Personality, Learning, Management."""

from __future__ import annotations

import tempfile
from pathlib import Path

from motor.assistant.learning import ConversationalLearning
from motor.assistant.management import ConversationManager, ConversationSummary
from motor.assistant.models import UserIntent
from motor.assistant.personality import DecisionRule, PersonalityManager


class TestPersonalityManager:
    def setup_method(self):
        self.pm = PersonalityManager()

    def test_default_profile(self):
        p = self.pm.get_active_profile()
        assert p.name == "default"

    def test_should_summarize_long(self):
        assert self.pm.should_summarize(500)

    def test_should_not_summarize_short(self):
        assert not self.pm.should_summarize(100)

    def test_should_ask_low_confidence(self):
        assert self.pm.should_ask(0.3)

    def test_should_not_ask_high_confidence(self):
        assert not self.pm.should_ask(0.9)

    def test_should_assume_high_confidence(self):
        assert self.pm.should_assume(0.9)

    def test_decide_command_high_conf(self):
        decisions = self.pm.decide(UserIntent.COMMAND, 0.95, 500)
        assert DecisionRule.ASSUME in decisions

    def test_decide_ask_low_conf(self):
        decisions = self.pm.decide(UserIntent.QUESTION, 0.3, 100)
        assert DecisionRule.ASK in decisions


class TestConversationalLearning:
    def setup_method(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            self.tmp = Path(f.name)
        self.cl = ConversationalLearning(db_path=str(self.tmp))

    def teardown_method(self):
        self.tmp.unlink(missing_ok=True)

    def test_record_interaction(self):
        self.cl.record_interaction("user1", "greeting", 50)
        prefs = self.cl.get_preferences("user1")
        assert prefs.preferred_length != ""

    def test_default_preferences(self):
        prefs = self.cl.get_preferences("new_user")
        assert prefs.preferred_format == "text"

    def test_multiple_interactions(self):
        for _i in range(5):
            self.cl.record_interaction("user1", "command", 100)
        prefs = self.cl.get_preferences("user1")
        assert "command" in prefs.previous_intents


class TestConversationManager:
    def setup_method(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            self.db_path = Path(f.name)
        from motor.assistant.message_store import MessageStore

        self.store = MessageStore(db_path=str(self.db_path))
        self.cm = ConversationManager(message_store=self.store)

    def teardown_method(self):
        self.db_path.unlink(missing_ok=True)

    def test_detect_goal_change_initial(self):
        assert not self.cm.detect_goal_change("c1", UserIntent.CHAT)

    def test_detect_goal_change(self):
        self.cm.set_goal("c1", UserIntent.CHAT)
        assert self.cm.detect_goal_change("c1", UserIntent.COMMAND)

    def test_needs_summary(self):
        assert self.cm.needs_summary("c1", 60, 50)

    def test_not_needs_summary_below_threshold(self):
        assert not self.cm.needs_summary("c1", 30, 50)

    def test_store_and_get_summary(self):
        s = ConversationSummary(conversation_id="c1", summary="test", topics=["ai"])
        self.cm.store_summary("c1", s)
        retrieved = self.cm.get_summary("c1")
        assert retrieved is not None
        assert retrieved.summary == "test"

    def test_add_pending_task(self):
        self.cm.store_summary("c1", ConversationSummary(conversation_id="c1", summary=""))
        self.cm.add_pending_task("c1", "revisar documento")
        tasks = self.cm.get_pending_tasks("c1")
        assert "revisar documento" in tasks

    def test_get_pending_tasks_no_summary(self):
        tasks = self.cm.get_pending_tasks("nonexistent")
        assert tasks == []

    def test_split_conversation_small(self):
        # No split if under threshold
        new_id = self.cm.split_conversation("c1", 50)
        assert new_id == "c1"
