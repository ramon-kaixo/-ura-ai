"""Tests for motor/assistant/style.py — StyleEngine."""

from __future__ import annotations

from motor.assistant.models import ConversationMode, UserIntent
from motor.assistant.style import Formality, StyleEngine, StyleProfile, Tone


class TestToneAndFormality:
    def test_tone_values(self):
        assert Tone.CASUAL.value == "casual"
        assert Tone.PROFESSIONAL.value == "professional"
        assert Tone.DIDACTIC.value == "didactic"

    def test_formality_values(self):
        assert Formality.INFORMAL.value == "informal"
        assert Formality.NEUTRAL.value == "neutral"
        assert Formality.FORMAL.value == "formal"


class TestStyleProfile:
    def test_default_profile(self):
        p = StyleProfile()
        assert p.tone == Tone.NEUTRAL
        assert p.formality == Formality.NEUTRAL
        assert p.max_length_chars == 1000
        assert p.depth == "normal"

    def test_custom_profile(self):
        p = StyleProfile(tone=Tone.CASUAL, depth="deep", use_bullets=True)
        assert p.tone == Tone.CASUAL
        assert p.depth == "deep"
        assert p.use_bullets


class TestStyleEngine:
    def setup_method(self):
        self.engine = StyleEngine()

    def test_conversation_mode(self):
        p = self.engine.get_profile(ConversationMode.CONVERSATION)
        assert p.tone == Tone.CASUAL
        assert p.formality == Formality.INFORMAL
        assert p.emoji_allowed
        assert p.max_length_chars == 500

    def test_work_mode(self):
        p = self.engine.get_profile(ConversationMode.WORK)
        assert p.tone == Tone.PROFESSIONAL
        assert p.formality == Formality.FORMAL
        assert not p.emoji_allowed
        assert p.use_bullets

    def test_explanation_mode(self):
        p = self.engine.get_profile(ConversationMode.EXPLANATION)
        assert p.tone == Tone.DIDACTIC
        assert p.depth == "deep"
        assert p.use_examples

    def test_greeting_overrides_length(self):
        p = self.engine.get_profile(ConversationMode.CONVERSATION, UserIntent.GREETING)
        assert p.max_length_chars == 200

    def test_command_overrides_bullets(self):
        p = self.engine.get_profile(ConversationMode.WORK, UserIntent.COMMAND)
        assert p.use_bullets

    def test_question_overrides_depth(self):
        p = self.engine.get_profile(ConversationMode.EXPLANATION, UserIntent.QUESTION)
        assert p.depth == "deep"

    def test_unknown_intent_no_override(self):
        p = self.engine.get_profile(ConversationMode.CONVERSATION, UserIntent.UNKNOWN)
        assert p.max_length_chars == 500  # default for conversation

    def test_build_system_prompt_conversation(self):
        prompt = self.engine.build_system_prompt(ConversationMode.CONVERSATION)
        assert "natural" in prompt or "conversacional" in prompt

    def test_build_system_prompt_work(self):
        prompt = self.engine.build_system_prompt(ConversationMode.WORK)
        assert "bullet" in prompt or "estructurada" in prompt

    def test_build_system_prompt_explanation(self):
        prompt = self.engine.build_system_prompt(ConversationMode.EXPLANATION)
        assert "ejemplo" in prompt or "paso" in prompt or "profundidad" in prompt
