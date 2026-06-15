from dataclasses import dataclass, field


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
