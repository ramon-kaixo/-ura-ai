"""Tests for evaluation, preferences, and auth modules."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from motor.assistant.evaluation import ConversationEvaluator
from motor.assistant.preferences import UserPreferenceLearning


@pytest.fixture
def db_path():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        yield f.name
    Path(f.name).unlink(missing_ok=True)


class TestEvaluator:
    def test_init_creates_db(self, db_path):
        ev = ConversationEvaluator(db_path)
        tables = ev._conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        assert any("evaluations" in t for t in tables[0])

    def test_record_and_score(self, db_path):
        ev = ConversationEvaluator(db_path)
        ev.record_metric("conv1", "sentiment", 0.8)
        ev.record_metric("conv1", "sentiment", 0.6)
        score = ev.get_conversation_score("conv1")
        assert score == 0.7

    def test_empty_score(self, db_path):
        ev = ConversationEvaluator(db_path)
        assert ev.get_conversation_score("nonexistent") == 0.0

    def test_record_with_details(self, db_path):
        ev = ConversationEvaluator(db_path)
        ev.record_metric("conv1", "quality", 0.9, {"reason": "good"})
        rows = ev._conn.execute("SELECT details FROM evaluations").fetchall()
        assert json.loads(rows[0][0]) == {"reason": "good"}

    def test_summary(self, db_path):
        ev = ConversationEvaluator(db_path)
        ev.record_metric("c1", "m1", 1.0)
        ev.record_metric("c1", "m1", 3.0)
        ev.record_metric("c2", "m2", 5.0)
        summary = ev.get_summary()
        assert summary["total_evaluations"] == 3
        assert summary["metrics"]["m1"]["avg"] == 2.0
        assert summary["metrics"]["m1"]["count"] == 2


class TestPreferences:
    def test_init_creates_db(self, db_path):
        pref = UserPreferenceLearning(db_path)
        tables = pref._conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        assert any("interactions" in t for t in tables[0])

    def test_record_and_get_preferences(self, db_path):
        pref = UserPreferenceLearning(db_path)
        pref.record("user1", "saludo", message_length=30)
        prefs = pref.get_preferences("user1")
        assert prefs["avg_message_length"] == 30
        assert "saludo" in prefs["common_intents"]

    def test_preferences_short_message(self, db_path):
        pref = UserPreferenceLearning(db_path)
        pref.record("user2", "si", message_length=5)
        prefs = pref.get_preferences("user2")
        assert prefs["preferred_length"] == "short"

    def test_preferences_cache(self, db_path):
        pref = UserPreferenceLearning(db_path)
        pref.record("user3", "test", message_length=50)
        prefs1 = pref.get_preferences("user3")
        prefs2 = pref.get_preferences("user3")
        assert prefs1 == prefs2

    def test_empty_user_preferences(self, db_path):
        pref = UserPreferenceLearning(db_path)
        prefs = pref.get_preferences("unknown")
        assert prefs["preferred_length"] == "normal"
        assert prefs["avg_message_length"] == 50
