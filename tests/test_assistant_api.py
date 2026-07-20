"""Tests para motor/assistant/api.py — endpoint conversacional."""

from __future__ import annotations

from motor.assistant.api import _FALLBACK_REPLIES, _build_system_prompt


class TestSystemPrompts:
    def test_spanish_conversation(self):
        prompt = _build_system_prompt("conversacion", {}, "es")
        assert "español" in prompt or "natural" in prompt
        assert "URA" in prompt

    def test_english_conversation(self):
        prompt = _build_system_prompt("conversacion", {}, "en")
        assert "English" in prompt or "natural" in prompt

    def test_work_mode_has_bullets(self):
        prompt = _build_system_prompt("trabajo", {}, "es")
        assert "bullet" in prompt or "estructurada" in prompt

    def test_explanation_mode_has_depth(self):
        prompt = _build_system_prompt("explicacion", {}, "es")
        assert "profundiza" in prompt or "paso" in prompt

    def test_sentiment_injected_spanish(self):
        prompt = _build_system_prompt(
            "conversacion", {"sentiment": "frustrado", "sentiment_action": "disculparse"}, "es"
        )
        assert "frustrado" in prompt

    def test_sentiment_injected_english(self):
        prompt = _build_system_prompt(
            "conversacion", {"sentiment": "frustrated", "sentiment_action": "apologize"}, "en"
        )
        assert "frustrated" in prompt

    def test_fallback_replies_exist(self):
        assert "es" in _FALLBACK_REPLIES
        assert "en" in _FALLBACK_REPLIES
