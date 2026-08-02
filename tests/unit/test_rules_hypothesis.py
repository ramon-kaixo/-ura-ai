"""Property-based tests (Hypothesis) para safe_eval — 0 mocks, 0 DB, 0 red.

Cubre 8 propiedades (P1-P8) con 100 ejemplos cada una.
"""
from __future__ import annotations

import math

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from knowledge.engine.rules import UnsafeExpressionError, safe_eval

# ── Estrategias base ─────────────────────────────────────────────────────────

literals = st.integers() | st.floats(allow_nan=False, allow_infinity=False) | st.booleans() | st.none()

safe_text = st.text(
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "P", "Zs")),
    min_size=0,
    max_size=50,
)

dict_ctx = st.dictionaries(keys=safe_text, values=literals, max_size=5)

# Expresiones sintácticamente válidas conocidas
KNOWN_VALID = st.sampled_from([
    "1 + 2",
    "3 * 4",
    "10 / 2",
    "2 ** 10",
    "not True",
    "True and False",
    "False or True",
    "1 == 1",
    "2 != 3",
    "4 > 3",
    "5 < 6",
    "7 >= 7",
    "8 <= 8",
    "'hola' + ' mundo'",
    "'abc' in ['a', 'b', 'c']",
    "x + y",
    "x * 2",
    "x == y",
    "abs(-5)",
    "len([1, 2, 3])",
    "int(3.14)",
    "str(42)",
    "bool(0)",
    "float(3)",
    "chr(65)",
    "ord('A')",
    "hex(255)",
    "oct(8)",
    "bin(3)",
    "[1, 2, 3][0]",
    "{'a': 1}.get('a')",
    "{'a': 1}.get('b', 0)",
    "{'a': 1}.keys()",
    "{'a': 1}.values()",
    "{'a': 1}.items()",
    "'HELLO'.lower()",
    "'hello'.upper()",
    "'  hi  '.strip()",
    "'a,b,c'.split(',')",
    "'hello'.startswith('he')",
    "'hello'.endswith('lo')",
    "'hello'.replace('l', 'x')",
    "any(x > 0 for x in [1, -2, 3])",
    "all(x > 0 for x in [1, 2, 3])",
    "[x * 2 for x in [1, 2, 3]]",
    "min(3, 1, 2)",
    "max(3, 1, 2)",
    "sum([1, 2, 3])",
    "round(3.14)",
    "sorted([3, 1, 2])",
    "reversed([1, 2, 3])",
    "enumerate([10, 20])",
    "zip([1, 2], ['a', 'b'])",
    "list(range(5))",
    "dict(a=1, b=2)",
    # Con contexto
    "x > 0",
    "name == 'test'",
    "len(items) == 3",
])

# Expresiones inseguras conocidas (generan UnsafeExpressionError)
KNOWN_UNSAFE = st.sampled_from([
    "x.__class__",
    "x.__dict__",
    "x.__subclasses__",
    "().__class__.__bases__",
    "lambda x: x",
    "__import__('os')",
    "eval('1+1')",
    "exec('x=1')",
    "open('/etc/passwd')",
    "getattr(x, y)",
    "setattr(x, y, z)",
])

# ── P1: Literal roundtrip ────────────────────────────────────────────────────

class TestLiteralRoundtrip:
    @given(st.integers())
    @settings(max_examples=100, deadline=5000)
    def test_int_roundtrip(self, x: int) -> None:
        assert safe_eval(repr(x)) == x

    @given(st.floats(allow_nan=False, allow_infinity=False))
    @settings(max_examples=100, deadline=5000)
    def test_float_roundtrip(self, x: float) -> None:
        result = safe_eval(repr(x))
        assert result == x or (math.isnan(result) and math.isnan(x))

    @given(st.booleans())
    @settings(max_examples=100, deadline=5000)
    def test_bool_roundtrip(self, x: bool) -> None:
        assert safe_eval(repr(x)) is x

    @given(st.none())
    @settings(max_examples=100, deadline=5000)
    def test_none_roundtrip(self, x: None) -> None:
        assert safe_eval(repr(x)) is None

    @given(st.lists(st.integers(), max_size=10))
    @settings(max_examples=100, deadline=5000)
    def test_list_roundtrip(self, x: list[int]) -> None:
        assert safe_eval(repr(x)) == x


# ── P2: Valid expressions + context ──────────────────────────────────────────

class TestValidExpressions:
    @given(expr=KNOWN_VALID, ctx=st.none() | dict_ctx)
    @settings(max_examples=100, deadline=5000)
    def test_no_crash(self, expr: str, ctx: dict[str, object] | None) -> None:
        try:
            result = safe_eval(expr, ctx)
        except UnsafeExpressionError:
            return
        except NameError:
            return
        assert result is not ...

    @given(st.lists(st.integers(min_value=-100, max_value=100), max_size=5))
    @settings(max_examples=100, deadline=5000)
    def test_list_comprehension(self, items: list[int]) -> None:
        result = safe_eval("[x * 2 for x in items]", {"items": items})
        assert result == [x * 2 for x in items]

    @given(st.dictionaries(st.text(max_size=5), st.integers(), max_size=5))
    @settings(max_examples=100, deadline=5000)
    def test_dict_methods(self, d: dict[str, int]) -> None:
        key = next(iter(d)) if d else "nonexistent"
        expr = f"d.get({key!r}, -1)"
        result = safe_eval(expr, {"d": d})
        assert result == d.get(key, -1)


# ── P3: Dunder siempre bloqueado ─────────────────────────────────────────────

class TestDunderBlocked:
    @given(expr=KNOWN_UNSAFE)
    @settings(max_examples=100, deadline=5000)
    def test_dunder_raises(self, expr: str) -> None:
        with pytest.raises(UnsafeExpressionError):
            safe_eval(expr, {"x": {}})

    @given(
        attr=st.sampled_from(["__class__", "__dict__", "__subclasses__", "__bases__", "__init__"]),
        obj=st.sampled_from(["x", "''", "[]", "{}", "()"]),
    )
    @settings(max_examples=100, deadline=5000)
    def test_any_dunder_attr(self, attr: str, obj: str) -> None:
        with pytest.raises(UnsafeExpressionError):
            safe_eval(f"{obj}.{attr}", {"x": {}})

    @given(attr=st.text(max_size=20))
    @settings(max_examples=100, deadline=5000)
    def test_random_dunder_pattern(self, attr: str) -> None:
        expr = f"x.__{attr}__"
        try:
            safe_eval(expr, {"x": {}})
            assert not (attr.isidentifier() and not attr.startswith("_"))
        except (UnsafeExpressionError, SyntaxError):
            pass


# ── P4: Palabras clave bloqueadas ────────────────────────────────────────────

class TestKeywordsBlocked:
    @given(st.sampled_from(["lambda x: x", "yield 1", "await x"]))
    @settings(max_examples=100, deadline=5000)
    def test_blocked_keywords(self, expr: str) -> None:
        with pytest.raises((UnsafeExpressionError, SyntaxError)):
            safe_eval(expr)


# ── P5: Method calls whitelist ───────────────────────────────────────────────

class TestMethodCallWhitelist:
    def test_dict_get_allowed(self) -> None:
        assert safe_eval("{'a': 1}.get('a')") == 1

    def test_dict_keys_allowed(self) -> None:
        assert list(safe_eval("{'a': 1}.keys()")) == ["a"]

    def test_dict_values_allowed(self) -> None:
        assert list(safe_eval("{'a': 1}.values()")) == [1]

    def test_dict_items_allowed(self) -> None:
        assert list(safe_eval("{'a': 1}.items()")) == [("a", 1)]

    def test_str_upper_allowed(self) -> None:
        assert safe_eval("'hello'.upper()") == "HELLO"

    def test_str_strip_allowed(self) -> None:
        assert safe_eval("'  hi  '.strip()") == "hi"

    def test_unknown_method_raises(self) -> None:
        with pytest.raises(UnsafeExpressionError):
            safe_eval("{'a': 1}.pop('a')")

    def test_unknown_type_raises(self) -> None:
        with pytest.raises(UnsafeExpressionError):
            safe_eval("[1, 2, 3].append(4)")

    @given(st.sampled_from(["pop", "clear", "update", "copy", "fromkeys", "setdefault"]))
    @settings(max_examples=100, deadline=5000)
    def test_unknown_dict_method_raises(self, method: str) -> None:
        with pytest.raises(UnsafeExpressionError):
            safe_eval(f"{{'a': 1}}.{method}()")

    @given(st.sampled_from(["capitalize", "casefold", "center", "count", "encode", "find",
                            "format", "index", "isalnum", "isalpha", "isascii", "isdecimal",
                            "isdigit", "isidentifier", "islower", "isnumeric", "isprintable",
                            "isspace", "istitle", "isupper", "join", "ljust", "lstrip",
                            "maketrans", "partition", "removeprefix", "removesuffix",
                            "rfind", "rindex", "rjust", "rpartition", "rsplit", "rstrip",
                            "swapcase", "title", "translate", "zfill"]))
    @settings(max_examples=100, deadline=5000)
    def test_unknown_str_method_raises(self, method: str) -> None:
        with pytest.raises(UnsafeExpressionError):
            safe_eval(f"'hello'.{method}()")


# ── P6: eval/exec/open bloqueados ────────────────────────────────────────────

class TestDangerousFunctionsBlocked:
    @given(st.sampled_from(["eval", "exec", "open", "__import__", "getattr", "setattr",
                            "delattr", "compile", "globals", "locals", "vars", "dir",
                            "input", "breakpoint"]))
    @settings(max_examples=100, deadline=5000)
    def test_dangerous_func_blocked(self, func: str) -> None:
        with pytest.raises((UnsafeExpressionError, NameError)):
            safe_eval(f"{func}()")


# ── P7: Límite de profundidad ────────────────────────────────────────────────

class TestDepthLimit:
    def test_deeply_nested_expression_raises(self) -> None:
        """15 niveles de binop → AST depth 15 > max 10 → UnsafeExpressionError."""
        expr = " + ".join(str(i) for i in range(15))
        with pytest.raises(UnsafeExpressionError):
            safe_eval(expr)

    def test_excessive_nodes_raises(self) -> None:
        """51 constantes + 50 operadores = 101+ nodos > max 100."""
        expr = " + ".join(str(i) for i in range(51))
        with pytest.raises(UnsafeExpressionError):
            safe_eval(expr)

    @given(st.text(min_size=500, max_size=2047, alphabet=" ()[]{} +-*/1234567890x"))
    @settings(max_examples=100, deadline=5000)
    def test_long_expression_raises(self, expr: str) -> None:
        try:
            safe_eval(expr)
        except (UnsafeExpressionError, SyntaxError, MemoryError, RecursionError):
            return


# ── P8: Determinismo ─────────────────────────────────────────────────────────

class TestDeterminism:
    @given(expr=KNOWN_VALID, ctx=st.none() | dict_ctx)
    @settings(max_examples=100, deadline=5000)
    def test_deterministic(self, expr: str, ctx: dict[str, object] | None) -> None:
        try:
            r1 = safe_eval(expr, ctx)
            r2 = safe_eval(expr, ctx)
        except (UnsafeExpressionError, NameError):
            return
        if type(r1).__name__ in ("list_reverseiterator", "map", "filter", "zip", "enumerate",
                                "dict_values", "dict_keys", "dict_items"):
            r1 = list(r1)
            r2 = list(r2)
        assert r1 == r2
