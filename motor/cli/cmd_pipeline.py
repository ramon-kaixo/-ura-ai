import json
import logging
import sys
from pathlib import Path

from motor.core.config import UraConfig
from motor.core.qdrant_client import QdrantClient
from motor.core.state import ScanResult
from motor.diagnostico import Diagnostico
from motor.pipeline.orchestrator import Orchestrator
from motor.scanner import Scanner
from motor.scanner.calibration import Calibration

log = logging.getLogger("ura.cli")
ARCHIVO_TRENDS = "trends.ndjson"


def cmd_pipeline(config: UraConfig, args) -> None:
    orch = Orchestrator(config)
    r = orch.run(dry_run=args.dry_run)
    sys.exit(0 if r.ok else 1)


def cmd_scan(config: UraConfig, args=None) -> None:
    sc = Scanner(config)
    sc.run()


def cmd_diagnose(config: UraConfig, args=None) -> None:
    qdrant = QdrantClient.instancia(config)
    diag = Diagnostico(config, qdrant)
    scan = ScanResult(ok=True, timestamp="")
    diag.run(scan)


def cmd_calibrate(config: UraConfig, args) -> None:
    cal = Calibration(config)
    if cal.hay_baseline and not args.force:
        sys.exit(1)
    sc = Scanner(config)
    scan = sc.run()
    trend_path = Path(config.deploy_dir) / ARCHIVO_TRENDS
    trends = []
    if trend_path.exists():
        trends = [json.loads(l) for l in trend_path.read_text().strip().splitlines() if l.strip()]
    cal.learn(scan, trends)
