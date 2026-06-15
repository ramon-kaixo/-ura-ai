import argparse, sys, logging
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('httpcore').setLevel(logging.WARNING)
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from core.config import UraConfig
from cli.cmd_pipeline import cmd_pipeline, cmd_scan, cmd_diagnose, cmd_calibrate
from cli.cmd_status import cmd_status, cmd_cross, cmd_trend, cmd_graph, cmd_perf, cmd_summarise
from cli.cmd_diag import cmd_history, cmd_check, cmd_verify, cmd_detect, cmd_learn, cmd_alerta, cmd_health_check
from cli.cmd_utils import cmd_notify, cmd_qdrant_backup, cmd_bench

COMMANDS = {
    "pipeline": cmd_pipeline, "scan": cmd_scan, "diagnose": cmd_diagnose, "calibrate": cmd_calibrate,
    "status": cmd_status, "cross": cmd_cross, "trend": cmd_trend, "graph": cmd_graph,
    "perf": cmd_perf, "summarise": cmd_summarise,
    "history": cmd_history, "check": cmd_check, "verify": cmd_verify, "detect": cmd_detect,
    "learn": cmd_learn, "alerta": cmd_alerta, "health-check": cmd_health_check,
    "qdrant-backup": cmd_qdrant_backup, "notify": cmd_notify, "bench": cmd_bench,
}


def _setup_logging(level: str):
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)
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
    sp_check = sub.add_parser("check", help="Preflight check / purge")
    sp_check.add_argument("--purge", action="store_true", help="Purgar huerfanos: stale PIDs, failed units, dangling Docker")
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
    sub.add_parser("bench", help="Benchmark de rendimiento del pipeline")

    cal = sub.add_parser("calibrate", help="Generar baseline desde estado actual")
    cal.add_argument("--force", action="store_true", help="Sobreescribir baseline existente")

    args = parser.parse_args()
    _setup_logging(args.log_level)
    config = UraConfig.load(args.config)
    config.log_level = args.log_level

    COMMANDS[args.command](config, args)


if __name__ == "__main__":
    main()
