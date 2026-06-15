import json, os, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config import UraConfig
from core.state import ScanResult

def _make_trends(path, puntos=10, health=99.0, ram=50.0, disk=60.0):
    lines = []
    for i in range(puntos):
        lines.append(json.dumps({"ts": f"2026-06-15T0{i:02d}:00:00Z", "hostname": "test",
                                  "health": health + i * 0.1, "incidentes": 0,
                                  "ram_pct": ram, "disk_pct": disk, "load": 0.5,
                                  "ok": True}))
    lines.append(json.dumps({"ts": "2026-06-15T10:00:00Z", "hostname": "test",
                              "health": health + puntos * 0.1, "incidentes": 0,
                              "ram_pct": ram, "disk_pct": disk, "load": 0.5,
                              "ok": True, "perf": {"scan_s": 1.2, "diag_s": 0.1, "ver_s": 0.0, "total_s": 1.3}}))
    Path(path).write_text("\n".join(lines) + "\n")

def test_detect_no_trends():
    from scanner.calibration import Calibration
    cfg = UraConfig()
    cal = Calibration(cfg)
    res = cal.detect([])
    assert res["ok"] == True
    assert len(res["anomalias"]) == 0

def test_detect_with_trends():
    from scanner.calibration import Calibration
    cfg = UraConfig()
    cal = Calibration(cfg)
    trends = [{"ram_pct": 50, "disk_pct": 60, "load_1m": 0.5},
              {"ram_pct": 51, "disk_pct": 61, "load_1m": 0.5},
              {"ram_pct": 80, "disk_pct": 62, "load_1m": 0.5}]
    res = cal.detect(trends)
    anomalias = [a for a in res["anomalias"] if a["metrica"] == "ram_pct"]
    assert len(anomalias) > 0

def test_calibration_with_trends():
    from scanner.calibration import Calibration
    cfg = UraConfig()
    cfg.data_dir = tempfile.mkdtemp()
    cal = Calibration(cfg)
    trends = [{"ram_pct": 50, "disk_pct": 60, "load_1m": 0.5}]
    estado = ScanResult(ok=True, timestamp="test")
    estado.recursos = {"ram_pct": 50, "disk_pct": 60, "load_1m": 0.5, "ram_gb": 16, "ram_available_gb": 8, "disk_gb": 100, "disk_free_gb": 40, "ncpu": 8}
    bl = cal.learn(estado, trends)
    assert "ram_pct_max" in bl

def test_pattern_matcher_empty():
    from diagnostico.pattern_matcher import buscar_patrones
    scan = ScanResult(ok=True, timestamp="test")
    scan.servicios = {"sshd": "active", "docker": "active"}
    scan.recursos = {"ram_pct": 50, "disk_pct": 50, "load_1m": 0.5, "ncpu": 8}
    scan.red = {"internet": True, "exit_node_online": True}
    scan.hw_health = {"ok": True, "tipo": "vm", "dmesg_errors": [], "journal_corrupt": 0}
    scan.duplicados = {}
    scan.flapping = []
    scan.contenedores_ko = []
    scan.diff_total = 0
    cfg = UraConfig()
    incidents, costs = buscar_patrones(scan, None, None, cfg)
    assert len(incidents) == 0

def test_pattern_matcher_failure():
    from diagnostico.pattern_matcher import buscar_patrones
    scan = ScanResult(ok=True, timestamp="test")
    scan.servicios = {"sshd": "failed", "docker": "active"}
    scan.recursos = {"ram_pct": 95, "disk_pct": 90, "load_1m": 10.0, "ncpu": 2}
    scan.red = {"internet": False, "exit_node_online": False}
    scan.hw_health = {"ok": False, "tipo": "vm", "dmesg_errors": ["OOM"], "journal_corrupt": 1}
    scan.duplicados = {"python3": 3}
    scan.flapping = ["sshd"]
    scan.contenedores_ko = ["agent-foo"]
    scan.diff_total = 5
    cfg = UraConfig()
    incidents, costs = buscar_patrones(scan, None, None, cfg)
    assert len(incidents) >= 5
    tipos = set(i["tipo"] for i in incidents)
    assert "ServiceFailure" in tipos
    assert "ResourcePressure" in tipos
    assert "ConfigConflict" in tipos
    assert "HardwareFailure" in tipos

def test_correlacion():
    from diagnostico.correlacion import agrupar_incidentes
    tags = ["ServiceFailure", "docker"]
    r = agrupar_incidentes(tags, hw_ok=True, hw_issues=[])
    assert isinstance(r, list)

def test_sliding_window():
    from scanner.sliding_window import SlidingWindow
    sw = SlidingWindow()
    assert sw is not None

def test_diff_detector():
    from scanner.diff_detector import compute_diff
        actual = {"servicios": {"sshd": "active", "docker": "inactive"},
                  "recursos": {"ram_pct": 95.0},
                  "contenedores": {"total": 2},
                  "hw_health": {"ok": True}}
        prev = {"servicios": {"sshd": "active", "docker": "active"},
                "recursos": {"ram_pct": 50.0},
                "contenedores": {"total": 2},
                "hw_health": {"ok": True}}
        diff, anomalias = compute_diff(actual, prev)
        assert diff > 0
        assert len(anomalias) > 0  # docker inactive + ram 95%
