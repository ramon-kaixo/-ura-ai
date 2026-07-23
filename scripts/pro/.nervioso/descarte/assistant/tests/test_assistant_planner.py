"""Tests for motor/assistant/planner.py — ConversationalPlanner."""

from __future__ import annotations

from motor.assistant.models import ConversationMode, UserIntent
from motor.assistant.planner import ConversationalPlanner


class TestConversationalPlanner:
    def setup_method(self):
        self.planner = ConversationalPlanner()

    def test_create_plan_greeting(self):
        plan = self.planner.create_plan("hola", UserIntent.GREETING)
        assert plan.plan_id != ""
        assert plan.objective != ""
        assert len(plan.tasks) >= 1

    def test_create_plan_question(self):
        plan = self.planner.create_plan("qué es URA?", UserIntent.QUESTION)
        assert plan.objective == "Responder pregunta"
        assert "riesgo" in plan.risks[0] if plan.risks else True

    def test_create_plan_command(self):
        plan = self.planner.create_plan("busca python", UserIntent.COMMAND)
        assert plan.next_action != ""

    def test_create_plan_chat_long(self):
        plan = self.planner.create_plan(
            "me gusta mucho cómo funciona este sistema de inteligencia artificial", UserIntent.CHAT
        )
        assert len(plan.objective) > 10

    def test_get_plan(self):
        plan = self.planner.create_plan("test", UserIntent.CHAT)
        retrieved = self.planner.get_plan(plan.plan_id)
        assert retrieved is not None
        assert retrieved.plan_id == plan.plan_id

    def test_get_plan_nonexistent(self):
        assert self.planner.get_plan("nonexistent") is None

    def test_update_plan(self):
        plan = self.planner.create_plan("test", UserIntent.CHAT)
        updated = self.planner.update_plan(plan.plan_id, objective="nuevo objetivo")
        assert updated is not None
        assert updated.objective == "nuevo objetivo"

    def test_update_plan_nonexistent(self):
        assert self.planner.update_plan("nonexistent", objective="x") is None

    def test_assess_risks(self):
        plan = self.planner.create_plan("test question?", UserIntent.QUESTION)
        risks = self.planner.assess_risks(plan.plan_id)
        assert isinstance(risks, list)

    def test_different_intents_produce_different_plans(self):
        plan_q = self.planner.create_plan("qué es?", UserIntent.QUESTION)
        plan_c = self.planner.create_plan("haz algo", UserIntent.COMMAND)
        assert plan_q.objective != plan_c.objective

    def test_explanation_mode_next_action(self):
        plan = self.planner.create_plan("explícame", UserIntent.CHAT, mode=ConversationMode.EXPLANATION)
        assert "explicación" in plan.next_action
