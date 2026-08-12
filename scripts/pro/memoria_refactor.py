#!/usr/bin/env python3
"""memoria_refactor.py — Memoria persistente del refactorizador (TASK-20260812-020).

Filosofía (RAMON): mínimo LLM + máximo determinismo, y el determinismo con
memoria + reglas + revisiones. Esta memoria da "conciencia" al pipeline:

  - Recuerda cada intento de refactor por función (modelo, resultado, motivo).
  - Evita repetir fallos conocidos (una función rechazada 2 veces con el mismo
    modelo no se reintenta con él).
  - Permite revisiones: el registro es inspeccionable y auditable.

Archivo: <URA_ROOT>/.nervioso/refactor_memoria.json
"""

from __future__ import annotations

import json
import time
from pathlib import Path


def _ruta_memoria(ura_root: Path) -> Path:
    return ura_root / ".nervioso" / "refactor_memoria.json"


def cargar_memoria(ura_root: Path) -> dict:
    """Carga la memoria persistente. Si no existe, devuelve vacía."""
    ruta = _ruta_memoria(ura_root)
    if not ruta.exists():
        return {"funciones": {}, "metricas": {"intentos": 0, "exitos": 0, "rechazos": 0}}
    try:
        return json.loads(ruta.read_text())
    except (json.JSONDecodeError, OSError):
        return {"funciones": {}, "metricas": {"intentos": 0, "exitos": 0, "rechazos": 0}}


def guardar_memoria(ura_root: Path, memoria: dict) -> None:
    """Persiste la memoria de forma atómica (write + rename)."""
    ruta = _ruta_memoria(ura_root)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    tmp = ruta.with_suffix(".tmp")
    tmp.write_text(json.dumps(memoria, indent=2, ensure_ascii=False))
    tmp.replace(ruta)


def registrar_intento(
    ura_root: Path,
    funcion_id: str,
    modelo: str,
    resultado: str,  # "exito" | "rechazo" | "error"
    motivo: str = "",
) -> dict:
    """Registra un intento de refactor y actualiza métricas.

    funcion_id: 'ruta:nombre' (identificador único de la función).
    """
    memoria = cargar_memoria(ura_root)
    funciones = memoria.setdefault("funciones", {})
    entrada = funciones.setdefault(
        funcion_id,
        {"intentos": [], "estado": "sin_intentar", "mejor_modelo": ""},
    )
    entrada["intentos"].append(
        {
            "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
            "modelo": modelo,
            "resultado": resultado,
            "motivo": motivo,
        },
    )
    # Estado derivado (regla simple): éxito tiene prioridad; si no, 2 rechazos
    # seguidos marcan la función como "necesita_otro_modelo".
    if any(i["resultado"] == "exito" for i in entrada["intentos"]):
        entrada["estado"] = "completada"
    else:
        ultimos = entrada["intentos"][-3:]
        rechazos_recientes = sum(1 for i in ultimos if i["resultado"] == "rechazo")
        if rechazos_recientes >= 2:
            entrada["estado"] = "necesita_otro_modelo"
        else:
            entrada["estado"] = "pendiente"

    m = memoria.setdefault("metricas", {"intentos": 0, "exitos": 0, "rechazos": 0})
    m["intentos"] += 1
    if resultado == "exito":
        m["exitos"] += 1
    elif resultado == "rechazo":
        m["rechazos"] += 1

    guardar_memoria(ura_root, memoria)
    return memoria


def consultar_funcion(ura_root: Path, funcion_id: str) -> dict:
    """Consulta el historial de una función (para no repetir fallos)."""
    memoria = cargar_memoria(ura_root)
    return memoria.get("funciones", {}).get(funcion_id, {"intentos": [], "estado": "sin_intentar"})


def resumen(ura_root: Path) -> dict:
    """Resumen de métricas para reportes y revisiones."""
    memoria = cargar_memoria(ura_root)
    return memoria.get("metricas", {"intentos": 0, "exitos": 0, "rechazos": 0})
