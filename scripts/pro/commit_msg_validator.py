"""Validador de mensajes de commit (conventional commits).

Uso:
    python3 scripts/pro/commit_msg_validator.py <mensaje>
    python3 scripts/pro/commit_msg_validator.py --read-file <ruta>

Exit 0: válido. Exit 1: inválido (mensaje a stderr).
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

CONVENTIONAL_RE = re.compile(
    r"^(feat|fix|test|docs|refactor|chore|perf|build|ci|style|revert)"
    r"(\([a-z0-9_.-]+\))?"
    r"!?: .{10,}$",
    re.IGNORECASE,
)

FORBIDDEN_RE = re.compile(
    r"^(wip|tmp|temp|work in progress|update\s*$|asdf|merge branch)",
    re.IGNORECASE,
)

_MAX_FIRST_LINE = 100


def validate(message: str) -> tuple[bool, str]:
    """Valida un mensaje de commit. Retorna (ok, motivo).

    Reglas:
    - Primera línea: tipo(scope)?: descripción (>= 10 chars)
    - Sin líneas de solo whitespace duplicadas consecutivas
    - Máximo 100 chars en la primera línea
    - Rechaza WIP/TMP/placeholder
    """
    lines = message.splitlines()
    first = lines[0].strip() if lines else ""

    if not first:
        return False, "mensaje vacío"
    if FORBIDDEN_RE.match(first):
        return False, f"placeholder detectado: '{first[:50]}'"
    if len(first) > _MAX_FIRST_LINE:
        return False, f"primera línea demasiado larga ({len(first)} > {_MAX_FIRST_LINE})"
    if not CONVENTIONAL_RE.match(first):
        return (
            False,
            "formato: tipo(scope)?: descripción — "
            "tipo en {feat,fix,test,docs,refactor,chore,perf,build,ci,style,revert}, "
            "descripción >= 10 chars",
        )
    prev_blank = False
    for line in lines[1:]:
        if not line.strip():
            if prev_blank:
                return False, "líneas en blanco consecutivas en el cuerpo"
            prev_blank = True
        else:
            prev_blank = False
    return True, "ok"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("message", nargs="?", help="mensaje a validar")
    parser.add_argument("--read-file", help="leer mensaje desde archivo (modo hook)")
    args = parser.parse_args(argv)

    if args.read_file:
        try:
            with Path(args.read_file).open(encoding="utf-8") as f:
                message = f.read()
        except OSError as e:
            print(f"commit-msg: no se pudo leer {args.read_file}: {e}", file=sys.stderr)
            return 1
    elif args.message:
        message = args.message
    else:
        parser.error("se requiere 'message' o '--read-file'")

    ok, reason = validate(message)
    if not ok:
        print(f"commit-msg: mensaje de commit rechazado — {reason}", file=sys.stderr)
        print("  Ejemplo: fix(cli): mensaje descriptivo de al menos 10 caracteres", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
