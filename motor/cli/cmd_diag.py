import json
import logging
import socket
import subprocess
import sys
from pathlib import Path

from motor.core.config import UraConfig
from motor.core.qdrant_client import QdrantClient
from motor.guard.preflight import ejecutar_preflight
from motor.guard.verifier import ejecutar_verificacion
from motor.scanner.calibration import Calibration

log = logging.getLogger("ura.cli")
ARCHIVO_TRENDS = "trends.ndjson"
ARCHIVO_ESTADO = "estado_alemania.json"


def cmd_history(config: UraConfig, args=None):
    qdrant = QdrantClient.instancia(config)
    if not qdrant.disponible:
        print(json.dumps({"error": "Qdrant no disponible"}, indent=2))
        sys.exit(1)
    incidents = qdrant.buscar_incidentes(limit=50)
    print(json.dumps({"incidentes": incidents}, indent=2, default=str))


def cmd_check(config: UraConfig, args=None):
    r = ejecutar_preflight(config)
    print(
        json.dumps(
            {
                "ok": r.ok,
                "bloqueado": r.bloqueado,
                "razon": r.razon,
                "configs_duplicadas": r.configs_duplicadas,
                "snapshot": r.snapshot_path,
            },
            indent=2,
            default=str,
        ),
    )
    sys.exit(0 if r.ok else 1)


def cmd_verify(config: UraConfig, args=None):
    r = ejecutar_verificacion(config, hubo_cambios=True)
    print(
        json.dumps(
            {"ok": r.ok, "verdict": r.verdict, "error": r.error, "revertido": r.revertido},
            indent=2,
            default=str,
        ),
    )


def cmd_detect(config: UraConfig, args=None):
    trend_path = Path(config.deploy_dir) / ARCHIVO_TRENDS
    if not trend_path.exists():
        print(json.dumps({"error": "No hay datos de tendencia. Ejecuta pipeline primero."}, indent=2))
        sys.exit(1)
    lines = [json.loads(l) for l in trend_path.read_text().strip().splitlines() if l.strip()]
    cal = Calibration(config)
    res = cal.detect(lines)
    print(json.dumps(res, indent=2, default=str))


def cmd_learn(config: UraConfig, args=None):
    trend_path = Path(config.deploy_dir) / ARCHIVO_TRENDS
    if not trend_path.exists() or not trend_path.stat().st_size:
        print(json.dumps({"error": "No hay datos de tendencia"}, indent=2))
        sys.exit(1)
    lines = [json.loads(l) for l in trend_path.read_text().splitlines() if l.strip()]
    if len(lines) < 3:
        print(json.dumps({"error": "Necesito al menos 3 puntos"}, indent=2))
        sys.exit(1)
    insights = []
    for metrica, nombre in [("health", "Health"), ("ram_pct", "RAM"), ("disk_pct", "DISK")]:
        vals = [l.get(metrica, 0) for l in lines if isinstance(l.get(metrica), (int, float))]
        if len(vals) >= 3:
            trend = (vals[-1] - vals[0]) / max(len(vals), 1)
            if trend > 0.5:
                insights.append(
                    {
                        "metrica": nombre,
                        "direccion": "subiendo",
                        "delta": round(trend * len(vals), 1),
                        "inicio": vals[0],
                        "final": vals[-1],
                    },
                )
            elif trend < -0.5:
                insights.append(
                    {
                        "metrica": nombre,
                        "direccion": "bajando",
                        "delta": round(trend * len(vals), 1),
                        "inicio": vals[0],
                        "final": vals[-1],
                    },
                )
    health_vals = [l.get("health", 0) for l in lines if isinstance(l.get("health"), (int, float))]
    min_h, max_h = min(health_vals), max(health_vals)
    insights.append({"metrica": "Health", "rango": f"{min_h}-{max_h}", "min": min_h, "max": max_h})
    disk_vals = [l.get("disk_pct", 0) for l in lines if isinstance(l.get("disk_pct"), (int, float))]
    if len(disk_vals) >= 3:
        tasa = (disk_vals[-1] - disk_vals[0]) / max(len(disk_vals), 1)
        if tasa > 0:
            dias_para_lleno = int((100 - disk_vals[-1]) / (tasa * 288)) if tasa > 0 else 999
            insights.append(
                {
                    "metrica": "DISK",
                    "tasa_crecimiento_diario": round(tasa * 288, 2),
                    "dias_para_llenar": dias_para_lleno if dias_para_lleno < 365 else ">1año",
                },
            )
    print(json.dumps({"ok": True, "total_puntos": len(lines), "insights": insights}, indent=2))


def cmd_alerta(config: UraConfig = None, args=None):
    r = subprocess.run(
        [
            "journalctl",
            "-u",
            "ura-pipeline.service",
            "--no-pager",
            "-p",
            "err",
            "--since",
            "1 hour ago",
            "-o",
            "short-iso",
        ],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    alerts = [l for l in r.stdout.strip().split("\n") if "ALERTA" in l or "error" in l.lower()]
    print(json.dumps({"alertas": alerts[-20:], "total": len(alerts)}, indent=2, default=str))


def cmd_health_check(config: UraConfig, args=None):
    checks = []
    for unit in ["ura-pipeline.service", "ura-pipeline.timer"]:
        try:
            r = subprocess.run(["systemctl", "is-active", unit], capture_output=True, text=True, timeout=5, check=False)
            ok = "active" in r.stdout or r.stdout.strip() in ("inactive",)
            checks.append({"check": unit, "ok": ok, "detail": r.stdout.strip()})
        except Exception as e:
            checks.append({"check": unit, "ok": False, "detail": str(e)})
    qdrant = QdrantClient.instancia(config)
    checks.append(
        {"check": "qdrant", "ok": qdrant.disponible, "detail": f"host={config.qdrant_host}:{config.qdrant_port}"},
    )
    estado_path = Path(config.deploy_dir) / ARCHIVO_ESTADO
    checks.append(
        {
            "check": "deploy json",
            "ok": estado_path.exists(),
            "detail": "existe" if estado_path.exists() else "no existe",
        },
    )
    trend_path = Path(config.deploy_dir) / ARCHIVO_TRENDS
    pts = len([l for l in trend_path.read_text().splitlines() if l.strip()]) if trend_path.exists() else 0
    checks.append(
        {
            "check": "trends",
            "ok": trend_path.exists(),
            "detail": f"{pts} puntos" if trend_path.exists() else "no existe",
        },
    )
    try:
        r = subprocess.run(
            ["docker", "ps", "-q", "--filter", "name=qdrant"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        checks.append(
            {
                "check": "docker qdrant",
                "ok": bool(r.stdout.strip()),
                "detail": "running" if r.stdout.strip() else "no running",
            },
        )
    except Exception as e:
        checks.append({"check": "docker qdrant", "ok": False, "detail": str(e)})
    print(
        json.dumps({"ok": all(c["ok"] for c in checks), "hostname": socket.gethostname(), "checks": checks}, indent=2),
    )
