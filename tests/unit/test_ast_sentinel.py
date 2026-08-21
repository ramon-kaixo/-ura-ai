"""Test AST Sentinel."""

import pytest

from core.guardians.ast_sentinel import ASTSentinel

s = ASTSentinel()


def test_limpio() -> None:
    v = s.analizar('def f(a:int,b:int)->int:\n """S"""\n return a+b', "b")
    assert v.ok


def test_malo() -> None:
    v = s.analizar("def f():\n try:\n  pass\n except:\n  pass", "m")
    assert not v.ok


def test_sin_tipos() -> None:
    v = s.analizar("def f(a,b):\n return a", "s")
    assert not v.ok


def test_cc_boolop_exacto() -> None:
    codigo = 'def f(a:int)->int:\n """d"""\n if a:\n  pass\n return a and a and a\n'
    v = s.analizar(codigo, "b")
    assert v.m["cc_max"] == 4


def test_cc_limite_max_cc() -> None:
    cuerpo9 = "".join(f" if a=={i}: a=i\n" for i in range(2, 11))
    v10 = s.analizar(f'def g(a:int)->int:\n """d"""\n{cuerpo9} return a\n', "g")
    assert v10.m["cc_max"] == 10
    assert not any("CC" in e for e in v10.errs)
    cuerpo10 = "".join(f" if a=={i}: a=i\n" for i in range(2, 12))
    v11 = s.analizar(f'def g(a:int)->int:\n """d"""\n{cuerpo10} return a\n', "g")
    assert any("CC" in e for e in v11.errs)


def test_sin_doc_solo_en_prod() -> None:
    sin_doc = "def f(a:int)->int:\n return a\n"
    v_dev = s.analizar(sin_doc, "dev", prod=False)
    assert not any("sin doc" in w for w in v_dev.warns)
    v_prod = s.analizar(sin_doc, "prod", prod=True)
    assert any("sin doc" in w for w in v_prod.warns)


def test_cc_max_retornado() -> None:
    codigo = 'def f(a:int)->int:\n """d"""\n if a:\n  a=2\n return a\n'
    v = s.analizar(codigo, "b")
    assert v.m["cc_max"] == 2


def test_magic_whitelist_no_avisa() -> None:
    codigo = 'def h(a:int)->bool:\n """d"""\n x=0\n y=1\n z=-1\n w=2\n t=True\n u=False\n return t or u or bool(a)\n'
    v = s.analizar(codigo, "h")
    assert not any("magic" in w for w in v.warns)


def test_magic_detecta_constante() -> None:
    codigo = 'def q(a:int)->int:\n """d"""\n return a*42\n'
    v = s.analizar(codigo, "q")
    assert any("magic 42" in w for w in v.warns)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
