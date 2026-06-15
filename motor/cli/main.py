import argparse
import json
import logging
import socket
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.config import UraConfig
from core.qdrant_client import QdrantClient
from diagnostico import Diagnostico
from guard.preflight import ejecutar_preflight
from guard.verifier import ejecutar_verificacion
from pipeline.orchestrator import Orchestrator
from scanner import Scanner
from scanner.calibration import Calibration

log = logging.getLogger("ura.cli")

ARCHIVO_ESTADO = "estado_alemania.json"
ARCHIVO_DIAGNOSTICO = "diagnostico.json"
ARCHIVO_TRENDS = "trends.ndjson"
HOST_REMOTO_ALEMANIA = "ramon_admin@178.105.81.83"
PROCESOS_DUPLICADOS_CLAVE = ("opencode", "python3")

def _setup_logging(level: str) -> None:
    """Configura logging en stderr."""
    h = logging.StreamHandler(sys.stderr)
    h.setFormatter(logging.Formatter("%(name)s %(levelname)s %(message)s"))
    logging.getLogger().addHandler(h)
    logging.getLogger().setLevel(getattr(logging, level.upper(), logging.INFO))

def main() -> None:
    """Punto de entrada CLI."""
    parser = argparse.ArgumentParser(prog="ura", description="Motor de Conocimiento unificado")
    parser.add_argument("--config", default="", help="Ruta a config JSON")
    parser.add_argument("--log-level", default="INFO", help="Nivel de log")
    sub = parser.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("pipeline", help="Ejecutar pipeline completo")
    sp.add_argument("--dry-run", action="store_true", help="No ejecutar escaneo real")

    sub.add_parser("scan", help="Solo escanear")
    sub.add_parser("diagnose", help="Solo diagnosticar (requiere scan previo)")
    sub.add_parser("status", help="Estado unificado")
    sub.add_parser("check", help="Preflight check")
    sub.add_parser("verify", help="Verificación post-cambio")
    sub.add_parser("history", help="Historial de incidentes desde Qdrant")
    sub.add_parser("trend", help="Tendencia de salud a lo largo del tiempo")
    sub.add_parser("graph", help="Gráfico ASCII de tendencia de salud")
    sub.add_parser("perf", help="Rendimiento del pipeline (duración por etapa)")
    sub.add_parser("cross", help="Estado consolidado local + SSH remoto")
    sub.add_parser("alerta", help="Alertas recientes desde journald")
    sub.add_parser("detect", help="Detectar anomalías vs tendencia histórica")
    sub.add_parser("health-check", help="Verificar todos los componentes del monitor")
    sub.add_parser("qdrant-backup", help="Exportar Qdrant a JSON de respaldo")
    sub.add_parser("summarise", help="Resumen one-line del sistema (MOTD)")
    sub.add_parser("learn", help="Analizar tendencias y extraer conocimiento")
    sub.add_parser("notify", help="Enviar notificación si hay alertas activas")

    cal = sub.add_parser("calibrate", help="Generar baseline desde estado actual")
    cal.add_argument("--force", action="store_true", help="Sobreescribir baseline existente")

    args = parser.parse_args()
    _setup_logging(args.log_level)
    config = UraConfig.load(args.config)
    config.log_level = args.log_level

    if args.command == "pipeline":
        _cmd_pipeline(config, args)

    elif args.command == "scan":
        _cmd_scan(config)

    elif args.command == "diagnose":
        _cmd_diagnose(config)

    elif args.command == "status":
        _cmd_status(config)

    elif args.command == "check":
        _cmd_check(config)

    elif args.command == "verify":
        _cmd_verify(config)

    elif args.command == "history":
        _cmd_history(config)

    elif args.command == "trend":
        _cmd_trend(config)

    elif args.command == "graph":
        _cmd_graph(config)

    elif args.command == "perf":
        _cmd_perf(config)

    elif args.command == "calibrate":
        _cmd_calibrate(config, args)

    elif args.command == "cross":
        _cmd_cross(config)

    elif args.command == "alerta":
        _cmd_alerta()

    elif args.command == "detect":
        _cmd_detect(config)

    elif args.command == "health-check":
        _cmd_health_check(config)

    elif args.command == "qdrant-backup":
        _cmd_qdrant_backup(config)

    elif args.command == "summarise":
        _cmd_summarise(config)

    elif args.command == "learn":
        _cmd_learn(config)

    elif args.command == "notify":
        _cmd_notify(config)


def _cmd_pipeline(config: UraConfig, args) -> None:
    """Ejecuta el pipeline completo."""
    orch = Orchestrator(config)
    r = orch.run(dry_run=args.dry_run)
    sys.exit(0 if r.ok else 1)


def _cmd_scan(config: UraConfig) -> None:
    """Ejecuta solo el escaneo."""
    sc = Scanner(config)
    sc.run()


def _cmd_diagnose(config: UraConfig) -> None:
    """Ejecuta solo el diagnóstico."""
    qdrant = QdrantClient.instancia(config)
    diag = Diagnostico(config, qdrant)
    from core.state import ScanResult
    scan = ScanResult(ok=True, timestamp="")
    diag.run(scan)


def _cmd_status(config: UraConfig) -> None:
    """Muestra estado unificado del sistema."""
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
        r = subprocess.run(["ps", "-eo", "comm="], capture_output=True, text=True, timeout=5)
        v = {}
        for l in r.stdout.strip().split("\n"):
            c = l.strip()
            if c:
                v[c] = v.get(c, 0) + 1
        info["procesos_duplicados"] = {k: v for k, v in v.items() if v > 1 and k in PROCESOS_DUPLICADOS_CLAVE}
    except Exception as e:
        log.debug("status procesos duplicados falló: %s", e)


def _cmd_check(config: UraConfig) -> None:
    """Ejecuta preflight check."""
    r = ejecutar_preflight(config)
    sys.exit(0 if r.ok else 1)


def _cmd_verify(config: UraConfig) -> None:
    """Ejecuta verificación post-cambio."""
    ejecutar_verificacion(config, hubo_cambios=True)


def _cmd_history(config: UraConfig) -> None:
    """Muestra historial de incidentes desde Qdrant."""
    qdrant = QdrantClient.instancia(config)
    if not qdrant.disponible:
        sys.exit(1)
    qdrant.buscar_incidentes(limit=50)


def _cmd_trend(config: UraConfig) -> None:
    """Muestra tendencia de salud."""
    dep = Path(config.deploy_dir) / ARCHIVO_TRENDS
    if not dep.exists():
        sys.exit(1)
    [json.loads(l) for l in dep.read_text().strip().splitlines() if l.strip()]


def _cmd_graph(config: UraConfig) -> None:
    """Muestra gráfico ASCII de tendencia de salud."""
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


def _cmd_perf(config: UraConfig) -> None:
    """Muestra rendimiento del pipeline."""
    dep = Path(config.deploy_dir) / ARCHIVO_TRENDS
    if not dep.exists():
        sys.exit(1)
    lines = [json.loads(l) for l in dep.read_text().strip().splitlines() if l.strip()]
    with_perf = [l for l in lines if "perf" in l]
    if not with_perf:
        sys.exit(1)
    last = with_perf[-1]["perf"]
    {k: round(sum(p["perf"][k] for p in with_perf[-20:]) / max(len(with_perf[-20:]), 1), 1) for k in last}


def _cmd_calibrate(config: UraConfig, args) -> None:
    """Genera baseline desde estado actual."""
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


def _cmd_cross(config: UraConfig) -> None:
    """Estado consolidado local + SSH remoto."""
    res = {"ts": datetime.utcnow().isoformat() + "Z", "local": {"hostname": socket.gethostname()}}
    estado_path = Path(config.deploy_dir) / ARCHIVO_ESTADO
    if estado_path.exists():
        res["local"].update(json.loads(estado_path.read_text()))
    for name, host in {"alemania": HOST_REMOTO_ALEMANIA}.items():
        try:
            r = subprocess.run(["ssh", "-o", "ConnectTimeout=5", "-o", "BatchMode=yes",
                                "-o", "StrictHostKeyChecking=accept-new",
                                "-i", "/home/ramon/.ssh/id_rsa",
                                host, "sudo", "ura", "--config", "/etc/ura/config.json", "status"],
                               capture_output=True, text=True, timeout=15)
            if r.returncode == 0:
                res[name] = json.loads(r.stdout)
            else:
                res[name] = {"error": r.stderr.strip()[:200]}
        except Exception as e:
            res[name] = {"error": str(e)[:200]}


def _cmd_alerta() -> None:
    """Muestra alertas recientes desde journald."""
    r = subprocess.run(["journalctl", "-u", "ura-pipeline.service", "--no-pager",
                        "-p", "err", "--since", "1 hour ago", "-o", "short-iso"],
                       capture_output=True, text=True, timeout=10)
    [l for l in r.stdout.strip().split("\n") if "ALERTA" in l or "error" in l.lower()]


def _cmd_detect(config: UraConfig) -> None:
    """Detecta anomalías vs tendencia histórica."""
    trend_path = Path(config.deploy_dir) / ARCHIVO_TRENDS
    if not trend_path.exists():
        sys.exit(1)
    lines = [json.loads(l) for l in trend_path.read_text().strip().splitlines() if l.strip()]
    cal = Calibration(config)
    cal.detect(lines)


def _cmd_health_check(config: UraConfig) -> None:
    """Verifica todos los componentes del monitor."""
    checks = []
    for unit in ["ura-pipeline.service", "ura-pipeline.timer"]:
        try:
            r = subprocess.run(["systemctl", "is-active", unit], capture_output=True, text=True, timeout=5)
            ok = "active" in r.stdout or r.stdout.strip() == "inactive"
            checks.append({"check": unit, "ok": ok, "detail": r.stdout.strip()})
        except Exception as e:
            checks.append({"check": unit, "ok": False, "detail": str(e)})
    qdrant = QdrantClient.instancia(config)
    checks.append({"check": "qdrant", "ok": qdrant.disponible, "detail": f"host={config.qdrant_host}:{config.qdrant_port}"})
    estado_path = Path(config.deploy_dir) / ARCHIVO_ESTADO
    checks.append({"check": "deploy json", "ok": estado_path.exists(), "detail": "existe" if estado_path.exists() else "no existe"})
    trend_path = Path(config.deploy_dir) / ARCHIVO_TRENDS
    pts = len([l for l in trend_path.read_text().splitlines() if l.strip()]) if trend_path.exists() else 0
    checks.append({"check": "trends", "ok": trend_path.exists(), "detail": f"{pts} puntos" if trend_path.exists() else "no existe"})
    try:
        r = subprocess.run(["docker", "ps", "-q", "--filter", "name=qdrant"], capture_output=True, text=True, timeout=5)
        checks.append({"check": "docker qdrant", "ok": bool(r.stdout.strip()), "detail": "running" if r.stdout.strip() else "no running"})
    except Exception as e:
        checks.append({"check": "docker qdrant", "ok": False, "detail": str(e)})


def _cmd_qdrant_backup(config: UraConfig) -> None:
    """Exporta Qdrant a JSON de respaldo."""
    qdrant = QdrantClient.instancia(config)
    if not qdrant.disponible:
        sys.exit(1)
    incidents = qdrant.buscar_incidentes(limit=1000)
    backup_path = Path(config.deploy_dir) / f"qdrant_backup_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    backup_path.write_text(json.dumps({"incidentes": incidents, "exported_at": datetime.utcnow().isoformat() + "Z",
                                        "total": len(incidents)}, indent=2))


def _cmd_summarise(config: UraConfig) -> None:
    """Resumen one-line del sistema (MOTD)."""
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
            f" scan={p.get('scan_s',0)}s"
    QdrantClient.instancia(config)


def _cmd_learn(config: UraConfig) -> None:
    """Analiza tendencias y extrae conocimiento."""
    trend_path = Path(config.deploy_dir) / ARCHIVO_TRENDS
    if not trend_path.exists() or not trend_path.stat().st_size:
        sys.exit(1)
    lines = [json.loads(l) for l in trend_path.read_text().splitlines() if l.strip()]
    if len(lines) < 3:
        sys.exit(1)
    insights = []
    for metrica, nombre in [("health", "Health"), ("ram_pct", "RAM"), ("disk_pct", "DISK")]:
        vals = [l.get(metrica, 0) for l in lines if isinstance(l.get(metrica), (int, float))]
        if len(vals) >= 3:
            trend = (vals[-1] - vals[0]) / max(len(vals), 1)
            if trend > 0.5:
                insights.append({"metrica": nombre, "direccion": "subiendo", "delta": round(trend * len(vals), 1),
                                 "inicio": vals[0], "final": vals[-1]})
            elif trend < -0.5:
                insights.append({"metrica": nombre, "direccion": "bajando", "delta": round(trend * len(vals), 1),
                                 "inicio": vals[0], "final": vals[-1]})
    health_vals = [l.get("health", 0) for l in lines if isinstance(l.get("health"), (int, float))]
    min_h, max_h = min(health_vals), max(health_vals)
    insights.append({"metrica": "Health", "rango": f"{min_h}-{max_h}", "min": min_h, "max": max_h})
    disk_vals = [l.get("disk_pct", 0) for l in lines if isinstance(l.get("disk_pct"), (int, float))]
    if len(disk_vals) >= 3:
        tasa = (disk_vals[-1] - disk_vals[0]) / max(len(disk_vals), 1)
        if tasa > 0:
            dias_para_lleno = int((100 - disk_vals[-1]) / (tasa * 288)) if tasa > 0 else 999
            insights.append({"metrica": "DISK", "tasa_crecimiento_diario": round(tasa * 288, 2),
                             "dias_para_llenar": dias_para_lleno if dias_para_lleno < 365 else ">1año"})


def _cmd_notify(config: UraConfig) -> None:
    """Envía notificación si hay alertas activas."""
    estado_path = Path(config.deploy_dir) / ARCHIVO_ESTADO
    if not estado_path.exists():
        sys.exit(0)
    d = json.loads(estado_path.read_text())
    hs = d.get("health_score", 100)
    inc = 0
    diag_path = Path(config.deploy_dir) / ARCHIVO_DIAGNOSTICO
    if diag_path.exists():
        diag = json.loads(diag_path.read_text())
        inc = len(diag.get("incidentes", []))
    if hs < 95 or inc > 0:
        msg = f"URA alerta: health={hs} incidentes={inc}"
        try:
            subprocess.run(["notify-send", "--urgency=critical", "URA", msg], capture_output=True, timeout=5)
        except FileNotFoundError:
            log.debug("notify-send no disponible")
    else:
        pass


if __name__ == "__main__":
    main()
