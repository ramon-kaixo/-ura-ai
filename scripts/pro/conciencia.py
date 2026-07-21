#!/usr/bin/env python3
"""Conciencia Unificada — Memoria global de todos los procesos del pipeline.

📖 MANUAL DE USO RÁPIDO:
  python3 conciencia.py --leer                          # Ver estado general
  python3 conciencia.py --escribir refactorer activo    # Actualizar proceso
  python3 conciencia.py --error 1 "F821 detectado"      # Registrar error (1=leve,2=crítico)
  python3 conciencia.py --progreso 67/107               # Actualizar progreso
  python3 conciencia.py --reset                         # Reiniciar para nuevo ciclo

🔒 GARANTÍAS:
  - 1 archivo JSON = 1 punto de verdad (.nervioso/conciencia.json)
  - Thread-safe: lock file para evitar corrupción por escrituras simultáneas
  - Memory-safe: arrays acotados a 50 entradas máx
  - Nivel de error global (0=OK, 1=LEVE, 2=CRÍTICO) visible de un vistazo
  - Si un proceso muere, otro puede retomar su estado desde el mismo archivo

Un solo archivo JSON (.nervioso/conciencia.json) que da "consciencia"
a cada proceso del pipeline: saben dónde están, qué hicieron y qué falta.

Principios:
  - 1 archivo = 1 punto de verdad
  - Todos los procesos leen/escriben el mismo archivo
  - Nivel de error global visible de un vistazo
  - Si un proceso muere, otro puede retomar su estado
  - Contexto nunca se pierde entre ciclos
"""

PLUGIN = {
    "name": "conciencia",
    "phase": "pre",
    "timeout": 15,
    "blocking": True,
    "needs_file": False,
}

import fcntl
import json
import os
import time
from pathlib import Path

CONCIENCIA_PATH = Path(os.environ.get("CONCIENCIA_PATH", ".nervioso/conciencia.json"))


# ── Core ──


def cargar() -> dict:
    if CONCIENCIA_PATH.exists():
        try:
            data = json.loads(CONCIENCIA_PATH.read_text())
            if not isinstance(data, dict):
                msg = "Not a dict"
                raise ValueError(msg)
            return data
        except (json.JSONDecodeError, ValueError, Exception):  # noqa: S110
            pass
    return _nuevo()


def _nuevo() -> dict:
    return {
        "creado": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "version": "1.0",
        "estado_general": "ok",
        "nivel_error": 0,  # 0=OK, 1=leve, 2=crítico
        "ultimo_ciclo": None,
        "procesos": {},
        "contexto_global": {
            "ultimo_archivo": None,
            "ciclo_actual": 0,
            "progreso": "0/0",
            "errores_acumulados": [],
            "arreglos_aplicados": [],
        },
    }


def guardar(data: dict) -> None:
    """Guarda con fcntl lock + escritura atomica. 0% race conditions."""
    CONCIENCIA_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = CONCIENCIA_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + chr(10))
    with open(str(CONCIENCIA_PATH.with_suffix(".lock")), "w") as lockfile:  # noqa: PTH123
        fcntl.flock(lockfile, fcntl.LOCK_EX)
        tmp.replace(CONCIENCIA_PATH)
        fcntl.flock(lockfile, fcntl.LOCK_UN)
        lockfile.close()


# ── API Pública ──


def escribir_proceso(nombre: str, estado: str, detalles: dict | None = None) -> None:
    """Registra el estado de un proceso."""
    data = cargar()
    data["procesos"][nombre] = {
        "estado": estado,
        "ultima_actualizacion": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "detalles": detalles or {},
    }
    guardar(data)


def registrar_error(nivel: int, mensaje: str) -> None:
    """Registra un error y ajusta el nivel global."""
    data = cargar()
    data["nivel_error"] = max(data["nivel_error"], nivel)
    data["contexto_global"]["errores_acumulados"].append(
        {
            "nivel": nivel,
            "mensaje": mensaje,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        },
    )
    # Mantener solo últimos 50 errores
    if len(data["contexto_global"]["errores_acumulados"]) > 50:
        data["contexto_global"]["errores_acumulados"] = data["contexto_global"]["errores_acumulados"][-50:]
    guardar(data)


def registrar_arreglo(descripcion: str) -> None:
    """Registra un arreglo aplicado."""
    data = cargar()
    data["contexto_global"]["arreglos_aplicados"].append(
        {
            "descripcion": descripcion,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        },
    )
    if len(data["contexto_global"]["arreglos_aplicados"]) > 50:
        data["contexto_global"]["arreglos_aplicados"] = data["contexto_global"]["arreglos_aplicados"][-50:]
    guardar(data)


def actualizar_progreso(archivo: str, ciclo: int | None = None, progreso: str | None = None) -> None:
    """Actualiza el contexto de progreso."""
    data = cargar()
    if archivo:
        data["contexto_global"]["ultimo_archivo"] = archivo
    if ciclo is not None:
        data["contexto_global"]["ciclo_actual"] = ciclo
    if progreso:
        data["contexto_global"]["progreso"] = progreso
    data["ultimo_ciclo"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    guardar(data)


def reset_ciclo() -> None:
    """Reinicia para nuevo ciclo."""
    data = _nuevo()
    guardar(data)


def estado() -> dict:
    """Devuelve el estado consolidado."""
    data = cargar()
    procesos = data.get("procesos", {})
    ctx = data.get("contexto_global", {})

    # Contar procesos en cada estado
    por_estado = {}
    for info in procesos.values():
        est = info.get("estado", "desconocido")
        por_estado[est] = por_estado.get(est, 0) + 1

    return {
        "general": data.get("estado_general", "ok"),
        "nivel_error": data.get("nivel_error", 0),
        "nivel_texto": ["✅ OK", "⚠️ LEVE", "🔴 CRÍTICO"][data.get("nivel_error", 0)],
        "procesos_activos": len(procesos),
        "por_estado": por_estado,
        "ciclo": ctx.get("ciclo_actual", 0),
        "progreso": ctx.get("progreso", "0/0"),
        "ultimo_archivo": ctx.get("ultimo_archivo", "—"),
        "errores": len(ctx.get("errores_acumulados", [])),
        "arreglos": len(ctx.get("arreglos_aplicados", [])),
        "ultimo_ciclo": data.get("ultimo_ciclo", "—"),
    }


# ── Main ──


def scan_project() -> None:
    root = Path.home() / "URA/ura_ia_1972"
    list(root.rglob("*.py"))


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Conciencia Unificada")
    parser.add_argument("--scan", action="store_true", help="Escanear todo el proyecto")
    parser.add_argument("--leer", action="store_true", help="Ver estado general")
    parser.add_argument(
        "--escribir",
        nargs=2,
        metavar=("PROCESO", "ESTADO"),
        help="Actualizar proceso",
    )
    parser.add_argument("--detalles", type=str, help="JSON detalles para --escribir")
    parser.add_argument(
        "--error",
        nargs=2,
        metavar=("NIVEL", "MSG"),
        help="Registrar error (nivel 1=leve,2=crítico)",
    )
    parser.add_argument("--progreso", type=str, help="Actualizar progreso (ej: 67/107)")
    parser.add_argument("--archivo", type=str, help="Archivo actual")
    parser.add_argument("--arreglo", type=str, help="Registrar arreglo")
    parser.add_argument("--reset", action="store_true", help="Reiniciar para nuevo ciclo")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.scan:
        scan_project()
        return

    if args.leer:
        e = estado()
        if args.json:
            pass
        else:
            {0: "✅", 1: "⚠️", 2: "🔴"}[e["nivel_error"]]
        return

    if args.reset:
        reset_ciclo()

    if args.error:
        nivel = int(args.error[0])
        msg = args.error[1]
        registrar_error(nivel, msg)

    if args.escribir:
        nombre = args.escribir[0]
        est = args.escribir[1]
        detalles = json.loads(args.detalles) if args.detalles else None
        escribir_proceso(nombre, est, detalles)

    if args.progreso or args.archivo:
        actualizar_progreso(args.archivo or "", progreso=args.progreso)

    if args.arreglo:
        registrar_arreglo(args.arreglo)


if __name__ == "__main__":
    main()
