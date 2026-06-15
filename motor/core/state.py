from dataclasses import dataclass, field
from typing import Optional

@dataclass
class ScanResult:
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
    ok: bool = True
    bloqueado: bool = False
    razon: str = ""
    snapshot_path: str = ""
    procesos_duplicados: list = field(default_factory=list)
    configs_duplicadas: list = field(default_factory=list)

@dataclass
class DiagnoseResult:
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
    ok: bool = True
    verdict: str = "not_run"
    test_response: str = ""
    revertido: bool = False
    error: str = ""

@dataclass
class PipelineResult:
    ok: bool = False
    timestamp: str = ""
    preflight: Optional[PreflightResult] = None
    scan: Optional[ScanResult] = None
    diagnose: Optional[DiagnoseResult] = None
    verify: Optional[VerifyResult] = None
    error: str = ""
