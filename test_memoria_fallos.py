"""Test de la Memoria 2 (fallos y arreglos)."""
import sys
from memoria_fallos import MemoriaFallos

def ok(m): print(f"  \033[92m{chr(10003)}\033[0m {m}")
def ng(m): print(f"  \033[91m{chr(10007)}\033[0m {m}")

print("\n=== TEST DE LA MEMORIA DE FALLOS ===\n")
e = 0

print("Prueba 1: Un fallo solo no es patron")
try:
    m = MemoriaFallos("p1")
    m.registrar("timeout", "tardo")
    assert m.es_patron("timeout") is False
    ok("Un fallo aislado no salta la alarma")
except Exception as ex: ng(f"P1: {ex}"); e += 1

print("\nPrueba 2: 3 fallos iguales = patron")
try:
    m = MemoriaFallos("p2")
    for _ in range(3): m.registrar("timeout", "x")
    assert m.es_patron("timeout") is True
    ok("3 fallos iguales saltan alarma")
except Exception as ex: ng(f"P2: {ex}"); e += 1

print("\nPrueba 3: Memoria corta (solo 5)")
try:
    m = MemoriaFallos("p3", max_fallos=5)
    for i in range(8): m.registrar(f"f{i}", str(i))
    assert len(m.fallos_recientes()) == 5
    assert "f0" not in [x.tipo for x in m.fallos_recientes()]
    ok("Solo guarda 5, los viejos se olvidan")
except Exception as ex: ng(f"P3: {ex}"); e += 1

print("\nPrueba 4: Recuerda arreglo")
try:
    m = MemoriaFallos("p4")
    m.registrar("err", "msg", arreglo="hacer X")
    assert m.arreglo_conocido("err") == "hacer X"
    assert m.arreglo_conocido("otro") is None
    ok("Recuerda el arreglo")
except Exception as ex: ng(f"P4: {ex}"); e += 1

print("\nPrueba 5: Detecta cual es el patron")
try:
    m = MemoriaFallos("p5")
    m.registrar("raro", "a")
    for _ in range(3): m.registrar("comun", "b")
    assert m.hay_patron_activo() == "comun"
    ok("Identifica el fallo patron")
except Exception as ex: ng(f"P5: {ex}"); e += 1

print("\n" + "=" * 40)
if e == 0: print("\033[92m  TODO OK \u2014 la memoria de fallos funciona\033[0m")
else: print(f"\033[91m  {e} FALLO(S)\033[0m")
print("=" * 40 + "\n")
sys.exit(e)
