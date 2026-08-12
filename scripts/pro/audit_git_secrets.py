#!/usr/bin/env python3
"""audit_git_secrets.py — Escaneo de secretos en el HISTORIAL git (TASK-20260812-024).

Complementa a audit_secrets.py (que solo mira el código actual): busca
credenciales/tokens/claves que hayan quedado incrustados en commits pasados
(la fuga no desaparece al borrarla del HEAD: sigue en git log).

Uso:
    python3 scripts/pro/audit_git_secrets.py                 # escaneo completo
    python3 scripts/pro/audit_git_secrets.py --json          # salida JSON
    python3 scripts/pro/audit_git_secrets.py --max-commits 500   # límite
    python3 scripts/pro/audit_git_secrets.py --only HEAD~20..HEAD  # rango

Es 100% read-only: no modifica el historial ni el working tree.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys

PATRONES: list[tuple[str, re.Pattern[str]]] = [
    ("aws_access_key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("aws_secret", re.compile(r"(?i)aws_secret(_access)?_?key\s*[:=]\s*['\"][A-Za-z0-9+/=]{20,}['\"]")),
    ("github_token", re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}")),
    ("github_oauth", re.compile(r"(?i)(github|gh)_?(token|oauth)\s*[:=]\s*['\"][a-z0-9]{35,}['\"]")),
    ("slack_token", re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}")),
    ("telegram_bot", re.compile(r"\d{8,10}:[A-Za-z0-9_-]{30,}")),
    ("private_key_begin", re.compile(r"-----BEGIN (RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----")),
    ("password_assign", re.compile(r"(?i)(password|passwd|pwd)\s*[:=]\s*['\"][^'\"]{6,}['\"]")),
    ("api_key_assign", re.compile(r"(?i)(api[_-]?key|apikey|secret[_-]?key|client[_-]?secret)\s*[:=]\s*['\"][A-Za-z0-9_\-\.]{12,}['\"]")),
    ("bearer_token", re.compile(r"(?i)['\"]authorization['\"]\s*:\s*['\"]bearer\s+[A-Za-z0-9._-]{10,}['\"]")),
    ("db_url_creds", re.compile(r"(?i)(postgres|mysql|mongodb)(\+[a-z]+)?://[^:\s/]+:[^@\s/]+@")),
    ("secret_env_export", re.compile(r"(?i)(export\s+)?[A-Z0-9_]{4,}_(SECRET|PASSWORD|TOKEN|API_KEY|PASSWD|PWD)\s*=\s*['\"][^'\"]{6,}['\"]")),
]

RELACIONADOS = re.compile(r"(?i)secret|password|token|credential|api[_-]?key|private key")


def _pares_git(*args: str) -> list[tuple[str, str]]:
    """git log en formato nombre-valor: [(clave, valor), ...] por commit."""
    cmd = ["git", "log", "--all", "--no-merges", "--pretty=format:%H%x00%an%x00%ad", *args]
    out = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if out.returncode != 0:
        return []
    pares: list[tuple[str, str]] = []
    for linea in out.stdout.splitlines():
        partes = linea.split("\x00")
        if len(partes) >= 2:
            pares.append((partes[0], partes[1]))
    return pares


def escanear(max_commits: int | None = None, rango: str | None = None) -> list[dict]:
    """Escanea el historial y devuelve los hallazgos.

    Para cada commit se extrae el diff completo (git show) y se aplican los
    patrones línea a línea, con contexto del nombre de archivo cuando git lo
    intercala (líneas '+++ b/...').
    """
    args: list[str] = []
    if rango:
        args.append(rango)
    elif max_commits:
        args = [f"-{max_commits}"]
    commits = _pares_git(*args)
    if not commits:
        return []

    hallazgos: list[dict] = []
    for sha, _autor in commits:
        show = subprocess.run(
            ["git", "show", "--format=", "--no-ext-diff", sha],
            capture_output=True,
            text=True,
            check=False,
        )
        if show.returncode != 0:
            continue
        archivo_actual = ""
        registrado: set[tuple[str, int]] = set()
        for i, linea in enumerate(show.stdout.splitlines()):
            if linea.startswith("+++ ") or linea.startswith("--- "):
                archivo_actual = linea[4:].strip().lstrip("b/")
                continue
            if not linea.startswith("+") or linea.startswith("+++"):
                continue
            num_linea = i + 1
            for nombre, patron in PATRONES:
                if patron.search(linea):
                    clave = (archivo_actual, num_linea)
                    if clave in registrado:
                        continue
                    registrado.add(clave)
                    hallazgos.append(
                        {
                            "commit": sha,
                            "archivo": archivo_actual,
                            "linea": num_linea,
                            "tipo": nombre,
                            "contenido": linea[1:].strip()[:120],
                        },
                    )
                    break
    return hallazgos


def es_repo_git() -> bool:
    return (
        subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            capture_output=True,
            check=False,
        ).returncode
        == 0
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Auditoría de secretos en historial git")
    parser.add_argument("--json", action="store_true", help="salida JSON")
    parser.add_argument("--max-commits", type=int, default=None, help="límite de commits a auditar")
    parser.add_argument("--only", default=None, help="rango git (p.ej. HEAD~20..HEAD)")
    parser.add_argument("--falsos-positivos", action="store_true", help="mostrar líneas solo relacionadas (informe de ruido)")
    parser.add_argument("--fail", action="store_true", help="exit 1 si hay hallazgos (modo CI)")
    args = parser.parse_args()

    if not es_repo_git():
        print("ERROR: no hay repo git en el directorio actual", file=sys.stderr)
        sys.exit(1)

    hallazgos = escanear(max_commits=args.max_commits, rango=args.only)

    # Filtro de verbosidad: PATRONES son señal fuerte; RELACIONADOS solo con flag
    if args.falsos_positivos:
        hallazgos = [
            h for h in hallazgos
            if h["tipo"] == "password_assign" and RELACIONADOS.search(h["contenido"])
        ]

    if args.json:
        print(json.dumps(hallazgos, indent=2, ensure_ascii=False))
        if args.fail and hallazgos:
            sys.exit(1)
        return

    if not hallazgos:
        print("OK: no se encontraron secretos en el historial filtrando por fuertes")
        return

    print(f"AVISO: {len(hallazgos)} posibles secretos en el historial:")
    for h in hallazgos[:100]:
        print(
            f"  {h['commit'][:8]} | {h['archivo']}:{h['linea']} "
            f"| {h['tipo']} | {h['contenido'][:60]}",
        )
    if len(hallazgos) > 100:
        print(f"  ... y {len(hallazgos) - 100} más")
    if args.fail:
        sys.exit(1)


if __name__ == "__main__":
    main()
