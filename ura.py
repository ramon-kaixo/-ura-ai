#!/usr/bin/env python3
"""URA CLI — Punto de entrada central (wrapper hacia motor/cli/main.py)."""

import sys
from pathlib import Path

# Guard: remove editable install finder to guarantee single import source.
for _f in list(sys.meta_path):
    if "__editable" in str(_f):
        sys.meta_path.remove(_f)
for _h in list(sys.path_hooks):
    if "__editable" in str(_h):
        sys.path_hooks.remove(_h)
_repo = str(Path(__file__).resolve().parent)
if _repo not in sys.path:
    sys.path.insert(0, _repo)
del _f, _h, _repo

from motor.cli.main import main as _motor_main

HELP = """URA CLI v3.0

  Comandos (URA class):
    finalize [-m "msg"]   Pipeline completo: test + commit + push
    test                   Validar schema, config, router, mantenimiento
    clean [-d]             Mantenimiento de disco (-d = dry-run)
    rotate                 Rotar logs
    snapshot               Guardar estado del repo
    snc                    Estado del Sistema Nervioso Central
    health                 Salud del GX10 (disco, RAM, VRAM)
    alerts                 Sincronizar logs críticos desde GX10
    index [--force]        Indexar documentos en memoria RAG
    ask "pregunta"         Consultar documentos indexados
    memory                 Estadisticas de memoria RAG
    doctor                 Diagnóstico completo del sistema
    metrics                Métricas del router (modelos, latencia)
    status                 Dashboard unificado (SNC + Git + Config)

  Comandos (Knowledge Engine):
    pipeline               Ejecutar pipeline completo
    scan                   Solo escanear
    diagnose               Solo diagnosticar
    ...

  Ejemplo:
    python3 ura.py finalize -m "fix: corrige cache de prompts"
"""


def main() -> int | None:
    if len(sys.argv) < 2:
        return 0

    if sys.argv[1] in ("-h", "--help"):
        return 0

    if sys.argv[1] == "status":
        sys.argv[1] = "dashboard"

    _motor_main()
    return None


if __name__ == "__main__":
    sys.exit(main())
