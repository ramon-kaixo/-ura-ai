"""Tests para safe_eval + _SafeEvalChecker — funciones 100% puras (sin DB, sin red).
Cada test documenta qué comportamiento verifica y qué bug detectaría.
"""
from __future__ import annotations

import ast

import pytest

from knowledge.engine.rules import (
    _MAX_AST_DEPTH,
    _MAX_AST_NODES,
    _MAX_EXPRESSION_LENGTH,
    _MAX_FUNCTION_CALLS,
    UnsafeExpressionError,
    _eval_ast,
    _SafeEvalChecker,
    safe_eval,
)

# ===================================================================
# Grupo A — Expresiones literales válidas
# ===================================================================

class TestLiterals:
    def test_int(self) -> None:
        assert safe_eval("42") == 42

    def test_float(self) -> None:
        assert safe_eval("3.14") == 3.14

    def test_string(self) -> None:
        assert safe_eval("'hello'") == "hello"

    def test_bool_true(self) -> None:
        assert safe_eval("True") is True

    def test_bool_false(self) -> None:
        assert safe_eval("False") is False

    def test_none(self) -> None:
        assert safe_eval("None") is None

    def test_list(self) -> None:
        assert safe_eval("[1, 2, 3]") == [1, 2, 3]

    def test_dict(self) -> None:
        assert safe_eval("{'a': 1}") == {"a": 1}

    def test_nested_list(self) -> None:
        assert safe_eval("[[1, 2], [3, 4]]") == [[1, 2], [3, 4]]

    def test_tuple(self) -> None:
        assert safe_eval("(1, 2)") == (1, 2)


# ===================================================================
# Grupo B — Operaciones aritméticas, comparación, booleanas
# ===================================================================

class TestOperators:
    def test_arithmetic(self) -> None:
        assert safe_eval("1 + 2 * 3") == 7

    def test_comparison_less(self) -> None:
        assert safe_eval("1 < 2") is True

    def test_comparison_eq(self) -> None:
        assert safe_eval("'a' == 'a'") is True

    def test_boolean_and_or(self) -> None:
        assert safe_eval("True and False or True") is True

    def test_unary_neg(self) -> None:
        assert safe_eval("-5") == -5

    def test_unary_not(self) -> None:
        assert safe_eval("not True") is False

    def test_ifexp_true_branch(self) -> None:
        assert safe_eval("1 if True else 2") == 1

    def test_ifexp_false_branch(self) -> None:
        assert safe_eval("2 if False else 3") == 3

    def test_subscript_list(self) -> None:
        assert safe_eval("[10, 20, 30][1]") == 20

    def test_subscript_dict(self) -> None:
        assert safe_eval("{'k': 'v'}['k']") == "v"


# ===================================================================
# Grupo C — Llamadas a funciones de la whitelist
# ===================================================================

class TestWhitelistFunctions:
    def test_abs(self) -> None:
        assert safe_eval("abs(-5)") == 5

    def test_len(self) -> None:
        assert safe_eval("len([1, 2, 3])") == 3

    def test_str_conversion(self) -> None:
        assert safe_eval("str(42)") == "42"

    def test_int_conversion(self) -> None:
        assert safe_eval("int('42')") == 42

    def test_float_conversion(self) -> None:
        assert safe_eval("float('3.14')") == 3.14

    def test_bool_conversion(self) -> None:
        assert safe_eval("bool(1)") is True

    def test_min(self) -> None:
        assert safe_eval("min(3, 1, 2)") == 1

    def test_max(self) -> None:
        assert safe_eval("max(3, 1, 2)") == 3

    def test_sum(self) -> None:
        assert safe_eval("sum([1, 2, 3])") == 6

    def test_isinstance(self) -> None:
        assert safe_eval("isinstance(42, int)") is True

    def test_sorted(self) -> None:
        assert safe_eval("sorted([3, 1, 2])") == [1, 2, 3]

    def test_whitelist_list(self) -> None:
        assert safe_eval("list('abc')") == ["a", "b", "c"]

    def test_whitelist_range(self) -> None:
        assert list(safe_eval("range(3)")) == [0, 1, 2]


# ===================================================================
# Grupo D — Contexto (variables inyectadas)
# ===================================================================

class TestContext:
    def test_single_variable(self) -> None:
        assert safe_eval("x + 1", {"x": 5}) == 6

    def test_multiple_variables(self) -> None:
        assert safe_eval("a + b", {"a": 1, "b": 2}) == 3

    def test_empty_context(self) -> None:
        assert safe_eval("42", {}) == 42

    def test_unused_context_ignored(self) -> None:
        assert safe_eval("1", {"unused": 99}) == 1

    def test_context_does_not_leak_whitelist(self) -> None:
        result = safe_eval("x + y", {"x": 1, "y": 2, "__import__": "hacker"})
        assert result == 3


# ===================================================================
# Grupo E — Seguridad: expresiones peligrosas bloqueadas
# ===================================================================

class TestSecurityBlocked:
    def test_rejects_import(self) -> None:
        with pytest.raises(UnsafeExpressionError):
            safe_eval("__import__('os')")

    def test_rejects_eval(self) -> None:
        with pytest.raises(UnsafeExpressionError):
            safe_eval("eval('1+1')")

    def test_rejects_exec(self) -> None:
        with pytest.raises(UnsafeExpressionError):
            safe_eval("exec('x=1')")

    def test_rejects_open(self) -> None:
        with pytest.raises(UnsafeExpressionError):
            safe_eval("open('/etc/passwd')")

    def test_rejects_compile(self) -> None:
        with pytest.raises(UnsafeExpressionError):
            safe_eval("compile('1', '', 'exec')")

    def test_rejects_getattr(self) -> None:
        with pytest.raises(UnsafeExpressionError):
            safe_eval("getattr('abc', '__class__')")

    def test_rejects_lambda(self) -> None:
        with pytest.raises(UnsafeExpressionError):
            safe_eval("lambda x: x")

    def test_rejects_named_expr(self) -> None:
        with pytest.raises(UnsafeExpressionError):
            safe_eval("(x := 1)")

    def test_rejects_attribute_access(self) -> None:
        with pytest.raises(UnsafeExpressionError):
            safe_eval("'str'.capitalize")

    def test_rejects_dunder_attribute(self) -> None:
        with pytest.raises(UnsafeExpressionError):
            safe_eval("'abc'.__class__")

    def test_rejects_dunder_method_call(self) -> None:
        with pytest.raises(UnsafeExpressionError):
            safe_eval("'abc'.__len__()")

    def test_rejects_private_attribute(self) -> None:
        with pytest.raises(UnsafeExpressionError):
            safe_eval("object().__dict__")


# ===================================================================
# Grupo F — Seguridad: límites de tamaño/profundidad/nodos/calls
# ===================================================================

class TestSecurityLimits:
    def test_rejects_too_long_expression(self) -> None:
        expr = "x" * (_MAX_EXPRESSION_LENGTH + 1)
        with pytest.raises(UnsafeExpressionError, match="demasiado larga"):
            safe_eval(expr)

    def test_accepts_max_length_expression_parses(self) -> None:
        expr = "42"
        result = safe_eval(expr)
        assert result == 42

    def test_rejects_deep_nesting(self) -> None:
        depth = _MAX_AST_DEPTH - 1
        nested = "1" + "".join(f" if True else ({i}" for i in range(depth))
        nested += ")" * depth
        with pytest.raises(UnsafeExpressionError, match="Profundidad"):
            safe_eval(nested)

    def test_accepts_max_depth(self) -> None:
        depth = _MAX_AST_DEPTH - 2
        nested = "1" + "".join(f" if True else ({i}" for i in range(depth))
        nested += ")" * depth
        result = safe_eval(nested)
        assert result is not None

    def test_rejects_too_many_nodes(self) -> None:
        nodes = _MAX_AST_NODES
        items = nodes - 2  # Expression + List overhead
        expr = "[" + ", ".join("0" for _ in range(items)) + "]"
        with pytest.raises(UnsafeExpressionError, match="nodos|Profundidad"):
            safe_eval(expr)

    def test_rejects_too_many_calls(self) -> None:
        calls = _MAX_FUNCTION_CALLS + 1
        expr = "+".join(f"abs({i})" for i in range(calls))
        with pytest.raises(UnsafeExpressionError, match="llamadas|Profundidad|nodos"):
            safe_eval(expr)


# ===================================================================
# Grupo G — _SafeEvalChecker (acceso directo)
# ===================================================================

class TestSafeEvalChecker:
    def test_collects_names_from_expression(self) -> None:
        tree = ast.parse("x + y", mode="eval")
        checker = _SafeEvalChecker()
        checker.visit(tree)
        assert checker.names == {"x", "y"}

    def test_collects_names_in_context(self) -> None:
        tree = ast.parse("a + b + c", mode="eval")
        checker = _SafeEvalChecker()
        checker.visit(tree)
        assert checker.names == {"a", "b", "c"}

    def test_empty_expression_raises_syntax_error(self) -> None:
        with pytest.raises(SyntaxError):
            ast.parse("", mode="eval")

    def test_rejects_blocked_node(self) -> None:
        checker = _SafeEvalChecker()
        node = ast.Lambda(  # type: ignore[arg-type]
            args=ast.arguments(
                posonlyargs=[], args=[ast.arg(arg="x")], kwonlyargs=[], kw_defaults=[], defaults=[],
            ),
            body=ast.Constant(value=None),
        )
        with pytest.raises(UnsafeExpressionError, match="Nodo no permitido"):
            checker.visit(node)


# ===================================================================
# Grupo H — _eval_ast directamente (casos borde)
# ===================================================================

class TestEvalAstEdgeCases:
    def test_constant_none(self) -> None:
        result = _eval_ast(ast.Constant(value=None), {})
        assert result is None

    def test_list_of_expressions(self) -> None:
        tree = ast.parse("[1, 2, 3]", mode="eval")
        result = _eval_ast(tree.body, {})
        assert result == [1, 2, 3]

    def test_nested_ifexp(self) -> None:
        tree = ast.parse("1 if True else (2 if False else 3)", mode="eval")
        result = _eval_ast(tree.body, {})
        assert result == 1
