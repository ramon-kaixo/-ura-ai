"""CLI main — parser, entry point, shared helpers."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

DEFAULT_DB_PATH = Path.home() / "URA" / "ura_ia_1972" / "knowledge" / "knowledge.db"
SCHEMA_FILE = Path(__file__).resolve().parent.parent.parent.parent / "schemas" / "knowledge_graph.sql"


def _resolve_db_path(args) -> Path:
    if hasattr(args, "db_path") and args.db_path:
        return Path(args.db_path)
    env = os.environ.get("URA_KNOWLEDGE_DB")
    if env:
        return Path(env)
    return DEFAULT_DB_PATH


def _get_conn(db_path: Path):
    from knowledge.engine.connection import open_db

    db_path.parent.mkdir(parents=True, exist_ok=True)
    return open_db(db_path)


def add_parser_init(sub):
    p_init = sub.add_parser("init", help="Create/reset knowledge.db")
    p_init.set_defaults(func=cmd_init)

def add_parser_verify(sub):
    p_verify = sub.add_parser("verify", help="Full graph integrity check")
    p_verify.add_argument("--source-dir", help="Path to source/ for hash verification")
    p_verify.set_defaults(func=cmd_verify)

def add_parser_status(sub):
    p_status = sub.add_parser("status", help="Show graph stats")
    p_status.set_defaults(func=cmd_status)


def main() -> int:
    _init_bus()
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


def _init_bus() -> None:
    """Inicializa el Event Bus global y registra suscriptores."""
    from knowledge.engine.eventbus import get_bus
    from knowledge.engine.subscribers import subscribe_all

    db = Path(os.environ.get("URA_KNOWLEDGE_DB", "")) or DEFAULT_DB_PATH
    bus = get_bus()
    subscribe_all(bus, db, Path(os.environ.get("URA_SOURCE_DIR", "") or "."))


if __name__ == "__main__":
    sys.exit(main())


if __name__ == "__main__":
    sys.exit(main())