"""Tests para BuiltinRule + RuleEvaluator + list_rules — sin DB, sin red.

BUGS DOCUMENTADOS EN PRODUCCIÓN:
1. _eval_call rechaza method calls (doc.get(...)) con "Solo llamadas a
   funciones directas". R001-R003 usan doc.get(...) → NUNCA se disparan.
   WORKAROUND: usar doc['title'] o doc.get('title','') en su lugar.
2. GeneratorExp no está en _ALLOWED_AST_NODES. R004-R005 usan any() con
   generator → NUNCA se disparan (se suman al bug 1).
3. RuleEvaluator(rules=[]) no vacía las reglas: [] or _BUILTIN_RULES → fallback.
"""
from __future__ import annotations

import pytest

from knowledge.engine.rules import (
    BuiltinRule,
    Finding,
    RuleEvaluator,
    RuleMetadata,
    _BUILTIN_RULES,
    list_rules,
)


# ===================================================================
# Grupo A — BuiltinRule (casos que SÍ funcionan)
# ===================================================================

class TestBuiltinRuleEvaluate:
    def test_simple_expression_triggers(self) -> None:
        """Usa solo funciones directas (sin method calls) para verificar
        que BuiltinRule.evaluate puede dispararse."""
        rule = BuiltinRule(
            metadata=RuleMetadata(id="T1", version="1", severity="INFO", description="test"),
            expression="True",
        )
        findings = rule.evaluate({"id": "x1"}, {})
        assert len(findings) == 1

    def test_false_expression_does_not_trigger(self) -> None:
        rule = BuiltinRule(
            metadata=RuleMetadata(id="T1", version="1", severity="INFO", description="test"),
            expression="False",
        )
        assert rule.evaluate({"id": "x1"}, {}) == []

    def test_finding_has_correct_fields(self) -> None:
        rule = BuiltinRule(
            metadata=RuleMetadata(id="T1", version="2", severity="WARN", description="custom"),
            expression="True",
        )
        findings = rule.evaluate({"id": "x1"}, {})
        f = findings[0]
        assert f.rule_id == "T1"
        assert f.rule_version == "2"
        assert f.severity == "WARN"
        assert f.message == "custom"
        assert f.doc_id == "x1"
        assert f.metadata == {"rule_name": "T1"}

    def test_doc_id_fallback(self) -> None:
        rule = BuiltinRule(
            metadata=RuleMetadata(id="T1", version="1", severity="INFO", description="test"),
            expression="True",
        )
        findings = rule.evaluate({}, {})
        assert findings[0].doc_id == "?"

    def test_exception_in_expression_returns_empty(self) -> None:
        rule = BuiltinRule(
            metadata=RuleMetadata(id="T1", version="1", severity="INFO", description="test"),
            expression="1/0",
        )
        assert rule.evaluate({"id": "x1"}, {}) == []

    def test_invalid_syntax_returns_empty(self) -> None:
        rule = BuiltinRule(
            metadata=RuleMetadata(id="T1", version="1", severity="INFO", description="test"),
            expression="@@invalid@@",
        )
        assert rule.evaluate({"id": "x1"}, {}) == []

    def test_context_via_subscript(self) -> None:
        """ctx[...] funciona (subscript), ctx.get(...) no (method call)."""
        rule = BuiltinRule(
            metadata=RuleMetadata(id="T1", version="1", severity="INFO", description="test"),
            expression="ctx['threshold'] > 10",
        )
        findings = rule.evaluate({"id": "x1"}, {"threshold": 20})
        assert len(findings) == 1

    def test_doc_via_subscript(self) -> None:
        """doc[...] funciona, doc.get(...) no."""
        rule = BuiltinRule(
            metadata=RuleMetadata(id="T1", version="1", severity="INFO", description="test"),
            expression="not bool(doc['title'])",
        )
        findings = rule.evaluate({"id": "x1", "title": ""}, {})
        assert len(findings) == 1

    def test_context_get_method_call_rejected(self) -> None:
        """.get() es method call → _eval_call lo rechaza → []"""
        rule = BuiltinRule(
            metadata=RuleMetadata(id="T1", version="1", severity="INFO", description="test"),
            expression="ctx.get('threshold', 0) > 10",
        )
        assert rule.evaluate({"id": "x1"}, {"threshold": 20}) == []

    def test_method_call_returns_empty(self) -> None:
        """BUG 1: doc.get() es method call, rechazado por _eval_call.
        La regla nunca se dispara."""
        rule = BuiltinRule(
            metadata=RuleMetadata(id="T1", version="1", severity="INFO", description="test"),
            expression="bool(doc.get('title', ''))",
        )
        assert rule.evaluate({"id": "x1"}, {}) == []


# ===================================================================
# Grupo B — Reglas built-in R001-R005 (documentan bugs)
# ===================================================================

class TestBuiltinRulesAllBroken:
    def test_R001_never_triggers(self) -> None:
        """BUG 1: doc.get('title', '') es method call, safe_eval lo rechaza."""
        r = _BUILTIN_RULES[0]
        assert r.evaluate({"id": "x1"}, {}) == []

    def test_R002_never_triggers(self) -> None:
        """BUG 1: doc.get('tags', []) es method call."""
        r = _BUILTIN_RULES[1]
        assert r.evaluate({"id": "x1"}, {}) == []

    def test_R003_never_triggers(self) -> None:
        """BUG 1: doc.get('body', '') es method call."""
        r = _BUILTIN_RULES[2]
        assert r.evaluate({"id": "x1"}, {}) == []

    def test_R004_never_triggers(self) -> None:
        """BUG 1 + 2: GeneratorExp en any() + doc.get method calls.
        safe_eval rechaza la expresión, BuiltinRule la traga con except."""
        r = _BUILTIN_RULES[3]
        assert r.evaluate({"id": "x1", "relations": ["nonexistent"]}, {"all_node_ids": {"other"}}) == []

    def test_R005_never_triggers(self) -> None:
        """BUG 1 + 2: GeneratorExp en any() + doc.get method calls."""
        r = _BUILTIN_RULES[4]
        assert r.evaluate({"id": "orphan", "relations": []}, {"all_relation_targets": {"other"}}) == []


# ===================================================================
# Grupo C — RuleEvaluator
# ===================================================================

class TestRuleEvaluatorInit:
    def test_default_rules(self) -> None:
        ev = RuleEvaluator()
        assert len(ev.rules) == 5
        ids = [r.metadata.id for r in ev.rules]
        assert ids == ["R001", "R002", "R003", "R004", "R005"]

    def test_custom_rules(self) -> None:
        custom = BuiltinRule(
            metadata=RuleMetadata(id="C1", version="1", severity="INFO", description="custom"),
            expression="True",
        )
        ev = RuleEvaluator(rules=[custom])
        assert len(ev.rules) == 1
        assert ev.rules[0].metadata.id == "C1"

    def test_rules_property_returns_copy(self) -> None:
        ev = RuleEvaluator()
        r = ev.rules
        r.clear()
        assert len(ev.rules) == 5

    def test_empty_rules_list_fallback(self) -> None:
        """BUG 3: [] or _BUILTIN_RULES → _BUILTIN_RULES. No permite
        RuleEvaluator vacío."""
        ev = RuleEvaluator(rules=[])
        assert len(ev.rules) == 5


class TestRuleEvaluatorEvaluate:
    def test_empty_docs(self) -> None:
        ev = RuleEvaluator()
        assert ev.evaluate([]) == []

    def test_custom_rule_triggers(self) -> None:
        custom = BuiltinRule(
            metadata=RuleMetadata(id="C1", version="1", severity="INFO", description="custom"),
            expression="True",
        )
        ev = RuleEvaluator(rules=[custom])
        findings = ev.evaluate([{"id": "d1"}])
        assert len(findings) == 1

    def test_custom_rule_no_trigger(self) -> None:
        custom = BuiltinRule(
            metadata=RuleMetadata(id="C1", version="1", severity="INFO", description="custom"),
            expression="False",
        )
        ev = RuleEvaluator(rules=[custom])
        assert ev.evaluate([{"id": "d1"}]) == []

    def test_deterministic_order(self) -> None:
        docs = [{"id": "b"}, {"id": "a"}]
        ev = RuleEvaluator(rules=[
            BuiltinRule(metadata=RuleMetadata(id="B", version="1", severity="INFO", description="x"), expression="True"),
            BuiltinRule(metadata=RuleMetadata(id="A", version="1", severity="INFO", description="x"), expression="True"),
        ])
        f1 = ev.evaluate(docs)
        f2 = ev.evaluate(docs)
        assert [(f.rule_id, f.doc_id) for f in f1] == [(f.rule_id, f.doc_id) for f in f2]

    def test_sorted_by_rule_then_doc(self) -> None:
        docs = [{"id": "z"}, {"id": "a"}]
        ev = RuleEvaluator(rules=[
            BuiltinRule(metadata=RuleMetadata(id="B", version="1", severity="INFO", description="x"), expression="True"),
            BuiltinRule(metadata=RuleMetadata(id="A", version="1", severity="INFO", description="x"), expression="True"),
        ])
        findings = ev.evaluate(docs)
        pairs = [(f.rule_id, f.doc_id) for f in findings]
        assert pairs == sorted(pairs)

    def test_rules_sorted_alphabetically(self) -> None:
        ev = RuleEvaluator(rules=[
            BuiltinRule(metadata=RuleMetadata(id="Z", version="1", severity="INFO", description="x"), expression="True"),
            BuiltinRule(metadata=RuleMetadata(id="A", version="1", severity="INFO", description="x"), expression="True"),
        ])
        ids = [r.metadata.id for r in ev.rules]
        assert ids == ["A", "Z"]

    def test_evaluate_one_convenience(self) -> None:
        custom = BuiltinRule(
            metadata=RuleMetadata(id="C1", version="1", severity="INFO", description="custom"),
            expression="True",
        )
        ev = RuleEvaluator(rules=[custom])
        assert len(ev.evaluate_one({"id": "d1"})) == 1

    def test_evaluate_one_no_trigger(self) -> None:
        custom = BuiltinRule(
            metadata=RuleMetadata(id="C1", version="1", severity="INFO", description="custom"),
            expression="False",
        )
        ev = RuleEvaluator(rules=[custom])
        assert ev.evaluate_one({"id": "d1"}) == []

    def test_builtin_rules_produce_no_findings(self) -> None:
        """Todas las reglas built-in están rotas (BUG 1 + 2).
        Verifica que al menos no crashean."""
        ev = RuleEvaluator()
        assert ev.evaluate([{"id": "d1"}]) == []

    def test_multiple_custom_rules_multiple_docs(self) -> None:
        rules = [
            BuiltinRule(metadata=RuleMetadata(id="A", version="1", severity="INFO", description="x"), expression="True"),
            BuiltinRule(metadata=RuleMetadata(id="B", version="1", severity="INFO", description="x"), expression="True"),
        ]
        docs = [{"id": "d1"}, {"id": "d2"}]
        ev = RuleEvaluator(rules=rules)
        findings = ev.evaluate(docs)
        assert len(findings) == 4  # 2 rules × 2 docs


# ===================================================================
# Grupo D — list_rules
# ===================================================================

class TestListRules:
    def test_returns_five(self) -> None:
        rules = list_rules()
        assert len(rules) == 5
        ids = [r.metadata.id for r in rules]
        assert ids == ["R001", "R002", "R003", "R004", "R005"]

    def test_returns_copy(self) -> None:
        rules = list_rules()
        rules.clear()
        assert len(list_rules()) == 5
