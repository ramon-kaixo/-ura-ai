"""Tests de cobertura para knowledge/engine/recommendation.py."""

from __future__ import annotations

import pytest

from knowledge.engine.recommendation import Recommendation, RecommendationValidator, ValidationResult


def _rec(**overrides) -> Recommendation:
    base = {"kind": "create", "target_id": "doc-new", "reason": "r"}
    base.update(overrides)
    return Recommendation(**base)


@pytest.fixture
def validator() -> RecommendationValidator:
    return RecommendationValidator()


def test_recommendation_defaults() -> None:
    r = _rec()
    assert r.priority == "medium"
    assert r.metadata == {}


def test_validation_result_defaults() -> None:
    v = ValidationResult(valid=True, reason="ok")
    assert v.warnings == []


@pytest.mark.parametrize(
    "kind,target,nodes,valid,reason",
    [
        ("create", "nuevo", {"a"}, True, "Documento nuevo válido"),
        ("create", "a", {"a"}, False, "ya existe"),
        ("update", "a", {"a"}, True, "Actualización válida"),
        ("update", "b", {"a"}, False, "no existe"),
        ("link", "a", {"a"}, True, "Enlace válido"),
        ("link", "b", {"a"}, False, "no existe"),
        ("archive", "a", {"a"}, True, "Archivo válido"),
        ("archive", "b", {"a"}, False, "no existe"),
    ],
)
def test_validate_por_tipo(validator, kind, target, nodes, valid, reason) -> None:
    res = validator.validate(_rec(kind=kind, target_id=target), set(nodes), set())
    assert res.valid is valid
    assert reason in res.reason


def test_validate_kind_desconocido(validator) -> None:
    res = validator.validate(_rec(kind="delete"), {"a"}, set())
    assert res.valid is False
    assert "desconocido" in res.reason
