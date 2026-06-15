import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.config import UraConfig
from diagnostico.correlacion import agrupar_incidentes
from pipeline.orchestrator import Orchestrator
from scanner.diff_detector import compute_diff


def test_pipeline_orchestrator_init() -> None:
    cfg = UraConfig()
    from core.qdrant_client import QdrantClient
    qdrant = QdrantClient.instancia(cfg)
    assert qdrant is not None

def test_pipeline_in_memory_state() -> None:
    cfg = UraConfig()
    orch = Orchestrator(cfg)
    r = orch.run(dry_run=True)
    assert r.preflight is not None
    assert r.ok
    assert r.scan is None  # dry-run

def test_diff_in_pipeline() -> None:
    p = {"servicios":{"ssh":"ok","docker":"ok"},"recursos":{"ram_pct":45},"contenedores":{"running":4},"hw_health":{"ok":True}}
    c = {"servicios":{"ssh":"ok","docker":"failed"},"recursos":{"ram_pct":71},"contenedores":{"running":3},"hw_health":{"ok":False}}
    cnt, _anom = compute_diff(c, p)
    assert cnt > 0

def test_correlacion_root_cause() -> None:
    g = agrupar_incidentes(["docker", "exit_node_offline"], hw_ok=False, hw_issues=["dmesg error"])
    causas = [x["causa_raiz"] for x in g]
    assert "hardware" in causas or "exit_node_offline" in causas

if __name__ == "__main__":
    test_pipeline_orchestrator_init()
    test_pipeline_in_memory_state()
    test_diff_in_pipeline()
    test_correlacion_root_cause()
