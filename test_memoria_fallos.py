"""Test memoria_fallos."""
import sys, pytest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from memoria_fallos import MemoriaFallos

def test_aislado():
    m = MemoriaFallos("p1")
    m.registrar("timeout", "tardo")
    assert not m.es_patron("timeout")

def test_patron():
    m = MemoriaFallos("p2")
    for _ in range(3):
        m.registrar("timeout", "x")
    assert m.es_patron("timeout")

def test_corta():
    m = MemoriaFallos("p3", max_fallos=5)
    for i in range(8):
        m.registrar(f"f{i}", str(i))
    assert len(m.fallos_recientes()) == 5
    assert "f0" not in [x.tipo for x in m.fallos_recientes()]

def test_arreglo():
    m = MemoriaFallos("p4")
    m.registrar("err", "msg", arreglo="hacer X")
    assert m.arreglo_conocido("err") == "hacer X"
    assert m.arreglo_conocido("otro") is None

def test_detectar():
    m = MemoriaFallos("p5")
    m.registrar("raro", "a")
    for _ in range(3):
        m.registrar("comun", "b")
    assert m.hay_patron_activo() == "comun"

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
