import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import RLock

log = logging.getLogger("ura.state")


class DegradedMode:
    """Singleton thread-safe que rastrea subsistemas en modo degradado.

    Uso:
        dm = DegradedMode()
        dm.mark_degraded("qdrant")
        dm.mark_healthy("qdrant")
        dm.is_degraded("qdrant")
        dm.status()  # -> {"degraded": ["qdrant"], "since": {"qdrant": "2024-..."}}
    """

    _instancia: "DegradedMode | None" = None
    _lock: RLock = RLock()

    def __init__(self) -> None:
        self._degraded: dict[str, datetime] = {}
        self._local_lock: RLock = RLock()

    def mark_degraded(self, subsystem: str) -> bool:
        """Marca un subsistema como degradado. Retorna True si ya lo estaba."""
        with self._local_lock:
            if subsystem in self._degraded:
                return True
            self._degraded[subsystem] = datetime.now(UTC)
            log.warning("DegradedMode: %s marcado como DEGRADADO", subsystem)
            return False

    def mark_healthy(self, subsystem: str) -> bool:
        """Marca un subsistema como saludable. Retorna True si ya lo estaba."""
        with self._local_lock:
            if subsystem not in self._degraded:
                return True
            del self._degraded[subsystem]
            log.warning("DegradedMode: %s recuperado — SALUDABLE", subsystem)
            return False

    def is_degraded(self, subsystem: str) -> bool:
        with self._local_lock:
            return subsystem in self._degraded

    def status(self) -> dict:
        """Estado serializable para API /api/v1/status."""
        with self._local_lock:
            degraded = sorted(self._degraded.keys())
            since = {k: v.isoformat() for k, v in self._degraded.items()}
            return {
                "global": len(degraded) > 0,
                "degraded": degraded,
                "since": since,
                "healthy": len(degraded) == 0,
            }

    @classmethod
    def instancia(cls) -> "DegradedMode":
        with cls._lock:
            if cls._instancia is None:
                cls._instancia = cls()
        return cls._instancia


@dataclass
class ScanResult:
    """Resultado completo de un escaneo del sistema."""

    ok: bool = False
    timestamp: str = ""
    hostname: str = ""
    servicios: dict = field(default_factory=dict)
    recursos: dict = field(default_factory=dict)
    contenedores: dict = field(default_factory=dict)
    red: dict = field(default_factory=dict)
    hw_health: dict = field(default_factory=lambda: {"ok": True, "issues": []})
    health_score: float = 100.0
    anomalias: list = field(default_factory=list)
    diff_total: int = 0
    flapping: list = field(default_factory=list)
    calibration_status: str = "unknown"
    duplicados: dict = field(default_factory=dict)
    contenedores_ko: list = field(default_factory=list)
    orphans: list = field(default_factory=list)
    systemd_failed: list = field(default_factory=list)
    systemd_orphans: list = field(default_factory=list)
    snapshot_hash: str = ""


@dataclass
class PreflightResult:
    """Resultado de la verificación prevuelo antes de escanear."""

    ok: bool = True
    bloqueado: bool = False
    razon: str = ""
    snapshot_path: str = ""
    procesos_duplicados: list = field(default_factory=list)
    configs_duplicadas: list = field(default_factory=list)


@dataclass
class DiagnoseResult:
    """Resultado del diagnóstico: incidentes, correlaciones y causas raíz."""

    ok: bool = True
    timestamp: str = ""
    incidentes: list = field(default_factory=list)
    correlaciones: list = field(default_factory=list)
    causas_raiz: list = field(default_factory=list)
    coste_historico: dict = field(default_factory=dict)
    modo_offline: bool = False
    snapshot_inicial: dict = field(default_factory=dict)


@dataclass
class VerifyResult:
    """Resultado de la verificación post-cambio."""

    ok: bool = True
    verdict: str = "not_run"
    test_response: str = ""
    revertido: bool = False
    error: str = ""


@dataclass
class PipelineResult:
    """Resultado completo del pipeline: preflight + scan + diagnose + verify."""

    ok: bool = False
    timestamp: str = ""
    preflight: PreflightResult | None = None
    scan: ScanResult | None = None
    diagnose: DiagnoseResult | None = None
    verify: VerifyResult | None = None
    error: str = ""
