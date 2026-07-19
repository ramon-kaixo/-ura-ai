import json
import logging
import socket
import sys
from datetime import UTC, datetime
from pathlib import Path

from motor.core.config import UraConfig
from motor.core.executor import SubprocessExecutor
from motor.core.qdrant_client import QdrantClient

log = logging.getLogger("ura.cli")
ARCHIVO_ESTADO = "estado_alemania.json"
ARCHIVO_TRENDS = "trends.ndjson"
HOST_REMOTO_ALEMANIA = "ramon_admin@178.105.81.83"
PROCESOS_DUPLICADOS_CLAVE = ("opencode", "python3")
_executor = SubprocessExecutor()


def cmd_status(config: UraConfig, args=None) -> None:
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
        r = _executor.run(["ps", "-eo", "comm="], timeout=5)
        v = {}
        for l in r.stdout.strip().split("\n"):
            c = l.strip()
            if c:
                v[c] = v.get(c, 0) + 1
        info["procesos_duplicados"] = {k: v for k, v in v.items() if v > 1 and k in PROCESOS_DUPLICADOS_CLAVE}
    except Exception as e:
        log.debug("status procesos duplicados falló: %s", e)


def cmd_cross(config: UraConfig, args=None) -> None:
    res = {"ts": datetime.now(UTC).isoformat() + "Z", "local": {"hostname": socket.gethostname()}}
    estado_path = Path(config.deploy_dir) / ARCHIVO_ESTADO
    if estado_path.exists():
        res["local"].update(json.loads(estado_path.read_text()))
    for name, host in {"alemania": HOST_REMOTO_ALEMANIA}.items():
        try:
            r = _executor.run(
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
                timeout=15,
            )
            if r.returncode == 0:
                res[name] = json.loads(r.stdout)
            else:
                res[name] = {"error": r.stderr.strip()[:200]}
        except Exception as e:
            res[name] = {"error": str(e)[:200]}


def cmd_trend(config: UraConfig, args=None) -> None:
    dep = Path(config.deploy_dir) / ARCHIVO_TRENDS
    if not dep.exists():
        sys.exit(1)
    [json.loads(l) for l in dep.read_text().strip().splitlines() if l.strip()]


def cmd_graph(config: UraConfig, args=None) -> None:
    dep = Path(config.deploy_dir) / ARCHIVO_TRENDS
    if not dep.exists():
        sys.exit(1)
    lines = [json.loads(l) for l in dep.read_text().strip().splitlines() if l.strip()]
    if len(lines) < 2:
        sys.exit(1)
    vals = [l["health"] for l in lines[-40:]]
    mn, mx = 90, 100
    rng = max(mx - mn, 0.1)
    idx = -len(vals)
    for i, v in enumerate(vals):
        h = max(0, min(10, int((v - mn) / rng * 10)))
        "█" * h + "░" * (10 - h)
        lines[idx + i]["ts"][11:16]


def cmd_perf(config: UraConfig, args=None) -> None:
    dep = Path(config.deploy_dir) / ARCHIVO_TRENDS
    if not dep.exists():
        sys.exit(1)
    lines = [json.loads(l) for l in dep.read_text().strip().splitlines() if l.strip()]
    with_perf = [l for l in lines if "perf" in l]
    if not with_perf:
        sys.exit(1)
    last = with_perf[-1]["perf"]
    {k: round(sum(p["perf"][k] for p in with_perf[-20:]) / max(len(with_perf[-20:]), 1), 1) for k in last}


def cmd_summarise(config: UraConfig, args=None) -> None:
    socket.gethostname()
    estado_path = Path(config.deploy_dir) / ARCHIVO_ESTADO
    if not estado_path.exists():
        sys.exit(1)
    d = json.loads(estado_path.read_text())
    d.get("health_score", "?")
    len(d.get("servicios", {}))
    sum(1 for v in d.get("servicios", {}).values() if v in ("inactive", "failed"))
    d.get("recursos", {}).get("ram_pct", 0)
    d.get("recursos", {}).get("disk_pct", 0)
    trend_path = Path(config.deploy_dir) / ARCHIVO_TRENDS
    if trend_path.exists():
        sum(1 for _ in trend_path.open())
        lines = [json.loads(l) for l in trend_path.read_text().splitlines() if l.strip()]
        with_p = [l for l in lines if "perf" in l]
        if with_p:
            p = with_p[-1]["perf"]
            f" scan={p.get('scan_s', 0)}s"
    QdrantClient.instancia(config)
