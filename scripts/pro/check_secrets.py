#!/usr/bin/env python3
"""check_secrets.py — Pre-commit hook: detecta secrets hardcodeados.

No imprime el valor del secreto: solo el fichero y el número de línea.

Los patrones de asignación excluyen las referencias a variables o comandos
(p. ej. ``$MAC_API_KEY`` o ``$(cat ~/.syncthing_api_key)``) mediante un
lookahead negativo sobre ``$``, de modo que el patrón seguro no se bloquea.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"sk-or-v1-[A-Za-z0-9]{20,}"),
    re.compile(r"apiKey[\"\' ]*:[\"\' ][A-Za-z0-9_-]{20,}"),
    re.compile(r"MAC_API_KEY\s*=\s*[\"'](?!\$)[^\"'\s]{8,}[\"']"),
    re.compile(r"X-API-Key:\s*[\"']?(?!\$)[A-Za-z0-9_\-]{16,}"),
    re.compile(r"GATEWAY_TOKEN\s*=\s*[\"'](?!\$)[^\"'\s]{8,}[\"']"),
    re.compile(r"PYPI_TOKEN\s*=\s*[\"'](?!\$)[^\"'\s]{8,}[\"']"),
)


def main(argv: list[str] | None = None) -> int:
    """Revisa los ficheros indicados; devuelve 1 si encuentra un secreto."""
    files = sys.argv[1:] if argv is None else argv
    encontrado = False
    for filepath in files:
        try:
            with Path(filepath).open(encoding="utf-8", errors="replace") as handle:
                for i, line in enumerate(handle, 1):
                    if any(pattern.search(line) for pattern in PATTERNS):
                        sys.stderr.write(f"{filepath}:{i}: posible secreto hardcodeado\n")
                        encontrado = True
        except OSError:
            continue
    return 1 if encontrado else 0


if __name__ == "__main__":
    sys.exit(main())
