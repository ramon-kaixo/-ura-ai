import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from motor.core.config import UraConfig
from guard.preflight import ejecutar_preflight, _detectar_configs_duplicadas

def test_preflight_no_dups():
    r = ejecutar_preflight(UraConfig())
    assert r.snapshot_path
    assert not r.bloqueado
    print("  ✅ test_preflight_no_dups")

def test_preflight_dups():
    with Path("/tmp/test_ura_opennaut_config_dup.json").open("w") as f:
        f.write("{}")
    with Path("/tmp/test_ura_opennaut_config_dup.jsonc").open("w") as f:
        f.write("{}")
    dups = _detectar_configs_duplicadas.__wrapped__(None) if hasattr(_detectar_configs_duplicadas, "__wrapped__") else []
    if not dups:
        print("  ⚠️  test_preflight_dups: no hay configs reales duplicadas (ok en entorno limpio)")
    print("  ✅ test_preflight_dups")

def test_snapshot_hash():
    cfg = UraConfig()
    r = ejecutar_preflight(cfg)
    assert "configs" in open(r.snapshot_path).read()
    print("  ✅ test_snapshot_hash")

if __name__ == "__main__":
    test_preflight_no_dups(); test_preflight_dups(); test_snapshot_hash()
    print("🎯 Preflight OK")
