import hashlib
import json
import logging
from datetime import UTC, datetime
from pathlib import Path

from motor.core.config import UraConfig
from motor.core.executor import SubprocessExecutor
from motor.core.qdrant_client import QdrantClient
from motor.core.state import DiagnoseResult, ScanResult
from motor.diagnostico.backup_knowledge import backup_incidente
from motor.diagnostico.circuit_breaker import CircuitBreaker
from motor.diagnostico.correlacion import agrupar_incidentes, resumir_incidentes
from motor.diagnostico.pattern_matcher import buscar_patrones

log = logging.getLogger("ura.diagnostico")
_executor = SubprocessExecutor()

RUTAS_CONFIG_OPENCODE = ["/etc/opencode/opencode.jsonc", "/etc/opencode/opencode.json"]


class Diagnostico:
    """Motor de diagnóstico: busca patrones, correlaciona, determina causas raíz."""

    def __init__(self, config: UraConfig, qdrant: QdrantClient):
        self.config = config
        self.qdrant = qdrant
        self.cb = CircuitBreaker(qdrant)

    def run(self, scan: ScanResult) -> DiagnoseResult:
        """Ejecuta el pipeline de diagnóstico completo."""
        r = DiagnoseResult(timestamp=datetime.now(UTC).isoformat() + "Z")
        r.snapshot_inicial = self._tomar_snapshot_inicial()
        if not scan.ok:
            r.ok = False
            log.warning("scan no ok, diagnostico limitado")
        if not self.cb.operacional():
            r.modo_offline = True
            log.warning("modo offline (circuit breaker abierto)")
        incidentes, costes = buscar_patrones(scan, self.qdrant, self.cb, self.config)
        r.incidentes = incidentes
        r.coste_historico = costes
        tags = self._extraer_tags(incidentes, scan)
        r.correlaciones = agrupar_incidentes(
            tags,
            hw_ok=scan.hw_health.get("ok", True),
            hw_issues=scan.hw_health.get("issues", []),
        )
        r.causas_raiz = self._determinar_causas(r.correlaciones)
        self._guardar_incidente_qdrant(r, scan)
        if r.incidentes:
            backup_incidente(self.config, r.incidentes[0])
        log.info("diagnostico: %d incidentes, %d causas", len(r.incidentes), len(r.causas_raiz))
        return r

    def _tomar_snapshot_inicial(self) -> dict:
        """Toma un snapshot de configs y procesos al inicio del diagnóstico."""
        snap = {"timestamp": datetime.now(UTC).isoformat() + "Z"}
        for archivo in RUTAS_CONFIG_OPENCODE:
            p = Path(archivo)
            if p.exists():
                snap[archivo] = {"hash": hashlib.sha256(p.read_bytes()).hexdigest()[:16], "size": p.stat().st_size}
        try:
            r = _executor.run(["ps", "-eo", "pid,comm", "--sort=-pid"], timeout=3)
            snap["procesos"] = [l.strip() for l in r.stdout.strip().split("\n")[:20]]
        except Exception as e:
            log.debug("snapshot procesos falló: %s", e)
        return snap

    def _extraer_tags(self, incidentes: list, scan: ScanResult) -> list:
        """Extrae tags desde incidentes y estado del scan para correlación."""
        tags = set()
        for inc in incidentes:
            tags.add(inc.get("tipo", "Unknown"))
            if inc.get("subtipo"):
                tags.add(inc["subtipo"])
        if scan.hw_health.get("issues"):
            tags.add("hw_issue")
        if scan.duplicados:
            tags.add("config_conflict")
        if scan.flapping:
            tags.add("flapping")
        if not scan.red.get("exit_node_online", True):
            tags.add("exit_node_offline")
        return list(tags)

    def _determinar_causas(self, correlaciones: list) -> list:
        """Extrae causas raíz de las correlaciones."""
        return [c["causa_raiz"] for c in correlaciones if "causa_raiz" in c]

    def _guardar_incidente_qdrant(self, diag: DiagnoseResult, scan: ScanResult):
        """Persiste el diagnóstico como incidente en Qdrant."""
        if not diag.incidentes:
            return
        impacto = [0.0] * 7
        if diag.causas_raiz:
            impacto[0] = 1.0
        if not scan.hw_health.get("ok", True):
            impacto[5] = 1.0
        if diag.modo_offline:
            impacto[6] = 1.0
        incidente = {
            "ts": diag.timestamp,
            "tipo": "AutoDiagnostico",
            "subtipo": "pipeline",
            "resumen": resumir_incidentes(diag.incidentes),
            "impacto_memoria": impacto,
            "hw_ok": scan.hw_health.get("ok", True),
            "hw_issues": scan.hw_health.get("issues", []),
        }
        self.qdrant.guardar_incidente(incidente)
