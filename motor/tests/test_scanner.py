import tempfile
from pathlib import Path
from motor.scanner.diff_detector import compute_diff
from motor.diagnostico.correlacion import agrupar_incidentes, resumir_incidentes
from motor.scanner.calibration import Calibration
from motor.core.config import UraConfig

def test_diff():
    p={"servicios":{"ssh":"ok","docker":"ok"},"recursos":{"ram_pct":45,"disk_pct":60,"load_1m":0.5},
       "contenedores":{"running":4},"hw_health":{"ok":True}}
    c={"servicios":{"ssh":"ok","docker":"failed"},"recursos":{"ram_pct":45,"disk_pct":71,"load_1m":0.5},
       "contenedores":{"running":3},"hw_health":{"ok":False}}
    cnt, anom = compute_diff(c, p)
    assert cnt >= 3
    assert any("docker" in a for a in anom)
    assert any("hw_health" in a for a in anom)
    print("  ✅ test_diff")

def test_correlacion():
    g = agrupar_incidentes(["docker", "exit_node_offline"], hw_ok=False, hw_issues=["dmesg error"])
    causas = [x["causa_raiz"] for x in g]
    assert "hardware" in causas
    g2 = agrupar_incidentes(["docker"], hw_ok=True)
    assert "docker" in [x["causa_raiz"] for x in g2]
    assert resumir_incidentes([]) == "Sin incidencias activas"
    assert "docker" in resumir_incidentes([{"tipo": "ServiceFailure", "subtipo": "docker"}])
    print("  ✅ test_correlacion")

def test_calibration():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = UraConfig()
        cfg.data_dir = tmp
        cfg.baseline_path = str(Path(tmp) / "baseline.json")
        cal = Calibration(cfg)
        assert not cal.hay_baseline
        class FakeScan:
            recursos = {"ram_pct": 45, "disk_pct": 60, "load_1m": 0.5}
        cal.learn(FakeScan())
        cal2 = Calibration(cfg)
        assert cal2.hay_baseline
        assert cal2._baseline.get("ram_pct_max", 0) > 0
    print("  ✅ test_calibration")

if __name__ == "__main__":
    test_diff(); test_correlacion(); test_calibration()
    print("🎯 Todos OK")
