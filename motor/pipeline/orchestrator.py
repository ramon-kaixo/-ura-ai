import json, logging, sys
from datetime import datetime
from pathlib import Path
from core.config import UraConfig
from core.state import PipelineResult
from core.qdrant_client import QdrantClient
from scanner import Scanner
from diagnostico import Diagnostico
from guard.preflight import ejecutar_preflight
from guard.verifier import ejecutar_verificacion

log = logging.getLogger("ura.pipeline")

class Orchestrator:
    def __init__(self, config: UraConfig):
        self.config = config
        self.qdrant = QdrantClient.instancia(config)

    def run(self, dry_run: bool = False) -> PipelineResult:
        result = PipelineResult(timestamp=datetime.utcnow().isoformat()+"Z")
        try:
            result.preflight = ejecutar_preflight(self.config)
            if result.preflight.bloqueado:
                result.ok = False
                result.error = f"Preflight bloqueado: {result.preflight.razon}"
                log.warning(result.error)
                self._emit(result)
                return result
            if dry_run:
                log.info("dry-run: pipeline OK hasta preflight")
                result.ok = True
                self._emit(result)
                return result
            scanner = Scanner(self.config)
            result.scan = scanner.run()
            if not result.scan.ok:
                log.warning("scan reporta no ok")
            diagnostico = Diagnostico(self.config, self.qdrant)
            result.diagnose = diagnostico.run(result.scan)
            hubo_cambios = result.diagnose.causas_raiz or result.scan.diff_total > 0
            result.verify = ejecutar_verificacion(self.config, hubo_cambios=hubo_cambios)
            self._escribir_side_effects(result)
            self._registrar_trend(result)
            result.ok = True
            log.info("pipeline OK health=%.1f incidentes=%d",
                     result.scan.health_score, len(result.diagnose.incidentes))
        except Exception as e:
            result.ok = False
            result.error = str(e)
            log.error("pipeline error: %s", e, exc_info=True)
        self._emit(result)
        return result

    def _registrar_trend(self, result: PipelineResult):
        if not result.scan:
            return
        dep = Path(self.config.deploy_dir)
        dep.mkdir(parents=True, exist_ok=True)
        entry = {"ts": result.scan.timestamp, "hostname": result.scan.hostname,
                 "health": result.scan.health_score,
                 "incidentes": len(result.diagnose.incidentes) if result.diagnose else 0,
                 "ram_pct": result.scan.recursos.get("ram_pct", 0),
                 "disk_pct": result.scan.recursos.get("disk_pct", 0),
                 "load": result.scan.recursos.get("load_avg_1m", 0),
                 "ok": result.ok}
        lines = (dep / "trends.ndjson")
        with open(lines, "a") as f:
            f.write(json.dumps(entry, default=str) + "\n")

    def _escribir_side_effects(self, result: PipelineResult):
        dep = Path(self.config.deploy_dir)
        dep.mkdir(parents=True, exist_ok=True)
        if result.scan:
            s = {"timestamp": result.scan.timestamp, "hostname": result.scan.hostname,
                 "health_score": result.scan.health_score, "servicios": result.scan.servicios,
                 "recursos": result.scan.recursos, "red": result.scan.red,
                 "hw_health": result.scan.hw_health}
            (dep / "estado_alemania.json").write_text(json.dumps(s, indent=2))
        if result.diagnose:
            d = {"timestamp": result.diagnose.timestamp,
                 "ok": result.diagnose.ok,
                 "incidentes": result.diagnose.incidentes,
                 "causas_raiz": result.diagnose.causas_raiz,
                 "modo_offline": result.diagnose.modo_offline,
                 "coste_historico": result.diagnose.coste_historico}
            (dep / "diagnostico.json").write_text(json.dumps(d, indent=2))

    def _emit(self, result: PipelineResult):
        print(json.dumps({"ura": "pipeline", "ok": result.ok,
                          "ts": result.timestamp,
                          "error": result.error,
                          "health_score": result.scan.health_score if result.scan else None,
                          "incidentes": len(result.diagnose.incidentes) if result.diagnose else 0},
                         default=str), flush=True)
