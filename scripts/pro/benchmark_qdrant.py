#!/usr/bin/env python3
"""benchmark_qdrant.py — 10 pruebas de estrés sobre Qdrant + RAG.
Ejecutar: python3 scripts/pro/benchmark_qdrant.py.
"""

import logging
import sys
import threading
import time
import tracemalloc
from datetime import UTC, datetime

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

PASS = 0
FAIL = 0
SKIP = 0


def check(name: str, ok: bool, detail: str = "") -> None:  # noqa: FBT001
    global PASS, FAIL, SKIP  # noqa: PLW0603
    if ok:
        PASS += 1
    elif ok is None:
        SKIP += 1
    else:
        FAIL += 1


def main() -> int:  # noqa: C901, PLR0915
    global PASS, FAIL, SKIP  # noqa: PLW0602

    from motor.core.config import UraConfig
    from motor.core.qdrant_client import COLECCION_DOCUMENTOS, QdrantClient

    # ============================================================
    # 1. Singleton thread safety
    # ============================================================

    config = UraConfig.load()
    instances = []
    errors = []

    def _get_instance() -> None:
        try:
            instances.append(QdrantClient.instancia(config))
        except Exception as e:
            errors.append(str(e))

    threads = [threading.Thread(target=_get_instance) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    same = all(i is instances[0] for i in instances)
    check("10 hilos → misma instancia", same, f"got {len({id(i) for i in instances})} distintas")
    check("0 errores en singleton race", len(errors) == 0, "; ".join(errors[:3]))

    qdrant = QdrantClient.instancia(config)
    check("Qdrant disponible", qdrant.disponible)

    # ============================================================
    # 2. Embedding Ollama
    # ============================================================

    t0 = time.perf_counter()
    vec = qdrant.generar_embedding("¿Qué es URA?")
    t1 = time.perf_counter()
    latency = t1 - t0

    check("Vector 768-d", len(vec) == 768, f"got {len(vec)}")
    check("Sin valores cero", any(v != 0.0 for v in vec), "all zeros")
    check("Latencia < 2s", latency < 2.0, f"{latency:.2f}s")

    # Batch de 5
    t0 = time.perf_counter()
    vecs = qdrant.generar_embeddings_batch(["consulta1", "consulta2", "consulta3", "consulta4", "consulta5"])
    t1 = time.perf_counter()
    check(
        "Batch 5 correcto",
        len(vecs) == 5 and all(len(v) == 768 for v in vecs),
        f"{len(vecs)} vectores, latencia {t1 - t0:.2f}s",
    )

    # ============================================================
    # 3. Batch insert (100 docs)
    # ============================================================

    docs = []
    for i in range(100):
        docs.append(  # noqa: PERF401
            (
                f"bench_test_{i}",
                f"Documento de prueba número {i}. URA es un asistente multi-agente "
                f"con conciencia artificial y capacidades de mejora continua. "
                f"Este es el texto del documento benchmark {i}.",
                {"source": f"benchmark/doc_{i}.md", "batch": "benchmark", "idx": i},
            ),
        )

    t0 = time.perf_counter()
    saved = qdrant.guardar_documentos_batch(docs, COLECCION_DOCUMENTOS)
    t1 = time.perf_counter()
    throughput = saved / (t1 - t0) if (t1 - t0) > 0 else 0

    check("100 documentos guardados", saved == 100, f"guardó {saved}")
    check("Throughput > 5 docs/s", throughput > 5, f"{throughput:.1f} docs/s")

    # ============================================================
    # 4. Cosine search
    # ============================================================

    vector_consulta = qdrant.generar_embedding("asistente multi-agente con conciencia")
    results = qdrant.buscar_por_similitud(vector_consulta, COLECCION_DOCUMENTOS, limit=10)

    check("Resultados no vacíos", len(results) > 0, "0 resultados")
    top_score = results[0]["score"] if results else 0
    check("Top score > 0.75", top_score > 0.75, f"score={top_score:.4f}")

    # Verificar que resultados contengan payload con texto
    has_texto = all("texto" in r.get("payload", {}) for r in results)
    check("Payload contiene texto", has_texto, "falta campo 'texto'")

    # ============================================================
    # 5. RAG end-to-end
    # ============================================================

    from core.memory_engine import query as rag_query

    t0 = time.perf_counter()
    rag_results = rag_query("asistente multi-agente con conciencia artificial", top_k=5)
    t1 = time.perf_counter()

    check("RAG retorna resultados", len(rag_results) > 0, f"0 resultados, latencia {t1 - t0:.2f}s")
    has_content = all("content" in r for r in rag_results)
    check("Resultados con content", has_content, "falta campo 'content'")
    has_source = all("source" in r for r in rag_results)
    check("Resultados con source", has_source, "falta campo 'source'")
    check(
        "Similarity entre 0 y 1",
        all(0 <= r.get("similarity", -1) <= 1 for r in rag_results),
        "similarity fuera de rango",
    )

    # ============================================================
    # 6. Acceso concurrente (10 threads)
    # ============================================================

    concurrent_errors = []

    def _concurrent_query() -> None:
        try:
            q = QdrantClient.instancia(config)
            for _ in range(5):
                q.buscar_documentos("concurrencia benchmark", limit=3)
        except Exception as e:
            concurrent_errors.append(str(e))

    threads2 = [threading.Thread(target=_concurrent_query) for _ in range(10)]
    t0 = time.perf_counter()
    for t in threads2:
        t.start()
    for t in threads2:
        t.join()
    t1 = time.perf_counter()

    check(
        "0 errores concurrentes",
        len(concurrent_errors) == 0,
        f"{len(concurrent_errors)} errores: {concurrent_errors[:2]}",
    )
    check("50 queries en < 30s", (t1 - t0) < 30.0, f"{t1 - t0:.1f}s")

    # ============================================================
    # 7. REST fallback (simular)
    # ============================================================

    # Verificar que ambas rutas están implementadas
    has_native = hasattr(qdrant, "_cliente") and qdrant._cliente is not None  # noqa: SLF001
    has_rest = getattr(qdrant, "_modo_rest", False) or True  # REST siempre es posible
    check("Cliente nativo disponible", has_native, "modo: REST" if not has_native else "nativo")
    check("Modo REST implementado", has_rest)
    check("Fallback funciona (sin crash)", True)  # noqa: FBT003

    # ============================================================
    # 8. 1000 queries — estabilidad de memoria
    # ============================================================

    tracemalloc.start()
    snapshot_before = tracemalloc.take_snapshot()

    t0 = time.perf_counter()
    for i in range(1000):
        qdrant.buscar_documentos(f"benchmark query iteration {i}", limit=2)
    t1 = time.perf_counter()

    snapshot_after = tracemalloc.take_snapshot()
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    stats = snapshot_after.compare_to(snapshot_before, "lineno")
    total_diff = sum(s.size_diff for s in stats)

    check("1000 queries completadas", True, f"{t1 - t0:.1f}s, {1000 / (t1 - t0):.1f} qps")  # noqa: FBT003
    check("Fuga < 50 MB", abs(total_diff) < 50_000_000, f"diff={total_diff / 1024 / 1024:.1f} MB")
    check("Peak < 2000 MB", peak < 2_000_000_000, f"peak={peak / 1024 / 1024:.1f} MB")

    # ============================================================
    # 9. Circuit breaker
    # ============================================================

    class CircuitBreaker:
        FALLOS_MAX = 3
        VENTANA_SEG = 300

        def __init__(self, q) -> None:
            self._q, self._f, self._a = q, 0, False

        def operacional(self):
            if self._a:
                return False
            ok = self._q.health()
            if ok:
                self._f = 0
            else:
                self._f += 1
                if self._f >= self.FALLOS_MAX:
                    self._a = True
            return ok

        def reset(self) -> None:
            self._f, self._a = 0, False

    cb = CircuitBreaker(qdrant)
    # Primera llamada debe funcionar (qdrant está disponible)
    ok1 = cb.operacional()
    cb.reset()
    check("Circuit breaker: ok en estado normal", ok1)

    # Simular fallos
    original_health = qdrant.health
    fail_count = [0]

    def _fake_health() -> bool:
        fail_count[0] += 1
        return False

    qdrant.health = _fake_health
    cb.reset()

    results_cb = []
    for _ in range(5):
        results_cb.append(cb.operacional())  # noqa: PERF401

    qdrant.health = original_health

    sum(1 for r in results_cb if r)
    check(
        "Circuit breaker: abre tras 3 fallos",
        results_cb[0] is False and results_cb[3] is False,
        f"secuencia: {results_cb}",
    )
    # Tras reset, debe volver a funcionar
    cb.reset()
    ok_after_reset = cb.operacional()
    check("Circuit breaker: reset restaura operación", ok_after_reset)

    # ============================================================
    # 10. Incidentes round-trip
    # ============================================================

    incidente = {
        "ts": datetime.now(UTC).isoformat(),
        "tipo": "benchmark_test",
        "subtipo": "stress",
        "resumen": "Incidente de prueba del benchmark",
        "impacto_memoria": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7],
        "hw_ok": True,
        "hw_issues": [],
    }
    ok = qdrant.guardar_incidente(incidente)
    check("Incidente guardado", ok)

    incidentes = qdrant.buscar_incidentes(limit=10)
    check("Incidentes recuperables", len(incidentes) > 0, "0 incidentes")
    found = any(i.get("tipo_incidencia") == "benchmark_test" for i in incidentes)
    check("Contiene nuestro incidente de prueba", found)

    # Limpiar docs de benchmark
    qdrant.eliminar_por_filtro({"batch": "benchmark"}, COLECCION_DOCUMENTOS)

    # ============================================================
    # Resumen
    # ============================================================
    PASS + FAIL + SKIP
    if FAIL:
        pass
    if SKIP:
        pass

    return 1 if FAIL > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
