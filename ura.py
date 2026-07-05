#!/usr/bin/env python3
"""URA CLI — Punto de entrada central (wrapper hacia motor/cli/main.py)."""
import sys

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


def main():
    if len(sys.argv) < 2:
        print(HELP, file=sys.stderr)
        return 0

    if sys.argv[1] in ("-h", "--help"):
        print(HELP, file=sys.stderr)
        return 0

    if sys.argv[1] == "status":
        sys.argv[1] = "dashboard"

    _motor_main()


if __name__ == "__main__":
    sys.exit(main())
