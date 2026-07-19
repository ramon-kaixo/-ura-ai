#!/usr/bin/env python3
"""Benchmark del cliente LLM unificado (motor.core.llm).

Mide por separado:
  1. generate()  — latencia p50/p95/p99, throughput, tokens/s
  2. embed()     — latencia p50/p95/p99, throughput

Permite seleccionar proveedor con --provider.

Uso exclusivo de la API pública motor.core.llm (generar/embed via router).
Sin duplicación de llamadas HTTP.

Interpretación de métricas:
  p50 = rendimiento típico.
  p95 = latencia de cola habitual.
  p99 = puede contener outliers del entorno (carga del sistema,
        planificación, calentamiento del modelo, etc.) y debe
        interpretarse junto con el número de iteraciones.

Uso:
  python3 scripts/pro/benchmark_llm.py [--iterations N] [--provider ollama|openai] [--output ruta.json]
  python3 scripts/pro/benchmark_llm.py --all-providers [--iterations N] [--output ruta.json]
"""

import argparse
import json
import logging
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from typing import Never

from motor.core.llm.registry import registry as _reg
from motor.core.llm.router import LLMRouter

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


def bench_generate(n: int, router: LLMRouter, provider: str | None = None) -> dict:
    latencias: list[float] = []
    tokens_generados: list[int] = []
    exitosos = 0
    fallos = 0

    for i in range(n):
        t0 = time.monotonic()
        try:
            respuesta = router.generate(PROMPT, provider=provider)
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
        "proveedor": provider or "default",
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


def bench_embed(n: int, router: LLMRouter, provider: str | None = None) -> dict:
    latencias: list[float] = []
    exitosos = 0
    fallos = 0

    for i in range(n):
        t0 = time.monotonic()
        try:
            vectores = router.embed(TEXTS, provider=provider)
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
        "proveedor": provider or "default",
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
    for r in resultados:
        if "error" in r:
            continue
        if r.get("textos_por_call"):
            pass
        if "tokens_por_segundo" in r:
            pass


def _bench_resilience() -> dict:  # noqa: C901
    """Mide latencia de retry y fallback con proveedores mock."""
    from motor.core.llm.base import BaseLLMProvider
    from motor.core.llm.registry import ProviderRegistry

    class _MockRetry(BaseLLMProvider):
        _count: int = 0

        def generate(self, prompt, model=None, options=None) -> str:
            self._count += 1
            if self._count < 3:
                msg = "transient"
                raise TimeoutError(msg)
            return "ok"

        def embed(self, texts, model=None):
            return [[0.0]]

        async def embed_async(self, texts, model=None):
            return [[0.0]]

        def health(self):
            return {"status": "ok"}

    class _MockFail(BaseLLMProvider):
        def generate(self, prompt, model=None, options=None) -> Never:
            msg = "fail"
            raise ValueError(msg)

        def embed(self, texts, model=None):
            return [[0.0]]

        async def embed_async(self, texts, model=None):
            return [[0.0]]

        def health(self):
            return {"status": "ok"}

    class _MockOK(BaseLLMProvider):
        def generate(self, prompt, model=None, options=None) -> str:
            return "ok"

        def embed(self, texts, model=None):
            return [[0.0]]

        async def embed_async(self, texts, model=None):
            return [[0.0]]

        def health(self):
            return {"status": "ok"}

    resultados: dict[str, dict] = {}

    # Retry
    reg_r = ProviderRegistry()
    reg_r.register("r", _MockRetry(), default=True)
    router_r = LLMRouter(registry=reg_r, retry_enabled=True, retry_max_attempts=5, retry_backoff_base=0.001)
    t0 = time.monotonic()
    r = router_r.generate("test")
    retry_latency = (time.monotonic() - t0) * 1000
    resultados["retry"] = {"ok": r == "ok", "latency_ms": round(retry_latency, 1), "calls": 3}

    # Fallback
    reg_f = ProviderRegistry()
    reg_f.register("a", _MockFail(), default=True)
    reg_f.register("b", _MockOK())
    router_f = LLMRouter(registry=reg_f, fallback_enabled=True)
    t0 = time.monotonic()
    r = router_f.generate("test")
    fb_latency = (time.monotonic() - t0) * 1000
    resultados["fallback"] = {"ok": r == "ok", "latency_ms": round(fb_latency, 1), "from": "a", "to": "b"}

    # Sin fallback (error)
    router_nf = LLMRouter(registry=reg_f, fallback_enabled=False)
    t0 = time.monotonic()
    r = router_nf.generate("test")
    nf_latency = (time.monotonic() - t0) * 1000
    resultados["no_fallback"] = {"ok": "Error" in r, "latency_ms": round(nf_latency, 1)}

    return resultados


def _mostrar_observabilidad(resultados: dict | None = None) -> None:
    from motor.core.llm.observability import metrics

    stats = metrics.summary()
    if stats:
        for _prov, _data in stats.items():
            pass


def _run_monitored_benchmark(
    n: int,
    provider: str | None,
    baseline_path: str,
    output: str,
) -> int:
    """Ejecuta benchmark con monitor de rendimiento activo integrado en el router."""
    from motor.core.llm.registry import registry as _reg

    router = LLMRouter(registry=_reg, monitor_enabled=True)

    # Cargar baseline previa si se especificó
    if baseline_path:
        p = Path(baseline_path)
        if p.exists():
            router._monitor.baseline.load(str(p))  # noqa: SLF001

    if provider:
        pass

    resultados: list[dict] = []

    r1 = bench_generate(n, router, provider=provider)
    resultados.append(r1)

    r2 = bench_embed(n, router, provider=provider)
    resultados.append(r2)

    _mostrar(resultados)
    _mostrar_observabilidad(resultados)

    # Reporte del monitor desde el router
    monitor = router._monitor  # noqa: SLF001
    if monitor:
        report = monitor.get_report()
        issues = monitor.get_recent_issues(10)
        if issues:
            pass

        # Guardar baseline
        if output:
            base_path = Path(output)
            monitor.baseline.save(str(base_path))

            # Snapshot final
            snap = {
                "resultados": _to_output(resultados),
                "monitor_report": report,
                "issues": issues,
            }
            snap_path = base_path.parent / f"{base_path.stem}_snapshot.json"
            Path(snap_path).write_text(json.dumps(snap, indent=2) + "\n")

            if issues:
                hotspot_path = base_path.parent / f"{base_path.stem}_hotspots.json"
                Path(hotspot_path).write_text(json.dumps(issues, indent=2) + "\n")

    return 0 if all("error" not in r for r in resultados) else 1


def _bench_all_providers(n: int, output: str) -> int:
    """Benchmark todos los proveedores registrados en el Registry."""
    providers = list(_reg.list())
    if not providers:
        return 1

    resultados: dict[str, dict] = {}
    router = LLMRouter(registry=_reg)

    for prov_name in providers:
        r = bench_generate(n, router, provider=prov_name)
        resultados[f"{prov_name}_generate"] = r
        r.get("exitosos", 0)
        r.get("iteraciones", 0)

    for prov_name in providers:
        r = bench_embed(n, router, provider=prov_name)
        resultados[f"{prov_name}_embed"] = r
        r.get("exitosos", 0)
        r.get("iteraciones", 0)

    # Mostrar tabla
    for prov_name in providers:
        r_gen = resultados.get(f"{prov_name}_generate", {})
        r_emb = resultados.get(f"{prov_name}_embed", {})
        for func, r in [("generate", r_gen), ("embed", r_emb)]:
            if "error" in r:
                continue
            r.get("latencia_p50_ms", 0)
            r.get("latencia_p95_ms", 0)
            r.get("latencia_p99_ms", 0)
            r.get("tokens_por_segundo", 0) if func == "generate" else 0
            r.get("fallos", 0)

    # Ranking
    ranking = sorted(
        [
            (p, resultados[f"{p}_generate"].get("latencia_p50_ms", 99999))
            for p in providers
            if "error" not in resultados.get(f"{p}_generate", {})
        ],
        key=lambda x: x[1],
    )
    for _rank, (_prov, _lat) in enumerate(ranking, 1):
        pass

    # Exportar
    if output:
        out = {
            "benchmark": "multi-provider",
            "iterations": n,
            "providers": {
                p: {
                    "generate": {
                        "p50_ms": resultados.get(f"{p}_generate", {}).get("latencia_p50_ms", 0),
                        "p95_ms": resultados.get(f"{p}_generate", {}).get("latencia_p95_ms", 0),
                        "p99_ms": resultados.get(f"{p}_generate", {}).get("latencia_p99_ms", 0),
                        "throughput": resultados.get(f"{p}_generate", {}).get("throughput_qps", 0),
                        "tokens_per_second": resultados.get(f"{p}_generate", {}).get("tokens_por_segundo", 0),
                        "errors": resultados.get(f"{p}_generate", {}).get("fallos", 0),
                    },
                    "embed": {
                        "p50_ms": resultados.get(f"{p}_embed", {}).get("latencia_p50_ms", 0),
                        "p95_ms": resultados.get(f"{p}_embed", {}).get("latencia_p95_ms", 0),
                        "p99_ms": resultados.get(f"{p}_embed", {}).get("latencia_p99_ms", 0),
                        "throughput": resultados.get(f"{p}_embed", {}).get("throughput_qps", 0),
                        "errors": resultados.get(f"{p}_embed", {}).get("fallos", 0),
                    },
                }
                for p in providers
            },
            "ranking": [{"rank": r, "provider": p, "latency_p50_ms": l} for r, (p, l) in enumerate(ranking, 1)],
        }
        Path(output).write_text(json.dumps(out, indent=2) + "\n")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark motor.core.llm")
    parser.add_argument("--iterations", type=int, default=50, help="iteraciones por función (default: 50)")
    parser.add_argument("--provider", type=str, default="", help="proveedor (ollama, openai, ...)")
    parser.add_argument("--output", type=str, default="", help="ruta JSON de salida")
    parser.add_argument("--resilience", action="store_true", help="benchmark de resiliencia (retry/fallback)")
    parser.add_argument("--monitor", action="store_true", help="benchmark con monitor de rendimiento")
    parser.add_argument("--baseline-load", type=str, default="", help="cargar baseline previa desde JSON")
    parser.add_argument("--baseline-save", type=str, default="", help="guardar baseline a JSON")
    parser.add_argument("--all-providers", action="store_true", help="benchmark todos los proveedores registrados")
    args = parser.parse_args()

    if args.resilience:
        resultados = _bench_resilience()
        for data in resultados.values():
            "✅" if data["ok"] else "❌"
        if args.output:
            Path(args.output).write_text(json.dumps(resultados, indent=2) + "\n")
        return 0

    if args.all_providers:
        return _bench_all_providers(n=args.iterations, output=args.output)

    if args.monitor:
        save_path = args.baseline_save or args.output or ""
        return _run_monitored_benchmark(
            args.iterations,
            args.provider or None,
            args.baseline_load,
            save_path,
        )

    n = args.iterations
    provider = args.provider or None
    router = LLMRouter(registry=_reg)

    if provider:
        pass

    resultados: list[dict] = []

    r1 = bench_generate(n, router, provider=provider)
    resultados.append(r1)

    r2 = bench_embed(n, router, provider=provider)
    resultados.append(r2)

    _mostrar(resultados)
    _mostrar_observabilidad(resultados)

    if args.output:
        out = _to_output(resultados)
        Path(args.output).write_text(json.dumps(out, indent=2) + "\n")

    return 0 if all("error" not in r for r in resultados) else 1


if __name__ == "__main__":
    sys.exit(main())
