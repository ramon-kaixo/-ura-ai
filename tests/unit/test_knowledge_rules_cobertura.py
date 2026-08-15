"""Tests de cobertura P2 para knowledge/engine/rules.py — ramas no cubiertas.

Cubre las 14 sentencias y 2 ramas restantes tras los tests existentes
(test_rules_builtin, test_rules_safe_eval, test_rules_hypothesis):
- Operadores unarios (+), sets literales, slices con step, comprehensions con
  cláusula if (path False), límite de llamadas a función en el checker.
- Caminos defensivos muertos vía API pública (eval/compile de nodos AST
  fabricados): method call sin Attribute, dunder method, operadores unarios/
  binarios fuera de whitelist, comparación con op desconocido, llamadas con
  func que no es Name, y nombre no presente en env.
"""

from __future__ import annotations

import ast

import pytest

from knowledge.engine.rules import (
    _ALLOWED_METHODS,
    _MAX_FUNCTION_CALLS,
    Rule,
    UnsafeExpressionError,
    _eval_ast,
    _eval_method_call,
    safe_eval,
)

# ===================================================================
# Grupo A — safe_eval: operadores/slices/comprehensions no cubiertos
# ===================================================================


class TestSafeEvalMissingPaths:
    def test_unary_plus(self) -> None:
        """UAdd: +5 → 5 (solo USub y Not estaban cubiertos)."""
        assert safe_eval("+5") == 5

    def test_set_literal(self) -> None:
        """ast.Set literal (solo List/Tuple/Dict cubiertos)."""
        assert safe_eval("{1, 2, 3}") == {1, 2, 3}

    def test_slice_bounds_and_step(self) -> None:
        """ast.Slice con lower, upper y step no nulos."""
        assert safe_eval("[1, 2, 3, 4, 5][1:3]") == [2, 3]
        assert safe_eval("[0, 1, 2, 3, 4][1:4:2]") == [1, 3]

    def test_slice_open_ends(self) -> None:
        """ast.Slice con lower/upper None y step presente."""
        assert safe_eval("[1, 2, 3, 4][::2]") == [1, 3]
        assert safe_eval("[1, 2, 3, 4][::-1]") == [4, 3, 2, 1]

    def test_comprehension_with_if_false(self) -> None:
        """Comprehension con cláusula if que nunca se cumple (all() → False)."""
        assert safe_eval("[x for x in [1, 2, 3] if x > 5]") == []

    def test_comprehension_with_if_true(self) -> None:
        """Comprehension con cláusula if que se cumple (all() → True)."""
        assert safe_eval("[x for x in [1, 2, 3, 6] if x > 5]") == [6]

    def test_nested_comprehension_generators(self) -> None:
        """Dos generadores encadenados (recursión de _process)."""
        assert safe_eval("[x * y for x in [1, 2] for y in [3, 4]]") == [3, 4, 6, 8]


# ===================================================================
# Grupo B — _SafeEvalChecker: límite de llamadas a función
# ===================================================================


class TestSafeEvalCheckerCallLimit:
    def test_too_many_calls_raises(self) -> None:
        """12 calls (max + 11 abs) a profundidad 4 → excede _MAX_FUNCTION_CALLS.

        El test previo (test_rules_safe_eval.py) fallaba en profundidad
        (13 niveles de BinOp) antes de llegar al chequeo de calls.
        """
        expr = "max(" + ",".join(f"abs({i})" for i in range(_MAX_FUNCTION_CALLS + 1)) + ")"
        with pytest.raises(UnsafeExpressionError, match="llamadas a funciones excedido"):
            safe_eval(expr)

    def test_exactly_max_calls_allowed(self) -> None:
        """10 calls en total (max + 9 abs = _MAX_FUNCTION_CALLS) no dispara."""
        n = _MAX_FUNCTION_CALLS - 1
        expr = "max(" + ",".join(f"abs({i})" for i in range(n)) + ")"
        assert safe_eval(expr) == max(range(n))


# ===================================================================
# Grupo C — _eval_method_call: caminos defensivos muertos vía API
# ===================================================================


class TestEvalMethodCallDefensive:
    def test_func_not_attribute_raises(self) -> None:
        """node.func sin Attribute → 'Solo method calls permitidos'."""
        node = ast.Call(func=ast.Constant(value=1), args=[])
        with pytest.raises(UnsafeExpressionError, match="Solo method calls permitidos"):
            _eval_method_call(node, {}, None)

    def test_dunder_method_prohibited(self) -> None:
        """Método dunder inyectado en whitelist → bloqueado (check 130-131).

        Inalcanzable vía safe_eval (checker bloquea atributos '_*' antes), por
        eso se fabrica el nodo y se parchea _ALLOWED_METHODS temporalmente.
        """
        original = _ALLOWED_METHODS["dict"]
        _ALLOWED_METHODS["dict"] = set(original) | {"__getitem__"}
        try:
            node = ast.Call(
                func=ast.Attribute(
                    value=ast.Constant(value={"a": 1}),
                    attr="__getitem__",
                    ctx=ast.Load(),
                ),
                args=[ast.Constant(value="a")],
                keywords=[],
            )
            with pytest.raises(UnsafeExpressionError, match="Dunder methods prohibidos"):
                _eval_method_call(node, {}, None)
        finally:
            _ALLOWED_METHODS["dict"] = original


# ===================================================================
# Grupo D — _eval_ast: operadores/comparaciones fuera de whitelist
# ===================================================================


class TestEvalAstDefensive:
    def test_unknown_unary_op_raises(self) -> None:
        """Invert (~) no está en la whitelist de operadores unarios."""
        node = ast.UnaryOp(op=ast.Invert(), operand=ast.Constant(value=5))
        with pytest.raises(UnsafeExpressionError, match="Operador unario no permitido"):
            _eval_ast(node, {})

    def test_unknown_binary_op_raises(self) -> None:
        """MatMult (@) no está en la whitelist de operadores binarios."""
        node = ast.BinOp(
            op=ast.MatMult(),
            left=ast.Constant(value=2),
            right=ast.Constant(value=3),
        )
        with pytest.raises(UnsafeExpressionError, match="Operador binario no permitido"):
            _eval_ast(node, {})

    def test_known_binary_op_outside_whitelist_nodes(self) -> None:
        """LShift está en el dict de _eval_binop pero no en _ALLOWED_AST_NODES."""
        node = ast.BinOp(
            op=ast.LShift(),
            left=ast.Constant(value=5),
            right=ast.Constant(value=2),
        )
        assert _eval_ast(node, {}) == 20

    def test_compare_unknown_op_falls_through(self) -> None:
        """Op de comparación desconocido → bucle sin break → True (fall-through)."""
        node = ast.Compare(
            left=ast.Constant(value=1),
            ops=[ast.And()],
            comparators=[ast.Constant(value=2)],
        )
        assert _eval_ast(node, {}) is True

    def test_call_func_not_name_raises(self) -> None:
        """Call con func que no es Name ni Attribute → 'Solo llamadas a funciones directas'."""
        node = ast.Call(func=ast.Constant(value=1), args=[])
        with pytest.raises(UnsafeExpressionError, match="Solo llamadas a funciones directas"):
            _eval_ast(node, {})

    def test_call_func_not_in_env_raises(self) -> None:
        """Call con Name no presente en env → 'Función no permitida'."""
        node = ast.Call(func=ast.Name(id="evil", ctx=ast.Load()), args=[])
        with pytest.raises(UnsafeExpressionError, match="Función no permitida: evil"):
            _eval_ast(node, {})


# ===================================================================
# Grupo E — Protocol Rule: body no-op ejecutable
# ===================================================================


class TestRuleProtocolBody:
    def test_protocol_evaluate_body_is_noop(self) -> None:
        """El body `...` del Protocol Rule.evaluate es un no-op ejecutable.

        Cubre la sentencia de la línea 537 (contrato documentado), que solo
        se ejecuta si alguien invoca el método del Protocol directamente.
        """
        assert Rule.evaluate(object(), {}, {}) is None
