#!/usr/bin/env python3
"""Agregador de Watermarks — Detecta patrones sistémicos y gestiona incidencias.

Lee watermarks del pipeline, detecta errores que se repiten ≥3 ciclos,
genera reglas de reparación automática (auto_reglas.py), y escala a
diagnóstico de prompt engineering.

Uso:
  python3 watermark_aggregator.py                          # Ver estado
  python3 watermark_aggregator.py --marcar-reparado <id>   # Marcar watermark como reparado
  python3 watermark_aggregator.py --limpiar                 # Limpiar watermarks resueltos
  python3 watermark_aggregator.py --auto-reglas             # Estado + generar reglas
"""

PLUGIN = {
    "name": "watermark_aggregator",
    "phase": "post",
    "timeout": 30,
    "blocking": False,
    "needs_file": False,
}

import contextlib
import json
import os
import subprocess
import time
from collections import Counter
from pathlib import Path

WATERMARKS_PATH = Path(os.environ.get("WATERMARKS_PATH", ".nervioso/watermarks.json"))
F821_BASELINE = Path(os.environ.get("F821_BASELINE", ".nervioso/f821_baseline.json"))


def cargar() -> dict:
    if WATERMARKS_PATH.exists():
        return json.loads(WATERMARKS_PATH.read_text())
    return {"watermarks": [], "patrones_sistemicos": [], "ultima_inspeccion": ""}


def guardar(data: dict) -> None:
    WATERMARKS_PATH.parent.mkdir(parents=True, exist_ok=True)
    WATERMARKS_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def detectar_patrones(data: dict, umbral: int = 3) -> list[dict]:
    """Detecta errores que aparecen ≥umbral veces (patrón sistémico)."""
    watermarks = data.get("watermarks", [])
    contador = Counter()
    detalles = {}

    for w in watermarks:
        if w.get("reparado", False):
            continue
        clave = f"{w.get('tipo', '')}:{w.get('mensaje', '')[:80]}"
        contador[clave] += 1
        if clave not in detalles:
            detalles[clave] = {
                "tipo": w.get("tipo", ""),
                "mensaje": w.get("mensaje", "")[:80],
                "archivos": [],
            }
        detalles[clave]["archivos"].append(w.get("archivo", ""))

    patrones = []
    for clave, count in contador.most_common():
        if count >= umbral:
            d = detalles[clave]
            patrones.append(
                {
                    "tipo": d["tipo"],
                    "mensaje": d["mensaje"],
                    "apariciones": count,
                    "archivos": list(set(d["archivos"])),
                    "diagnostico": _diagnosticar(d["tipo"]),
                },
            )

    return patrones


def _diagnosticar(tipo: str) -> str:
    diagnosticos = {
        "F821": "El refactorizador está omitiendo imports o variables que la función original usaba. Revisar prompt: incluir 'PRESERVA todos los imports y variables globales'.",
        "SYNTAX": "El LLM devolvió código con errores de sintaxis. El prompt debe ser más restrictivo.",
        "BROKEN_STR": "Cadenas de texto mal cerradas. Añadir verificación de triples comillas en el prompt.",
        "DANGLING": "El refactor creó bloques huérfanos. Dividir funciones respetando la indentación original.",
        "EMPTY_BODY": "El LLM dejó funciones vacías. Aumentar num_predict o reducir complejidad del fragmento.",
        "LARGE_FUNC": "Las helpers generadas siguen siendo grandes. Reducir el límite de 30 líneas por helper.",
        "NESTING": "Anidamiento excesivo en el refactor. Forzar extracción de más funciones intermedias.",
        "TYPE_MISMATCH": "El refactor cambió tipos de variables. Revisar contexto de anotaciones.",
        "SECURITY": "El LLM introdujo prácticas inseguras. Añadir advertencia de seguridad en el prompt.",
    }
    return diagnosticos.get(tipo, f"Patrón no clasificado: {tipo}. Revisar manualmente.")


def marcar_reparado(watermark_id: str) -> bool:
    data = cargar()
    for w in data.get("watermarks", []):
        if w.get("watermark_id") == watermark_id:
            w["reparado"] = True
            w["fecha_reparacion"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            guardar(data)
            return True
    return False


def limpiar_resueltos():
    """Elimina watermarks reparados que tienen más de 7 días."""
    data = cargar()
    ahora = time.time()
    conservar = []
    for w in data.get("watermarks", []):
        if w.get("reparado", False) and "timestamp" in w:
            try:
                ts = time.mktime(time.strptime(w["timestamp"], "%Y-%m-%dT%H:%M:%S"))
                if ahora - ts > 7 * 86400:
                    continue  # eliminar: más de 7 días reparado
            except Exception:
                pass
        conservar.append(w)
    data["watermarks"] = conservar
    guardar(data)
    return len(conservar)


def estado() -> dict:
    data = cargar()
    watermarks = data.get("watermarks", [])
    activos = [w for w in watermarks if not w.get("reparado", False)]
    resueltos = [w for w in watermarks if w.get("reparado", False)]
    patrones = detectar_patrones(data)

    return {
        "total_watermarks": len(watermarks),
        "activos": len(activos),
        "resueltos": len(resueltos),
        "patrones_sistemicos": patrones,
        "ultima_inspeccion": data.get("ultima_inspeccion", ""),
        "top_tipos": dict(Counter(w.get("tipo", "") for w in activos).most_common(5)),
    }


def scan_project() -> None:
    from pathlib import Path as _Path

    root = _Path.home() / "URA/ura_ia_1972"
    list(root.rglob("*.py"))


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Agregador de Watermarks")
    parser.add_argument("--scan", action="store_true", help="Escanear todo el proyecto")
    parser.add_argument("--marcar-reparado", type=str, help="ID del watermark a marcar reparado")
    parser.add_argument("--limpiar", action="store_true", help="Limpiar resueltos viejos")
    parser.add_argument("--auto-reglas", action="store_true", help="Estado + generar reglas auto")
    parser.add_argument("--json", action="store_true", help="Salida JSON")
    args = parser.parse_args()
    if args.scan:
        scan_project()
        return

    if args.marcar_reparado:
        marcar_reparado(args.marcar_reparado)
        return

    if args.limpiar:
        limpiar_resueltos()
        return

    e = estado()

    # Generar reglas automáticas si hay patrones sistémicos
    if args.auto_reglas and e.get("patrones_sistemicos"):
        with contextlib.suppress(Exception):
            subprocess.run(
                ["python3", "scripts/pro/auto_reglas.py", "--generar"],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )

    if args.json:
        pass
    else:
        if e["top_tipos"]:
            for _t, _n in e["top_tipos"].items():
                pass
        if e["patrones_sistemicos"]:
            for _p in e["patrones_sistemicos"]:
                pass


if __name__ == "__main__":
    main()
