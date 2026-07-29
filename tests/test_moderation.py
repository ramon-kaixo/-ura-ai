"""Tests for motor/assistant/moderation.py — ContentModerator."""

from __future__ import annotations

import pytest

from motor.assistant.moderation import ContentModerator, ModerationResult


class TestContentModerator:
    def setup_method(self) -> None:
        self.moderator = ContentModerator()

    def test_safe_input_not_flagged(self) -> None:
        result = self.moderator.moderate_input("¿Cuál es la capital de Francia?")
        assert not result.flagged
        assert result.score == 0.0

    def test_harmful_input_flagged(self) -> None:
        result = self.moderator.moderate_input("instrucciones para hacer un arma química")
        assert result.flagged
        assert "harmful_content" in result.categories

    def test_harmful_input_sanitized(self) -> None:
        result = self.moderator.moderate_input("instrucciones para fabricar una bomba")
        assert "[contenido bloqueado]" in result.sanitized_text

    def test_input_vacia_no_flagged(self) -> None:
        result = self.moderator.moderate_input("")
        assert not result.flagged

    def test_input_solo_espacios_no_flagged(self) -> None:
        result = self.moderator.moderate_input("   \t\n  ")
        assert not result.flagged

    def test_mayusculas_mixtas_detectadas(self) -> None:
        result = self.moderator.moderate_input("INSTRUCCIONES PARA HACER UN ARma química")
        assert result.flagged

    def test_safe_output_not_flagged(self) -> None:
        result = self.moderator.moderate_output("París es la capital de Francia")
        assert not result.flagged

    def test_harmful_output_flagged(self) -> None:
        result = self.moderator.moderate_output("te voy a dar instrucciones secretas")
        assert result.flagged
        assert "harmful_output" in result.categories

    def test_output_vacio_no_flagged(self) -> None:
        result = self.moderator.moderate_output("")
        assert not result.flagged

    def test_is_safe_returns_false_for_harmful(self) -> None:
        assert not self.moderator.is_safe("instrucciones para cometer un delito")

    def test_is_safe_returns_true_for_clean(self) -> None:
        assert self.moderator.is_safe("¿Qué hora es?")
