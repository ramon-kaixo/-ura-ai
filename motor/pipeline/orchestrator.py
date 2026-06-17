import json, logging, time
from datetime import datetime
from pathlib import Path
from motor.core.config import UraConfig
from motor.core.state import PipelineResult
from motor.core.qdrant_client import QdrantClient
from scanner import Scanner
from diagnostico import Diagnostico
from guard.preflight import ejecutar_preflight
from guard.verifier import ejecutar_verificacion

log = logging.getLogger("ura.pipeline")
ALERT_LOG = logging.getLogger("ura.alerta")

ARCHIVO_ESTADO = "estado_alemania.json"
ARCHIVO_DIAGNOSTICO = "diagnostico.json"
ARCHIVO_TRENDS = "trends.ndjson"

class Orchestrator:
    """Orquestador del pipeline: preflight → scan → diagnose → verify."""

    def __init__(self, config: UraConfig):
        self.config = config
        self.qdrant = QdrantClient.instancia(config)

    def run(self, dry_run: bool = False) -> PipelineResult:
        """Ejecuta el pipeline completo."""
        result = PipelineResult(timestamp=datetime.utcnow().isoformat()+"Z")
        t_total = time.time()
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
            t1 = time.time()
            scanner = Scanner(self.config)
            result.scan = scanner.run()
            t_scan = time.time() - t1
            if not result.scan.ok:
                log.warning("scan reporta no ok")
            t2 = time.time()
            diagnostico = Diagnostico(self.config, self.qdrant)
            result.diagnose = diagnostico.run(result.scan)
            t_diag = time.time() - t2
            hubo_cambios = result.diagnose.causas_raiz or result.scan.diff_total > 0
            t3 = time.time()
            result.verify = ejecutar_verificacion(self.config, hubo_cambios=hubo_cambios)
            t_ver = time.time() - t3
            self._escribir_side_effects(result)
            self._registrar_trend(result, {"scan_s": round(t_scan, 1), "diag_s": round(t_diag, 1),
                                            "ver_s": round(t_ver, 1), "total_s": round(time.time() - t_total, 1)})
            hs = result.scan.health_score
            inc = len(result.diagnose.incidentes)
            if hs < 90 or inc > 0:
                ALERT_LOG.error("ALERTA health=%.1f incidentes=%d host=%s",
                                hs, inc, result.scan.hostname)
            result.ok = True
            log.info("pipeline OK health=%.1f incidentes=%d (%.1fs)", hs, inc, time.time() - t_total)
        except Exception as e:
            result.ok = False
            result.error = str(e)
            log.error("pipeline error: %s", e, exc_info=True)
        self._emit(result)
        return result

    def _registrar_trend(self, result: PipelineResult, perf: dict = None):
        """Registra métricas de tendencia a disco."""
        if not result.scan:
            return
        dep = Path(self.config.deploy_dir)
        dep.mkdir(parents=True, exist_ok=True)
        entry = {"ts": result.scan.timestamp, "hostname": result.scan.hostname,
                 "health": result.scan.health_score,
                 "incidentes": len(result.diagnose.incidentes) if result.diagnose else 0,
                 "ram_pct": result.scan.recursos.get("ram_pct", 0),
                 "disk_pct": result.scan.recursos.get("disk_pct", 0),
                 "load": result.scan.recursos.get("load_1m", 0),
                 "ok": result.ok}
        if perf:
            entry["perf"] = perf
        lines = (dep / ARCHIVO_TRENDS)
        with open(lines, "a") as f:
            f.write(json.dumps(entry, default=str) + "\n")

    def _escribir_side_effects(self, result: PipelineResult):
        """Escribe JSON de estado y diagnóstico a disco."""
        dep = Path(self.config.deploy_dir)
        dep.mkdir(parents=True, exist_ok=True)
        if result.scan:
            s = {"timestamp": result.scan.timestamp, "hostname": result.scan.hostname,
                 "health_score": result.scan.health_score, "servicios": result.scan.servicios,
                 "recursos": result.scan.recursos, "red": result.scan.red,
                 "hw_health": result.scan.hw_health,
                 "orphans": result.scan.orphans,
                 "systemd_failed": result.scan.systemd_failed}
            (dep / ARCHIVO_ESTADO).write_text(json.dumps(s, indent=2))
        if result.diagnose:
            d = {"timestamp": result.diagnose.timestamp,
                 "ok": result.diagnose.ok,
                 "incidentes": result.diagnose.incidentes,
                 "causas_raiz": result.diagnose.causas_raiz,
                 "modo_offline": result.diagnose.modo_offline,
                 "coste_historico": result.diagnose.coste_historico}
            (dep / ARCHIVO_DIAGNOSTICO).write_text(json.dumps(d, indent=2))

    def _emit(self, result: PipelineResult):
        """Emite resultado del pipeline como JSON a stdout."""
        print(json.dumps({"ura": "pipeline", "ok": result.ok,
                          "ts": result.timestamp,
                          "error": result.error,
                          "health_score": result.scan.health_score if result.scan else None,
                          "incidentes": len(result.diagnose.incidentes) if result.diagnose else 0},
                         default=str), flush=True)
