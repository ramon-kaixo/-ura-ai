"""Tests para motor/intelligence/agents/planner.py y motor/observability/readiness.py."""
from __future__ import annotations

from unittest import mock

import pytest

from motor.intelligence.agents.message import AgentRole, AgentTask
from motor.intelligence.agents.planner import PlannerAgent
from motor.observability.readiness import ReadinessEntry, ReadinessRegistry


def _task(objective: str, context: dict | None = None) -> AgentTask:
    return AgentTask(id="t1", objective=objective, context=context or {})


class TestPlannerAgent:
    def test_init(self) -> None:
        p = PlannerAgent()
        assert p.name == "planner"
        assert p.role == AgentRole.PLANNER
        assert p.capabilities == ["plan", "decompose"]
        assert p.status.value == "idle"
        assert len(p.id) == 12

    def test_init_con_id(self) -> None:
        p = PlannerAgent("mi-id")
        assert p.id == "mi-id"

    def test_run_ok(self) -> None:
        p = PlannerAgent()
        result = p.run(_task("busca y encuentra informacion"))
        assert result.success is True
        assert "subtasks" in result.output
        assert result.duration_ms >= 0
        assert p.status.value == "idle"  # restaurado

    def test_run_error(self, monkeypatch) -> None:
        p = PlannerAgent()
        monkeypatch.setattr(p, "_decompose", mock.Mock(side_effect=ValueError("boom")))
        result = p.run(_task("x"))
        assert result.success is False
        assert "boom" in result.error

    def test_decompose_researcher(self) -> None:
        p = PlannerAgent()
        subs = p._decompose("search information about cats", {})
        roles = [s["agent_role"] for s in subs]
        assert AgentRole.RESEARCHER in roles
        # researcher insertado al inicio
        assert subs[0]["agent_role"] == AgentRole.RESEARCHER

    def test_decompose_executor(self) -> None:
        p = PlannerAgent()
        subs = p._decompose("run the script", {})
        roles = [s["agent_role"] for s in subs]
        assert AgentRole.EXECUTOR in roles

    def test_decompose_validator(self) -> None:
        p = PlannerAgent()
        subs = p._decompose("verify the result", {})
        roles = [s["agent_role"] for s in subs]
        assert AgentRole.VALIDATOR in roles

    def test_decompose_varias(self) -> None:
        p = PlannerAgent()
        subs = p._decompose("search, execute and verify everything", {})
        roles = {s["agent_role"] for s in subs}
        assert AgentRole.RESEARCHER in roles
        assert AgentRole.EXECUTOR in roles
        assert AgentRole.VALIDATOR in roles

    def test_decompose_sin_keyword_default_executor(self) -> None:
        p = PlannerAgent()
        subs = p._decompose("something without keywords", {})
        assert len(subs) == 1
        assert subs[0]["agent_role"] == AgentRole.EXECUTOR

    def test_decompose_atributos(self) -> None:
        p = PlannerAgent()
        subs = p._decompose("execute the script", {})
        assert subs[0]["priority"] == 0
        assert subs[0]["timeout"] == 30
        assert subs[0]["objective"] == "execute the script"


class TestReadinessEntry:
    def test_defaults(self) -> None:
        e = ReadinessEntry(dependency="db")
        assert e.ready is False
        assert e.reason == ""
        assert e.dependency == "db"


class TestReadinessRegistry:
    def test_sin_dependencias_ready(self) -> None:
        r = ReadinessRegistry()
        assert r.is_ready() is True
        assert r.snapshot()["ready"] is True

    def test_register(self) -> None:
        r = ReadinessRegistry()
        r.register_dependency("qdrant")
        r.register_dependency("qdrant")  # idempotente
        assert len(r._dependencies) == 1
        assert r.is_ready() is False

    def test_set_ready(self) -> None:
        r = ReadinessRegistry()
        r.register_dependency("qdrant")
        r.set_ready("qdrant")
        assert r.is_ready() is True

    def test_set_not_ready(self) -> None:
        r = ReadinessRegistry()
        r.register_dependency("qdrant")
        r.set_ready("qdrant")
        r.set_not_ready("qdrant", "caido")
        assert r.is_ready() is False
        assert r._dependencies["qdrant"].reason == "caido"

    def test_set_ready_inexistente(self) -> None:
        r = ReadinessRegistry()
        r.set_ready("nope")  # no debe lanzar
        r.set_not_ready("nope")  # no debe lanzar

    def test_multiples(self) -> None:
        r = ReadinessRegistry()
        r.register_dependency("a")
        r.register_dependency("b")
        r.set_ready("a")
        assert r.is_ready() is False
        r.set_ready("b")
        assert r.is_ready() is True

    def test_snapshot(self) -> None:
        r = ReadinessRegistry()
        r.register_dependency("a")
        r.set_ready("a")
        snap = r.snapshot()
        assert snap["ready"] is True
        assert snap["dependencies"]["a"]["ready"] is True
