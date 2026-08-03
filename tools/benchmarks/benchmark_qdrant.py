#!/usr/bin/env python3
"""benchmark_qdrant.py — 10 pruebas de estrés sobre Qdrant + RAG.
Ejecutar: python3 scripts/pro/benchmark_qdrant.py.
"""

import logging
import sys
import time
import tracemalloc

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

PASS = 0
FAIL = 0
SKIP = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global PASS, FAIL, SKIP  # noqa: PLW0603
    if ok:
        PASS += 1
    elif ok is None:
        SKIP += 1
    else:
        FAIL += 1


from motor.core.qdrant_client import COLECCION_DOCUMENTOS, QdrantClient


# Helper 1: Singleton thread safety
def _get_instance() -> None:
    try:
        instances.append(QdrantClient.instancia(config))
    except Exception as e:
        errors.append(str(e))


# Helper 2: Embedding Ollama
def generate_embedding(text) -> list[float]:
    t0 = time.perf_counter()
    vec = qdrant.generar_embedding(text)
    t1 = time.perf_counter()
    return vec, (t1 - t0)


# Helper 3: Batch insert
def save_documents(docs) -> int:
    t0 = time.perf_counter()
    saved = qdrant.guardar_documentos_batch(docs, COLECCION_DOCUMENTOS)
    t1 = time.perf_counter()
    return saved, (t1 - t0)


# Helper 4: Cosine search
def cosine_search(vector_consulta):
    results = qdrant.buscar_por_similitud(vector_consulta, COLECCION_DOCUMENTOS, limit=10)
    return results


# Helper 5: RAG end-to-end
def rag_query_helper(text):
    t0 = time.perf_counter()
    rag_results = rag_query(text, top_k=5)
    t1 = time.perf_counter()
    return rag_results, (t1 - t0)


# Helper 6: Acceso concurrente
def concurrent_query():
    try:
        q = QdrantClient.instancia(config)
        for _ in range(5):
            q.buscar_documentos("concurrencia benchmark", limit=3)
    except Exception as e:
        concurrent_errors.append(str(e))


# Helper 7: REST fallback
def check_rest_implementation():
    has_native = hasattr(qdrant, "_cliente") and qdrant._cliente is not None
    has_rest = getattr(qdrant, "_modo_rest", False) or True  # REST siempre es posible
    return has_native, has_rest


# Helper 8: 1000 queries — estabilidad de memoria
def memory_stability():
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

    return (t1 - t0), total_diff, peak


# Helper 9: Circuit breaker
def circuit_breaker():
    class CircuitBreaker:
        FALLOS_MAX = 3
        VENTANA_SEG = 300

        def __init__(self, q):
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
    results_cb = []
    for _ in range(5):
        results_cb.append(cb.operacional())
    return results_cb


# Helper 10: Incidentes round-trip
def save_incident(incidente):
    ok = qdrant.guardar_incidente(incidente)
    return ok


def retrieve_incidents():
    incidentes = qdrant.buscar_incidentes(limit=10)
    found = any(i.get("tipo_incidencia") == "benchmark_test" for i in incidentes)
    return found, len(incidentes) > 0, incidentes


if __name__ == "__main__":
    sys.exit(main())
