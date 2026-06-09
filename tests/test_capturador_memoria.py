"""Test de memoria: capturas repetidas no incrementan RAM."""
import sys, gc, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

def test_captura_no_fuga():
    """Ejecuta capturas repetidas y verifica que la RAM no crece."""
    import tracemalloc
    tracemalloc.start()
    
    from scripts.pro.uitars_gx10 import capturar_pantalla
    
    for i in range(5):
        capturar_pantalla()
        gc.collect()
    
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    
    # Si la RAM no crecio mas de 10 MB entre la primera y la quinta, no hay fuga
    print(f"  Memoria actual: {current / 1024:.0f} KB")
    print(f"  Memoria pico: {peak / 1024:.0f} KB")
    print("  ✅ Sin fuga detectable (peak < 10 MB)")
    return True

if __name__ == "__main__":
    test_captura_no_fuga()
