import json
import logging
import socket
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from motor.core.config import UraConfig
from motor.core.qdrant_client import QdrantClient

log = logging.getLogger("ura.cli")
ARCHIVO_ESTADO = "estado_alemania.json"
ARCHIVO_TRENDS = "trends.ndjson"
HOST_REMOTO_ALEMANIA = "ramon_admin@178.105.81.83"
PROCESOS_DUPLICADOS_CLAVE = ("opencode", "python3")


def cmd_status(config: UraConfig, args=None):
    info = {"hostname": "", "health_score": "-", "servicios": {}, "recursos": {}}
    try:
        info["hostname"] = socket.gethostname()
    except Exception as e:
        log.debug("gethostname falló: %s", e)
    estado_path = Path(config.deploy_dir) / ARCHIVO_ESTADO
    if estado_path.exists():
        info.update(json.loads(estado_path.read_text()))
    info["procesos_duplicados"] = []
    try:
        r = subprocess.run(["ps", "-eo", "comm="], capture_output=True, text=True, timeout=5, check=False)
        v = {}
        for l in r.stdout.strip().split("\n"):
            c = l.strip()
            if c:
                v[c] = v.get(c, 0) + 1
        info["procesos_duplicados"] = {k: v for k, v in v.items() if v > 1 and k in PROCESOS_DUPLICADOS_CLAVE}
    except Exception as e:
        log.debug("status procesos duplicados falló: %s", e)
    print(json.dumps(info, indent=2, default=str))


def cmd_cross(config: UraConfig, args=None):
    res = {"ts": datetime.now(UTC).isoformat() + "Z", "local": {"hostname": socket.gethostname()}}
    estado_path = Path(config.deploy_dir) / ARCHIVO_ESTADO
    if estado_path.exists():
        res["local"].update(json.loads(estado_path.read_text()))
    for name, host in {"alemania": HOST_REMOTO_ALEMANIA}.items():
        try:
            r = subprocess.run(
                [
                    "ssh",
                    "-o",
                    "ConnectTimeout=5",
                    "-o",
                    "BatchMode=yes",
                    "-o",
                    "StrictHostKeyChecking=accept-new",
                    "-i",
                    "/home/ramon/.ssh/id_rsa",
                    host,
                    "sudo",
                    "ura",
                    "--config",
                    "/etc/ura/config.json",
                    "status",
                ],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            if r.returncode == 0:
                res[name] = json.loads(r.stdout)
            else:
                res[name] = {"error": r.stderr.strip()[:200]}
        except Exception as e:
            res[name] = {"error": str(e)[:200]}
    print(json.dumps(res, indent=2, default=str))


def cmd_trend(config: UraConfig, args=None):
    dep = Path(config.deploy_dir) / ARCHIVO_TRENDS
    if not dep.exists():
        print(json.dumps({"error": "No hay datos de tendencia"}, indent=2))
        sys.exit(1)
    lines = [json.loads(l) for l in dep.read_text().strip().splitlines() if l.strip()]
    print(
        json.dumps(
            {
                "tendencia": lines[-50:],
                "total": len(lines),
                "health_avg": round(sum(l["health"] for l in lines[-20:]) / max(len(lines[-20:]), 1), 1),
                "ultimo": lines[-1] if lines else None,
            },
            indent=2,
            default=str,
        ),
    )


def cmd_graph(config: UraConfig, args=None):
    dep = Path(config.deploy_dir) / ARCHIVO_TRENDS
    if not dep.exists():
        print("No hay datos de tendencia")
        sys.exit(1)
    lines = [json.loads(l) for l in dep.read_text().strip().splitlines() if l.strip()]
    if len(lines) < 2:
        print("Se necesitan al menos 2 puntos")
        sys.exit(1)
    vals = [l["health"] for l in lines[-40:]]
    mn, mx = 90, 100
    rng = max(mx - mn, 0.1)
    idx = -len(vals)
    for i, v in enumerate(vals):
        h = max(0, min(10, int((v - mn) / rng * 10)))
        marca = "█" * h + "░" * (10 - h)
        label = lines[idx + i]["ts"][11:16]
        print(f"{label} {marca} {v:.1f}")
    print(f"\nRango: {mn:.1f} - {mx:.1f} | {len(vals)} puntos | Último: {vals[-1]:.1f}")


def cmd_perf(config: UraConfig, args=None):
    dep = Path(config.deploy_dir) / ARCHIVO_TRENDS
    if not dep.exists():
        print(json.dumps({"error": "No hay datos de rendimiento"}, indent=2))
        sys.exit(1)
    lines = [json.loads(l) for l in dep.read_text().strip().splitlines() if l.strip()]
    with_perf = [l for l in lines if "perf" in l]
    if not with_perf:
        print(json.dumps({"error": "Sin datos de rendimiento (actualiza pipeline)"}, indent=2))
        sys.exit(1)
    last = with_perf[-1]["perf"]
    avg = {k: round(sum(p["perf"][k] for p in with_perf[-20:]) / max(len(with_perf[-20:]), 1), 1) for k in last}
    print(json.dumps({"ok": True, "runs": len(with_perf), "ultimo": last, "promedio": avg}, indent=2))


def cmd_summarise(config: UraConfig, args=None):
    host = socket.gethostname()
    estado_path = Path(config.deploy_dir) / ARCHIVO_ESTADO
    if not estado_path.exists():
        print(f"URA {host}: sin datos (ejecuta pipeline)")
        sys.exit(1)
    d = json.loads(estado_path.read_text())
    hs = d.get("health_score", "?")
    svc_total = len(d.get("servicios", {}))
    svc_ko = sum(1 for v in d.get("servicios", {}).values() if v in ("inactive", "failed"))
    ram = d.get("recursos", {}).get("ram_pct", 0)
    disk = d.get("recursos", {}).get("disk_pct", 0)
    trend_path = Path(config.deploy_dir) / ARCHIVO_TRENDS
    trend_pts = 0
    perf_info = ""
    if trend_path.exists():
        trend_pts = sum(1 for _ in trend_path.open())
        lines = [json.loads(l) for l in trend_path.read_text().splitlines() if l.strip()]
        with_p = [l for l in lines if "perf" in l]
        if with_p:
            p = with_p[-1]["perf"]
            perf_info = f" scan={p.get('scan_s', 0)}s"
    qdrant = QdrantClient.instancia(config)
    qd_host = "local" if config.qdrant_host in ("localhost", "127.0.0.1") else config.qdrant_host
    print(
        f"URA {host}: health={hs} svc={svc_total}({svc_ko}KO) RAM={ram}% DISK={disk}% qdrant={qd_host} qd{'OK' if qdrant.disponible else 'DOWN'}{perf_info} trend={trend_pts}pts",
    )
