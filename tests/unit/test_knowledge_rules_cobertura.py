"""Tests de cobertura para knowledge/engine/rules.py (SafeEval + RuleEvaluator)."""

from __future__ import annotations

import ast

import pytest

from knowledge.engine.rules import (
    _ALLOWED_METHODS,
    BuiltinRule,
    Finding,
    RuleEvaluator,
    RuleMetadata,
    UnsafeExpressionError,
    _eval_ast,
    list_rules,
    safe_eval,
)

# ── SafeEval: aritmética y operadores ───────────────────────────────────────


def test_safe_eval_aritmetica() -> None:
    assert safe_eval("1 + 2 * 3") == 7
    assert safe_eval("10 / 4") == 2.5
    assert safe_eval("10 // 3") == 3
    assert safe_eval("10 % 3") == 1
    assert safe_eval("2 ** 10") == 1024
    assert safe_eval("5 - 3") == 2
    assert safe_eval("-5") == -5
    assert safe_eval("+5") == 5
    assert safe_eval("not False") is True


def test_safe_eval_bits_inalcanzables_via_checker() -> None:
    for op in (ast.LShift(), ast.RShift(), ast.BitOr(), ast.BitXor(), ast.BitAnd()):
        tree = ast.BinOp(left=ast.Constant(6), op=op, right=ast.Constant(3))
        assert _eval_ast(tree, {}) is not None


def test_safe_eval_comparaciones() -> None:
    assert safe_eval("1 < 2") is True
    assert safe_eval("1 < 2 < 3") is True
    assert safe_eval("3 > 2 > 5") is False
    assert safe_eval("'a' in ('a', 'b')") is True
    assert safe_eval("'c' not in ('a', 'b')") is True
    assert safe_eval("1 == 1") is True
    assert safe_eval("1 != 2") is True
    assert safe_eval("'x' is 'x'") is True
    assert safe_eval("'x' is not 'y'") is True
    assert safe_eval("1 <= 2") is True
    assert safe_eval("2 >= 2") is True


def test_safe_eval_booleanos() -> None:
    assert safe_eval("True or False") is True
    assert safe_eval("False or False") is False
    assert safe_eval("True and False") is False
    assert safe_eval("True and True") is True


def test_safe_eval_ternario() -> None:
    assert safe_eval("1 if 2 > 1 else 0") == 1
    assert safe_eval("0 if 1 > 2 else 9") == 9


def test_safe_eval_containers() -> None:
    assert safe_eval("[1, 2][0]") == 1
    assert safe_eval("(1, 2)[1]") == 2
    assert safe_eval("{1, 2, 3}") == {1, 2, 3}
    assert safe_eval("{'a': 1}['a']") == 1
    assert safe_eval("{'a': 1}") == {"a": 1}


def test_safe_eval_slices() -> None:
    assert safe_eval("'abcd'[1:3]") == "bc"
    assert safe_eval("'abcd'[1:]") == "bcd"
    assert safe_eval("[0, 1, 2, 3][:2]") == [0, 1]
    assert safe_eval("[0, 1, 2, 3][::2]") == [0, 2]
    assert safe_eval("[0, 1, 2, 3][1:3:1]") == [1, 2]


def test_safe_eval_comprehensions() -> None:
    assert safe_eval("[x for x in [1, 2, 3] if x > 1]") == [2, 3]
    assert safe_eval("[x * y for x in [1, 2] for y in [3, 4]]") == [3, 4, 6, 8]
    assert safe_eval("sum(x for x in [1, 2, 3])") == 6


def test_safe_eval_funciones() -> None:
    assert safe_eval("len([1, 2, 3])") == 3
    assert safe_eval("max([1, 2, 3])") == 3
    assert safe_eval("min([1, 2], default=0)") == 1
    assert safe_eval("sorted([3, 1, 2])") == [1, 2, 3]
    assert safe_eval("list(range(3))") == [0, 1, 2]
    assert safe_eval("all([True, True])") is True
    assert safe_eval("any([False, True])") is True
    assert safe_eval("abs(-3)") == 3
    assert safe_eval("str(3)") == "3"
    assert safe_eval("int('3')") == 3
    assert safe_eval("enumerate([7])") is not None
    assert safe_eval("reversed([1, 2])") is not None
    assert safe_eval("zip([1], [2])") is not None
    assert safe_eval("tuple([1])") == (1,)
    assert safe_eval("set([1, 1])") == {1}
    assert safe_eval("dict([('a', 1)])") == {"a": 1}
    assert safe_eval("isinstance(1, int)") is True
    assert safe_eval("bool([])") is False
    assert safe_eval("float('1.5')") == 1.5


def test_safe_eval_method_calls() -> None:
    assert safe_eval("'abc'.upper()") == "ABC"
    assert safe_eval("'ABC'.lower()") == "abc"
    assert safe_eval("'  x  '.strip()") == "x"
    assert safe_eval("'a b c'.split()") == ["a", "b", "c"]
    assert safe_eval("'hola'.startswith('ho')") is True
    assert safe_eval("'hola'.endswith('la')") is True
    assert safe_eval("{'a': 1}.get('a')") == 1
    assert safe_eval("{'a': 1}.get('z', 9)") == 9
    assert safe_eval("max([], default=9)") == 9
    assert safe_eval("list({'a': 1, 'b': 2}.keys())") == ["a", "b"]
    assert safe_eval("list({'a': 1}.values())") == [1]
    assert safe_eval("list({'a': 1}.items())") == [("a", 1)]


def test_safe_eval_context() -> None:
    assert safe_eval("doc['title'] == 'x'", {"doc": {"title": "x"}}) is True
    assert safe_eval("doc.get('tags', [])", {"doc": {"title": "x"}}) == []
    extra = {"doc": {"id": "1"}, "no_usado": 42}
    assert safe_eval("doc['id']", extra) == "1"


def test_safe_eval_constantes_aliases() -> None:
    assert safe_eval("true") is True
    assert safe_eval("false") is False
    assert safe_eval("null") is None


# ── SafeEval: rechazos ──────────────────────────────────────────────────────


def test_safe_eval_longitud_maxima() -> None:
    with pytest.raises(UnsafeExpressionError):
        safe_eval("1" * 4096)


def test_safe_eval_nodo_prohibido_lambda() -> None:
    with pytest.raises(UnsafeExpressionError):
        safe_eval("lambda: 1")


def test_safe_eval_nodo_prohibido_fstring() -> None:
    with pytest.raises(UnsafeExpressionError):
        safe_eval("f'{1}'")


def test_safe_eval_nodo_prohibido_walrus() -> None:
    with pytest.raises(UnsafeExpressionError):
        safe_eval("(x := 1)")


def test_safe_eval_profundidad_maxima() -> None:
    with pytest.raises(UnsafeExpressionError):
        safe_eval("-" * 11 + "1")


def test_safe_eval_nodos_maximos() -> None:
    with pytest.raises(UnsafeExpressionError):
        safe_eval("+".join(["1"] * 101))


def test_safe_eval_calls_maximos() -> None:
    with pytest.raises(UnsafeExpressionError):
        safe_eval("max(max(max(max(max(max(max(max(max(max(max(1)))))))))))")


def test_safe_eval_funcion_no_permitida() -> None:
    with pytest.raises(UnsafeExpressionError):
        safe_eval("open('/etc/passwd')")


def test_safe_eval_nombre_no_definido() -> None:
    with pytest.raises(UnsafeExpressionError):
        safe_eval("zzz")


def test_safe_eval_dunder_prohibido() -> None:
    with pytest.raises(UnsafeExpressionError):
        safe_eval("'a'.__len__()")


def test_safe_eval_atributo_privado_prohibido() -> None:
    with pytest.raises(UnsafeExpressionError):
        safe_eval("doc._secreto", {"doc": {"_secreto": 1}})


def test_safe_eval_method_tipo_no_permitido() -> None:
    with pytest.raises(UnsafeExpressionError):
        safe_eval("(1).bit_length()")


def test_safe_eval_method_no_permitido() -> None:
    with pytest.raises(UnsafeExpressionError):
        safe_eval("{'a': 1}.update({'b': 2})")


def test_safe_eval_nodo_no_soportado() -> None:
    tree = ast.UnaryOp(op=ast.Invert(), operand=ast.Constant(5))
    with pytest.raises(UnsafeExpressionError):
        _eval_ast(tree, {})


def test_safe_eval_method_call_no_attribute() -> None:
    tree = ast.Call(func=ast.Name(id="nope", ctx=ast.Load()), args=[], keywords=[])
    with pytest.raises(UnsafeExpressionError):
        _eval_ast(tree, {})


def test_safe_eval_binop_no_permitido() -> None:
    tree = ast.BinOp(
        left=ast.Constant(1),
        op=ast.MatMult(),
        right=ast.Constant(2),
    )
    with pytest.raises(UnsafeExpressionError):
        _eval_ast(tree, {})


def test_safe_eval_builtin_rule_excepcion_logueada() -> None:
    rule = BuiltinRule(
        metadata=RuleMetadata(id="RX", version="1", severity="WARN", description="div"),
        expression="1 / 0",
    )
    assert rule.evaluate({"id": "d1"}, {}) == []


# ── RuleEvaluator ───────────────────────────────────────────────────────────


def _doc(did: str, **kw: object) -> dict[str, object]:
    base: dict[str, object] = {
        "id": did,
        "title": f"T{did}",
        "tags": ["x"],
        "body": "cuerpo",
        "relations": [],
    }
    base.update(kw)
    return base


def test_evaluator_r001_sin_titulo() -> None:
    ev = RuleEvaluator()
    findings = ev.evaluate([_doc("d1", title="")])
    assert any(f.rule_id == "R001" for f in findings)


def test_evaluator_r002_sin_tags() -> None:
    ev = RuleEvaluator()
    findings = ev.evaluate([_doc("d1", tags=[])])
    assert any(f.rule_id == "R002" for f in findings)


def test_evaluator_r003_body_vacio() -> None:
    ev = RuleEvaluator()
    findings = ev.evaluate([_doc("d1", body="")])
    assert any(f.rule_id == "R003" for f in findings)


def test_evaluator_r004_enlace_inexistente() -> None:
    ev = RuleEvaluator()
    findings = ev.evaluate([_doc("d1", relations=["ghost"])], all_node_ids={"d1"})
    assert any(f.rule_id == "R004" for f in findings)
    ok = ev.evaluate([_doc("d1", relations=["d2"])], all_node_ids={"d1", "d2"})
    assert not any(f.rule_id == "R004" for f in ok)


def test_evaluator_r005_aislado() -> None:
    ev = RuleEvaluator()
    findings = ev.evaluate([_doc("d1")])
    assert any(f.rule_id == "R005" for f in findings)
    con_target = ev.evaluate([_doc("d1")], all_relation_targets={"d1"})
    assert not any(f.rule_id == "R005" for f in con_target)


def test_evaluator_orden_determinista() -> None:
    ev = RuleEvaluator()
    findings = ev.evaluate([_doc("b"), _doc("a")])
    ids = [(f.rule_id, f.doc_id) for f in findings]
    assert ids == sorted(ids)
    assert findings[0].doc_id == "a"


def test_evaluator_doc_sin_id() -> None:
    ev = RuleEvaluator()
    findings = ev.evaluate([{"title": "x", "tags": [], "body": ""}])
    assert all(f.doc_id == "?" for f in findings)


def test_evaluator_one() -> None:
    ev = RuleEvaluator()
    assert len(ev.evaluate_one(_doc("d1"))) == 1  # solo R005 (tiene título/tags/body)


def test_evaluator_rules_personalizadas_ordenadas() -> None:
    r2 = BuiltinRule(
        metadata=RuleMetadata(id="R200", version="1", severity="INFO", description="b"),
        expression="False",
    )
    r1 = BuiltinRule(
        metadata=RuleMetadata(id="R100", version="1", severity="INFO", description="a"),
        expression="False",
    )
    ev = RuleEvaluator(rules=[r2, r1])
    assert [r.metadata.id for r in ev.rules] == ["R100", "R200"]


def test_evaluator_rules_property_devuelve_copia() -> None:
    ev = RuleEvaluator()
    ev.rules.append(BuiltinRule(metadata=RuleMetadata(id="X", version="1", severity="I", description=""), expression="False"))
    assert all(r.metadata.id != "X" for r in ev._rules)


def test_list_rules() -> None:
    assert [r.metadata.id for r in list_rules()] == ["R001", "R002", "R003", "R004", "R005"]


def test_metadatos_y_findings_defaults() -> None:
    m = RuleMetadata(id="R001", version="1", severity="WARN", description="x")
    assert m.category == "quality"
    assert m.deterministic is True
    assert m.cost == "O(1)"
    assert m.enabled_by_default is True
    f = Finding(rule_id="R1", rule_version="1", doc_id="d", severity="WARN", message="m")
    assert f.metadata == {}
    assert _ALLOWED_METHODS["str"] == {"upper", "lower", "strip", "replace", "startswith", "endswith", "split"}
