#!/usr/bin/env python3
"""CLI principal del Motor URA."""

import logging
import sys
from collections.abc import Callable
from typing import Any

from motor.cli.cmd_diag import (
    cmd_alerta,
    cmd_check,
    cmd_detect,
    cmd_health_check,
    cmd_history,
    cmd_learn,
    cmd_verify,
)
from motor.cli.cmd_pipeline import cmd_calibrate, cmd_diagnose, cmd_pipeline, cmd_scan
from motor.cli.cmd_status import (
    cmd_cross,
    cmd_graph,
    cmd_perf,
    cmd_status,
    cmd_summarise,
    cmd_trend,
)
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
    cmd_snapshot,
    cmd_snc,
    cmd_test,
)
from motor.cli.cmd_utils import cmd_bench, cmd_notify, cmd_qdrant_backup
from motor.core.config import UraConfig

# Type aliases for CLI commands
CliCmd = Callable[[UraConfig, Any], None]
UraCmd = Callable[[UraConfig, list[str]], int]

COMMANDS: dict[str, CliCmd] = {
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

URA_COMMANDS: dict[str, UraCmd] = {
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
}


def _build_parser() -> Any:
    import argparse

    parser = argparse.ArgumentParser(
        prog="ura",
        description="URA Motor CLI — Pipeline, diagnóstico, estado y comandos URA",
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Ruta a config.yaml (default: motor/core/config.yaml)",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Nivel de logging",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    for name in COMMANDS:
        sub.add_parser(name, help=f"{name} — comando del motor")

    for name in URA_COMMANDS:
        s = sub.add_parser(name, help=f"{name} — comando URA")
        s.add_argument("raw", nargs="*", help="Raw arguments (passthrough)")

    return parser


def _setup_logging(level: str) -> None:
    """Configura logging compatible con tests existentes."""
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    h = logging.StreamHandler(sys.stderr)
    h.setFormatter(logging.Formatter("%(name)s %(levelname)s %(message)s"))

    root = logging.getLogger()
    root.addHandler(h)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))


def main() -> None:
    args = _build_parser().parse_args()
    _setup_logging(args.log_level)
    config = UraConfig.load()
    config.log_level = args.log_level

    if args.command in COMMANDS:
        COMMANDS[args.command](config, args)
    elif args.command in URA_COMMANDS:
        raw_args = getattr(args, "raw", [])
        sys.exit(URA_COMMANDS[args.command](config, raw_args))


if __name__ == "__main__":
    main()
