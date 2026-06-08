"""Test de la Memoria 3 (movimiento / cubos)."""
import sys
from memoria_movimiento import MemoriaMovimiento

def ok(m): print(f"  \033[92m{chr(10003)}\033[0m {m}")
def ng(m): print(f"  \033[91m{chr(10007)}\033[0m {m}")

class RelojFalso:
    def __init__(self): self.t = 1000.0
    def __call__(self): return self.t
    def avanzar(self, s): self.t += s

print("\n=== TEST DE LA MEMORIA DE MOVIMIENTO (cubos) ===\n")
e = 0

print("Prueba 1: Cubo va y vuelve a tiempo")
try:
    m = MemoriaMovimiento("enricher", tiempo_max_s=30)
    r = RelojFalso(); m._reloj = r
    m.mandar_cubo("c1", "indexer")
    r.avanzar(5)
    m.cubo_volvio("c1")
    assert m.circulo_sano() is True
    ok("Cubo volvio a tiempo, circulo sano")
except Exception as ex: ng(f"P1: {ex}"); e += 1

print("\nPrueba 2: Cubo no vuelve a tiempo")
try:
    m = MemoriaMovimiento("enricher", tiempo_max_s=30)
    r = RelojFalso(); m._reloj = r
    m.mandar_cubo("c2", "indexer")
    r.avanzar(45)
    assert m.circulo_sano() is False
    assert "indexer" in m.nodos_atascados()
    ok("Cubo no volvio, alarma y senala nodo")
except Exception as ex: ng(f"P2: {ex}"); e += 1

print("\nPrueba 3: 3 cubos, 1 se atasca")
try:
    m = MemoriaMovimiento("enricher", tiempo_max_s=30)
    r = RelojFalso(); m._reloj = r
    m.mandar_cubo("a", "i"); m.mandar_cubo("b", "g"); m.mandar_cubo("c", "aud")
    r.avanzar(10)
    m.cubo_volvio("a"); m.cubo_volvio("c")
    r.avanzar(40)
    rotos = m.cubos_sin_volver()
    assert len(rotos) == 1 and rotos[0].id_cubo == "b"
    ok("Detecta que solo cubo_b (guardian) se atascó")
except Exception as ex: ng(f"P3: {ex}"); e += 1

print("\nPrueba 4: Cubo que vuelve se olvida")
try:
    m = MemoriaMovimiento("enricher", tiempo_max_s=30)
    r = RelojFalso(); m._reloj = r
    m.mandar_cubo("cx", "indexer")
    m.cubo_volvio("cx")
    r.avanzar(100)
    assert m.circulo_sano() is True
    ok("Cubo que volvio no queda en memoria")
except Exception as ex: ng(f"P4: {ex}"); e += 1

print("\n" + "=" * 40)
if e == 0: print("\033[92m  TODO OK \u2014 la memoria de movimiento funciona\033[0m")
else: print(f"\033[91m  {e} FALLO(S)\033[0m")
print("=" * 40 + "\n")
sys.exit(e)
