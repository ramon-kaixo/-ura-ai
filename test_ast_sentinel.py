"""Test AST Sentinel."""
import pytest
from core.guardians.ast_sentinel import ASTSentinel

s = ASTSentinel()

def test_limpio():
    v = s.analizar('def f(a:int,b:int)->int:\n """S"""\n return a+b', "b")
    assert v.ok

def test_malo():
    v = s.analizar('def f():\n try:\n  pass\n except:\n  pass', "m")
    assert not v.ok

def test_sin_tipos():
    v = s.analizar('def f(a,b):\n return a', "s")
    assert not v.ok

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
