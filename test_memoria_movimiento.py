"""Test memoria_movimiento."""
import pytest
from memoria_movimiento import MemoriaMovimiento

class RelojFalso:
    def __init__(self): self.t = 1000.0
    def __call__(self): return self.t
    def avanzar(self, s): self.t += s

def test_vuelve():
    m = MemoriaMovimiento("enricher", tiempo_max_s=30)
    r = RelojFalso(); m._reloj = r
    m.mandar_cubo("c1", "indexer")
    r.avanzar(5)
    m.cubo_volvio("c1")
    assert m.circulo_sano() is True

def test_no_vuelve():
    m = MemoriaMovimiento("enricher", tiempo_max_s=30)
    r = RelojFalso(); m._reloj = r
    m.mandar_cubo("c2", "indexer")
    r.avanzar(45)
    assert m.circulo_sano() is False
    assert "indexer" in m.nodos_atascados()

def test_tres_cubos():
    m = MemoriaMovimiento("enricher", tiempo_max_s=30)
    r = RelojFalso(); m._reloj = r
    m.mandar_cubo("a", "i"); m.mandar_cubo("b", "g"); m.mandar_cubo("c", "aud")
    r.avanzar(10)
    m.cubo_volvio("a"); m.cubo_volvio("c")
    r.avanzar(40)
    rotos = m.cubos_sin_volver()
    assert len(rotos) == 1 and rotos[0].id_cubo == "b"

def test_olvida():
    m = MemoriaMovimiento("enricher", tiempo_max_s=30)
    r = RelojFalso(); m._reloj = r
    m.mandar_cubo("cx", "indexer")
    m.cubo_volvio("cx")
    r.avanzar(100)
    assert m.circulo_sano() is True

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
