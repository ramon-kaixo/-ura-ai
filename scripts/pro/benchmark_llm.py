#!/usr/bin/env python3
"""Benchmark del cliente LLM unificado (motor.core.llm).

Mide por separado:
  1. generate()  — latencia p50/p95/p99, throughput, tokens/s
  2. embed()     — latencia p50/p95/p99, throughput

Uso exclusivo de la API pública motor.core.llm.
Sin duplicación de llamadas HTTP.

Interpretación de métricas:
  p50 = rendimiento típico.
  p95 = latencia de cola habitual.
  p99 = puede contener outliers del entorno (carga del sistema,
        planificación, calentamiento del modelo, etc.) y debe
        interpretarse junto con el número de iteraciones.

Uso:
  python3 scripts/pro/benchmark_llm.py [--iterations N] [--output ruta.json]
"""

import argparse
import json
import logging
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from motor.core.llm import embed, generate

logging.basicConfig(level=logging.WARNING, format="%(message)s")
log = logging.getLogger("benchmark_llm")

PROMPT = "Explica brevemente qué es un sistema RAG (Retrieval-Augmented Generation) en no más de tres frases."
TEXTS = [
    "El sistema RAG combina recuperación de información con generación de lenguaje.",
    "Los embeddings permiten buscar por similitud semántica en bases vectoriales.",
    "Ollama ejecuta modelos de lenguaje localmente en CPU o GPU.",
]


def _percentile(data: list[float], p: float) -> float:
    if not data:
        return 0.0
    idx = max(0, min(len(data) - 1, int(len(data) * p / 100)))
    return sorted(data)[idx]


def _estimar_tokens(texto: str) -> int:
    return max(1, len(texto) // 4)


def bench_generate(n: int) -> dict:
    latencias: list[float] = []
    tokens_generados: list[int] = []
    exitosos = 0
    fallos = 0

    for i in range(n):
        t0 = time.monotonic()
        try:
            respuesta = generate(PROMPT)
            elapsed = (time.monotonic() - t0) * 1000
            if respuesta and not respuesta.startswith("Error:"):
                latencias.append(elapsed)
                tokens_generados.append(_estimar_tokens(respuesta))
                exitosos += 1
            else:
                fallos += 1
                log.warning("iter %d: respuesta inesperada: %s", i, respuesta[:80])
        except Exception as e:
            fallos += 1
            log.warning("iter %d: excepción: %s", i, e)

    if not latencias:
        return {"error": "sin llamadas exitosas", "total": n, "fallos": fallos}

    total_tokens = sum(tokens_generados)
    tiempo_total_seg = sum(latencias) / 1000
    return {
        "funcion": "generate",
        "modelo": "qwen2.5:3b",
        "iteraciones": n,
        "exitosos": exitosos,
        "fallos": fallos,
        "latencia_media_ms": statistics.mean(latencias),
        "latencia_p50_ms": _percentile(latencias, 50),
        "latencia_p95_ms": _percentile(latencias, 95),
        "latencia_p99_ms": _percentile(latencias, 99),
        "latencia_min_ms": min(latencias),
        "latencia_max_ms": max(latencias),
        "throughput_qps": exitosos / tiempo_total_seg if tiempo_total_seg > 0 else 0,
        "tokens_totales": total_tokens,
        "tokens_por_segundo": total_tokens / tiempo_total_seg if tiempo_total_seg > 0 else 0,
        "tokens_medios_por_call": statistics.mean(tokens_generados),
    }


def bench_embed(n: int) -> dict:
    latencias: list[float] = []
    exitosos = 0
    fallos = 0

    for i in range(n):
        t0 = time.monotonic()
        try:
            vectores = embed(TEXTS)
            elapsed = (time.monotonic() - t0) * 1000
            if vectores and len(vectores) == len(TEXTS) and any(abs(v) > 1e-6 for v in vectores[0]):
                latencias.append(elapsed)
                exitosos += 1
            else:
                fallos += 1
                log.warning("iter %d: vectores inesperados", i)
        except Exception as e:
            fallos += 1
            log.warning("iter %d: excepción: %s", i, e)

    if not latencias:
        return {"error": "sin llamadas exitosas", "total": n, "fallos": fallos}

    tiempo_total_seg = sum(latencias) / 1000
    return {
        "funcion": "embed",
        "modelo": "nomic-embed-text",
        "textos_por_call": len(TEXTS),
        "iteraciones": n,
        "exitosos": exitosos,
        "fallos": fallos,
        "latencia_media_ms": statistics.mean(latencias),
        "latencia_p50_ms": _percentile(latencias, 50),
        "latencia_p95_ms": _percentile(latencias, 95),
        "latencia_p99_ms": _percentile(latencias, 99),
        "latencia_min_ms": min(latencias),
        "latencia_max_ms": max(latencias),
        "throughput_qps": exitosos / tiempo_total_seg if tiempo_total_seg > 0 else 0,
    }


def _to_output(resultados: list[dict]) -> dict:
    out: dict = {}
    for r in resultados:
        if "error" in r:
            out[r["funcion"]] = {"error": r["error"]}
            continue
        d = {
            "iterations": r["iteraciones"],
            "mean_ms": r["latencia_media_ms"],
            "p50_ms": r["latencia_p50_ms"],
            "p95_ms": r["latencia_p95_ms"],
            "p99_ms": r["latencia_p99_ms"],
            "min_ms": r["latencia_min_ms"],
            "max_ms": r["latencia_max_ms"],
            "throughput": r["throughput_qps"],
        }
        if "tokens_por_segundo" in r:
            d["tokens_per_second"] = r["tokens_por_segundo"]
        out[r["funcion"]] = d
    return out


def _mostrar(resultados: list[dict]) -> None:
    linea = "-" * 68
    for r in resultados:
        if "error" in r:
            print(f"\n  ❌ {r['funcion']}: {r['error']}")
            continue
        print(f"\n  {r['funcion']}")
        print(linea)
        print(f"  modelo        {r.get('modelo', '?')}")
        print(f"  iteraciones   {r['iteraciones']}  ({r['exitosos']} exitosas, {r['fallos']} fallos)")
        if r.get("textos_por_call"):
            print(f"  batch size    {r['textos_por_call']} textos")
        print("\n  latencia")
        print(f"    media       {r['latencia_media_ms']:8.0f} ms")
        print(f"    p50         {r['latencia_p50_ms']:8.0f} ms")
        print(f"    p95         {r['latencia_p95_ms']:8.0f} ms")
        print(f"    p99         {r['latencia_p99_ms']:8.0f} ms")
        print(f"    min         {r['latencia_min_ms']:8.0f} ms")
        print(f"    max         {r['latencia_max_ms']:8.0f} ms")
        print(f"\n  throughput    {r['throughput_qps']:6.1f} calls/s")
        if "tokens_por_segundo" in r:
            print(f"  tokens/s      {r['tokens_por_segundo']:6.0f}")
            print(f"  tokens/call   {r['tokens_medios_por_call']:6.0f}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark motor.core.llm")
    parser.add_argument("--iterations", type=int, default=50, help="iteraciones por función (default: 50)")
    parser.add_argument("--output", type=str, default="", help="ruta JSON de salida")
    args = parser.parse_args()
    n = args.iterations

    print(f"\n{'=' * 68}")
    print("  Benchmark — motor.core.llm")
    print(f"  {n} iteraciones por función")
    print(f"{'=' * 68}\n")

    resultados: list[dict] = []

    print("  [1/2] generate() ...", end=" ", flush=True)
    r1 = bench_generate(n)
    resultados.append(r1)
    estado = "✅" if "error" not in r1 else "❌"
    print(f"{estado}  ({r1.get('exitosos', 0)}/{r1.get('iteraciones', 0)})")

    print("  [2/2] embed()    ...", end=" ", flush=True)
    r2 = bench_embed(n)
    resultados.append(r2)
    estado = "✅" if "error" not in r2 else "❌"
    print(f"{estado}  ({r2.get('exitosos', 0)}/{r2.get('iteraciones', 0)})")

    _mostrar(resultados)

    if args.output:
        out = _to_output(resultados)
        Path(args.output).write_text(json.dumps(out, indent=2) + "\n")
        print(f"\n  JSON guardado → {args.output}")

    print(f"\n{'=' * 68}\n")
    return 0 if all("error" not in r for r in resultados) else 1


if __name__ == "__main__":
    sys.exit(main())
