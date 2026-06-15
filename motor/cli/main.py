import argparse, sys, json, logging
from datetime import datetime
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from core.config import UraConfig
from core.qdrant_client import QdrantClient
from scanner import Scanner
from scanner.calibration import Calibration
from diagnostico import Diagnostico
from pipeline.orchestrator import Orchestrator
from guard.preflight import ejecutar_preflight
from guard.verifier import ejecutar_verificacion

def _setup_logging(level: str):
    h = logging.StreamHandler(sys.stderr)
    h.setFormatter(logging.Formatter("%(name)s %(levelname)s %(message)s"))
    logging.getLogger().addHandler(h)
    logging.getLogger().setLevel(getattr(logging, level.upper(), logging.INFO))

def main():
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
    sub.add_parser("cross", help="Estado consolidado local + SSH remoto")
    sub.add_parser("alerta", help="Alertas recientes desde journald")
    sub.add_parser("detect", help="Detectar anomalías vs tendencia histórica")

    cal = sub.add_parser("calibrate", help="Generar baseline desde estado actual")
    cal.add_argument("--force", action="store_true", help="Sobreescribir baseline existente")

    args = parser.parse_args()
    _setup_logging(args.log_level)
    config = UraConfig.load(args.config)
    config.log_level = args.log_level

    if args.command == "pipeline":
        orch = Orchestrator(config)
        r = orch.run(dry_run=args.dry_run)
        sys.exit(0 if r.ok else 1)

    elif args.command == "scan":
        sc = Scanner(config)
        r = sc.run()
        print(json.dumps({"health_score": r.health_score, "servicios": r.servicios,
                          "recursos": r.recursos, "hw_ok": r.hw_health.get("ok"),
                          "red": r.red, "duplicados": r.duplicados}, indent=2, default=str))

    elif args.command == "diagnose":
        qdrant = QdrantClient.instancia(config)
        diag = Diagnostico(config, qdrant)
        from core.state import ScanResult
        scan = ScanResult(ok=True, timestamp="")
        r = diag.run(scan)
        print(json.dumps({"ok": r.ok, "incidentes": r.incidentes, "causas_raiz": r.causas_raiz,
                          "modo_offline": r.modo_offline}, indent=2, default=str))

    elif args.command == "status":
        import subprocess as sproc
        info = {"hostname": "", "health_score": "-", "servicios": {}, "recursos": {}}
        try:
            import socket; info["hostname"] = socket.gethostname()
        except: pass
        estado_path = Path(config.deploy_dir) / "estado_alemania.json"
        if estado_path.exists():
            info.update(json.loads(estado_path.read_text()))
        info["procesos_duplicados"] = []
        try:
            r = sproc.run(["ps", "-eo", "comm="], capture_output=True, text=True, timeout=5)
            v = {}
            for l in r.stdout.strip().split("\n"):
                c = l.strip()
                if c: v[c] = v.get(c, 0) + 1
            info["procesos_duplicados"] = {k: v for k, v in v.items() if v > 1 and k in ("opencode", "python3")}
        except: pass
        print(json.dumps(info, indent=2, default=str))

    elif args.command == "check":
        r = ejecutar_preflight(config)
        print(json.dumps({"ok": r.ok, "bloqueado": r.bloqueado, "razon": r.razon,
                          "configs_duplicadas": r.configs_duplicadas,
                          "snapshot": r.snapshot_path}, indent=2, default=str))
        sys.exit(0 if r.ok else 1)

    elif args.command == "verify":
        r = ejecutar_verificacion(config, hubo_cambios=True)
        print(json.dumps({"ok": r.ok, "verdict": r.verdict, "error": r.error,
                          "revertido": r.revertido}, indent=2, default=str))

    elif args.command == "history":
        qdrant = QdrantClient.instancia(config)
        if not qdrant.disponible:
            print(json.dumps({"error": "Qdrant no disponible"}, indent=2))
            sys.exit(1)
        incidents = qdrant.buscar_incidentes(limit=50)
        print(json.dumps({"incidentes": incidents}, indent=2, default=str))

    elif args.command == "trend":
        dep = Path(config.deploy_dir) / "trends.ndjson"
        if not dep.exists():
            print(json.dumps({"error": "No hay datos de tendencia"}, indent=2))
            sys.exit(1)
        lines = [json.loads(l) for l in dep.read_text().strip().splitlines() if l.strip()]
        print(json.dumps({"tendencia": lines[-50:], "total": len(lines),
                          "health_avg": round(sum(l["health"] for l in lines[-20:])/max(len(lines[-20:]),1), 1),
                          "ultimo": lines[-1] if lines else None}, indent=2, default=str))

    elif args.command == "calibrate":
        cal = Calibration(config)
        if cal.hay_baseline and not args.force:
            print(json.dumps({"error": "Baseline ya existe, usa --force para sobreescribir"}, indent=2))
            sys.exit(1)
        sc = Scanner(config)
        scan = sc.run()
        trend_path = Path(config.deploy_dir) / "trends.ndjson"
        trends = []
        if trend_path.exists():
            trends = [json.loads(l) for l in trend_path.read_text().strip().splitlines() if l.strip()]
        bl = cal.learn(scan, trends)
        print(json.dumps({"ok": True, "baseline": bl, "puntos_usados": len(trends)}, indent=2, default=str))

    elif args.command == "cross":
        import subprocess as sproc, socket
        res = {"ts": datetime.utcnow().isoformat() + "Z", "local": {"hostname": socket.gethostname()}}
        estado_path = Path(config.deploy_dir) / "estado_alemania.json"
        if estado_path.exists():
            res["local"].update(json.loads(estado_path.read_text()))
        for name, host in {"alemania": "ramon_admin@178.105.81.83"}.items():
            try:
                r = sproc.run(["ssh", "-o", "ConnectTimeout=5", "-o", "BatchMode=yes",
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
        print(json.dumps(res, indent=2, default=str))

    elif args.command == "alerta":
        import subprocess as sproc
        r = sproc.run(["journalctl", "-u", "ura-pipeline.service", "--no-pager",
                       "-p", "err", "--since", "1 hour ago", "-o", "short-iso"],
                      capture_output=True, text=True, timeout=10)
        alerts = [l for l in r.stdout.strip().split("\n") if "ALERTA" in l or "error" in l.lower()]
        print(json.dumps({"alertas": alerts[-20:], "total": len(alerts)}, indent=2, default=str))

    elif args.command == "detect":
        trend_path = Path(config.deploy_dir) / "trends.ndjson"
        if not trend_path.exists():
            print(json.dumps({"error": "No hay datos de tendencia. Ejecuta pipeline primero."}, indent=2))
            sys.exit(1)
        lines = [json.loads(l) for l in trend_path.read_text().strip().splitlines() if l.strip()]
        cal = Calibration(config)
        res = cal.detect(lines)
        print(json.dumps(res, indent=2, default=str))

if __name__ == "__main__":
    main()
