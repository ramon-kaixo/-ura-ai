import json, sys, logging
from pathlib import Path
from motor.core.config import UraConfig
from motor.pipeline.orchestrator import Orchestrator
from motor.scanner import Scanner
from motor.scanner.calibration import Calibration
from motor.core.qdrant_client import QdrantClient
from motor.diagnostico import Diagnostico
from motor.core.state import ScanResult

log = logging.getLogger("ura.cli")
ARCHIVO_TRENDS = "trends.ndjson"


def cmd_pipeline(config: UraConfig, args):
    orch = Orchestrator(config)
    r = orch.run(dry_run=args.dry_run)
    sys.exit(0 if r.ok else 1)


def cmd_scan(config: UraConfig, args=None):
    sc = Scanner(config)
    r = sc.run()
    print(json.dumps({"health_score": r.health_score, "servicios": r.servicios,
                       "recursos": r.recursos, "hw_ok": r.hw_health.get("ok"),
                       "red": r.red, "duplicados": r.duplicados}, indent=2, default=str))


def cmd_diagnose(config: UraConfig, args=None):
    qdrant = QdrantClient.instancia(config)
    diag = Diagnostico(config, qdrant)
    scan = ScanResult(ok=True, timestamp="")
    r = diag.run(scan)
    print(json.dumps({"ok": r.ok, "incidentes": r.incidentes, "causas_raiz": r.causas_raiz,
                       "modo_offline": r.modo_offline}, indent=2, default=str))


def cmd_calibrate(config: UraConfig, args):
    cal = Calibration(config)
    if cal.hay_baseline and not args.force:
        print(json.dumps({"error": "Baseline ya existe, usa --force para sobreescribir"}, indent=2))
        sys.exit(1)
    sc = Scanner(config)
    scan = sc.run()
    trend_path = Path(config.deploy_dir) / ARCHIVO_TRENDS
    trends = []
    if trend_path.exists():
        trends = [json.loads(l) for l in trend_path.read_text().strip().splitlines() if l.strip()]
    bl = cal.learn(scan, trends)
    print(json.dumps({"ok": True, "baseline": bl, "puntos_usados": len(trends)}, indent=2, default=str))
