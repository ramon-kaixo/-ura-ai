import argparse
import logging
import sys

from motor.cli.cmd_diag import cmd_alerta, cmd_check, cmd_detect, cmd_health_check, cmd_history, cmd_learn, cmd_verify
from motor.cli.cmd_pipeline import cmd_calibrate, cmd_diagnose, cmd_pipeline, cmd_scan
from motor.cli.cmd_status import cmd_cross, cmd_graph, cmd_perf, cmd_status, cmd_summarise, cmd_trend
from motor.cli.cmd_ura import cmd_alerts as ura_cmd_alerts
from motor.cli.cmd_ura import (
    cmd_ask,
    cmd_dashboard,
    cmd_doctor,
    cmd_finalize,
    cmd_health,
    cmd_index,
    cmd_maintenance,
    cmd_memory,
    cmd_metrics,
    cmd_rotate,
    cmd_service,
    cmd_snapshot,
    cmd_snc,
    cmd_system,
    cmd_test,
)
from motor.cli.cmd_utils import cmd_bench, cmd_notify, cmd_qdrant_backup
from motor.core.config import UraConfig
from motor.observability.logging import setup_logging

COMMANDS = {
    "pipeline": cmd_pipeline,
    "scan": cmd_scan,
    "diagnose": cmd_diagnose,
    "calibrate": cmd_calibrate,
    "status": cmd_status,
    "cross": cmd_cross,
    "trend": cmd_trend,
    "graph": cmd_graph,
    "perf": cmd_perf,
    "summarise": cmd_summarise,
    "history": cmd_history,
    "check": cmd_check,
    "verify": cmd_verify,
    "detect": cmd_detect,
    "learn": cmd_learn,
    "alerta": cmd_alerta,
    "health-check": cmd_health_check,
    "qdrant-backup": cmd_qdrant_backup,
    "notify": cmd_notify,
    "bench": cmd_bench,
}

URA_COMMANDS: dict[str, object] = {
    "finalize": cmd_finalize,
    "test": cmd_test,
    "snapshot": cmd_snapshot,
    "maintenance": cmd_maintenance,
    "clean": cmd_maintenance,
    "rotate": cmd_rotate,
    "health": cmd_health,
    "alerts": ura_cmd_alerts,
    "logs": ura_cmd_alerts,
    "snc": cmd_snc,
    "heartbeat": cmd_snc,
    "doctor": cmd_doctor,
    "metrics": cmd_metrics,
    "dashboard": cmd_dashboard,
    "index": cmd_index,
    "ask": cmd_ask,
    "memory": cmd_memory,
    "system": cmd_system,
    "service": cmd_service,
}


def _setup_logging(level: str) -> None:
    setup_logging(
        level=level,
        fmt="%(name)s %(levelname)s %(message)s",
        handlers=[logging.StreamHandler(sys.stderr)],
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def main() -> None:
    parser = argparse.ArgumentParser(prog="ura", description="URA CLI — Conocimiento y Sistema")
    parser.add_argument("--config", default="", help="Ruta a config JSON")
    parser.add_argument("--log-level", default="INFO", help="Nivel de log")
    sub = parser.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("pipeline", help="Ejecutar pipeline completo")
    sp.add_argument("--dry-run", action="store_true", help="No ejecutar escaneo real")
    sub.add_parser("scan", help="Solo escanear")
    sub.add_parser("diagnose", help="Solo diagnosticar (requiere scan previo)")
    sub.add_parser("status", help="Estado unificado (Knowledge Engine)")
    sp_check = sub.add_parser("check", help="Preflight check / purge")
    sp_check.add_argument("--purge", action="store_true", help="Purgar huerfanos")
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

    for name in (
        "finalize",
        "test",
        "snapshot",
        "maintenance",
        "clean",
        "rotate",
        "health",
        "alerts",
        "logs",
        "snc",
        "heartbeat",
        "doctor",
        "metrics",
        "dashboard",
        "index",
        "ask",
        "memory",
        "system",
        "service",
    ):
        s = sub.add_parser(name)
        s.add_argument("raw", nargs="*", help="Raw arguments (passthrough)")

    args = parser.parse_args()
    _setup_logging(args.log_level)
    config = UraConfig.load(args.config)
    config.log_level = args.log_level

    if args.command in COMMANDS:
        COMMANDS[args.command](config, args)
    elif args.command in URA_COMMANDS:
        raw_args = getattr(args, "raw", [])
        sys.exit(URA_COMMANDS[args.command](config, raw_args))


if __name__ == "__main__":
    main()
