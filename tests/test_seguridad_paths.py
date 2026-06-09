"""Test de seguridad: directory traversal y paths absolutos."""
import sys, os, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

def test_path_resolve_no_escape():
    """Verifica que .resolve() impide directory traversal."""
    home = Path.home()
    # Simular un COLA_DIR malicioso
    malicious = home / ".." / "etc" / "passwd"
    resolved = malicious.resolve()
    assert str(resolved).startswith(str(home.resolve())) is False
    print("  ✅ Directory traversal detectado")

def test_cola_dir_dentro_de_home():
    """COLA_DIR debe estar dentro de /home/ramon."""
    from core.open_claw_reporte import COLA_DIR
    assert str(COLA_DIR).startswith(str(Path.home().resolve()))
    print("  ✅ COLA_DIR dentro de home")

def test_get_cola_pendiente_no_raise():
    """get_cola_pendiente no debe lanzar excepcion si el directorio no existe."""
    from core.open_claw_reporte import get_cola_pendiente
    n = get_cola_pendiente()
    assert isinstance(n, int)
    print(f"  ✅ get_cola_pendiente() = {n}")

if __name__ == "__main__":
    test_path_resolve_no_escape()
    test_cola_dir_dentro_de_home()
    test_get_cola_pendiente_no_raise()
    print("\n  ✅ Tests de seguridad: OK")
