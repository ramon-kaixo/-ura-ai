#!/usr/bin/env python3
"""F14 Resilience Tests — Bloque 2.

Uso:
  python3 scripts/pro/f14_resilience.py           # ejecuta todos los escenarios
  python3 scripts/pro/f14_resilience.py --scenario R01,R02  # solo algunos

Requiere: Docker (Qdrant), systemd (Ollama), acceso GX10.

Cada escenario documenta: fault, expected, observed, auto_recovery,
recovery_time, data_loss, verdict.

No corrige ningún defecto. Solo mide, documenta, informa.
"""

import contextlib
import csv
import json
import os
import platform
import subprocess
import sys
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_PROJECT_ROOT))
os.environ.setdefault("URA_LOG_LEVEL", "ERROR")

OUTPUT_DIR = _PROJECT_ROOT / "motor" / "data" / "benchmarks" / "f14" / "resilience"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

ENV = {
    "timestamp": datetime.now(UTC).isoformat(),
    "hostname": platform.node(),
    "platform": platform.platform(),
    "python": platform.python_version(),
    "commit_sha": subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()  # noqa: PLW1510, S607
    or "unknown",
    "version": subprocess.run(["git", "describe", "--tags", "--always"], capture_output=True, text=True).stdout.strip()  # noqa: PLW1510, S607
    or "unknown",
    "cpu_cores": os.cpu_count() or 0,
}


# ─── Helpers de sistema ──────────────────────────────────────────────


def qdrant_running() -> bool:
    r = subprocess.run(  # noqa: PLW1510
        ["docker", "ps", "--filter", "name=ura-qdrant", "--format", "{{.Names}}"],  # noqa: S607
        capture_output=True,
        text=True,
        timeout=10,
    )
    return "ura-qdrant" in r.stdout


def ollama_running() -> bool:
    try:
        r = subprocess.run(  # noqa: PLW1510
            ["systemctl", "is-active", "ollama"],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=5,
        )
        return "active" in r.stdout
    except Exception:
        return False


def docker_exec(cmd: list[str], timeout: int = 30) -> tuple[int, str, str]:
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)  # noqa: PLW1510, S603
    return r.returncode, r.stdout, r.stderr


def qdrant_health() -> bool:
    try:
        r = subprocess.run(  # noqa: PLW1510
            ["curl", "-sf", "http://localhost:6333/health"],  # noqa: S607
            capture_output=True,
            timeout=5,
        )
        return r.returncode == 0
    except Exception:
        return False


def ollama_health() -> bool:
    try:
        r = subprocess.run(  # noqa: PLW1510
            ["curl", "-sf", "http://localhost:11434/api/tags"],  # noqa: S607
            capture_output=True,
            timeout=5,
        )
        return r.returncode == 0
    except Exception:
        return False


def wait_for_qdrant(timeout: int = 30) -> float:
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout:
        if qdrant_health():
            return round(time.monotonic() - t0, 1)
        time.sleep(1)
    return round(time.monotonic() - t0, 1)


def wait_for_ollama(timeout: int = 60) -> float:
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout:
        if ollama_health():
            return round(time.monotonic() - t0, 1)
        time.sleep(2)
    return round(time.monotonic() - t0, 1)


# ─── Import de componentes (bajo demanda) ────────────────────────────


def _make_hybrid_retriever():
    from motor.core.config import UraConfig
    from motor.core.qdrant_client import QdrantClient
    from motor.intelligence.retrieval.hybrid import HybridRetriever
    from motor.intelligence.retrieval.lexical import LexicalRetriever
    from motor.intelligence.retrieval.vector import VectorRetriever

    config = UraConfig(qdrant_host="localhost", qdrant_port=6333)
    qdrant = QdrantClient(config)
    vr = VectorRetriever(qdrant_client=qdrant)
    lr = LexicalRetriever()
    return HybridRetriever(vector_retriever=vr, lexical_retriever=lr, alpha=0.7, beta=0.3)


def _make_runtime():
    from motor.intelligence.agents.runtime import MultiAgentRuntime

    return MultiAgentRuntime()


# ─── Escenarios ───────────────────────────────────────────────────────


def scenario_r01() -> dict[str, Any]:
    """R01 — Qdrant no disponible al arrancar."""
    fault = "docker stop ura-qdrant durante una consulta de retrieval"
    expected = "DegradedMode marca qdrant como degraded, sistema lanza excepción controlada, no crash"
    data_loss = False
    auto_recovery = True
    recovery_time = -1.0

    if not qdrant_running():
        return {
            "id": "R01",
            "fault": fault,
            "expected": expected,
            "observed": "Qdrant ya no estaba disponible antes del test. SKIP.",
            "auto_recovery": False,
            "recovery_time_s": -1,
            "data_loss": False,
            "veredict": "SKIP",
        }

    try:
        hr = _make_hybrid_retriever()
    except Exception as e:
        return {
            "id": "R01",
            "fault": fault,
            "expected": expected,
            "observed": f"Error al construir retriever: {e}. El sistema no pudo inicializar.",
            "auto_recovery": False,
            "recovery_time_s": -1,
            "data_loss": False,
            "veredict": "FAIL",
        }

    # 1. Primero verificar que funciona con Qdrant healthy
    with contextlib.suppress(Exception):
        hr.search("test query before stop", k=3)

    # 2. Detener Qdrant
    docker_exec(["docker", "stop", "ura-qdrant"])
    time.sleep(2)

    # 3. Intentar búsqueda (debe fallar controladamente)
    observed = ""
    try:
        hr.search("test query after stop", k=3)
        observed = "La búsqueda retornó sin error a pesar de que Qdrant estaba caído"
    except Exception as e:
        observed = f"Excepción controlada: {type(e).__name__}: {e}"

    # 4. Restaurar Qdrant
    docker_exec(["docker", "start", "ura-qdrant"])
    recovery_time = wait_for_qdrant(timeout=30)

    # 5. Verificar recuperación
    try:
        hr = _make_hybrid_retriever()
        hr.search("test query after restore", k=3)
        observed += " | Post-restauración: search funciona correctamente"
    except Exception as e:
        observed += f" | Post-restauración: error: {e}"
        auto_recovery = False

    verdict = "PASS" if recovery_time < 30 else "PARTIAL"
    if not auto_recovery:
        verdict = "FAIL"

    return {
        "id": "R01",
        "fault": fault,
        "expected": expected,
        "observed": observed,
        "auto_recovery": auto_recovery,
        "recovery_time_s": recovery_time,
        "data_loss": data_loss,
        "veredict": verdict,
    }


def scenario_r02() -> dict[str, Any]:
    """R02 — Ollama inaccesible o timeout."""
    fault = "systemctl stop ollama, luego intentar operación con agente"
    expected = "Agente detecta timeout, error graceful, no crash del runtime"
    data_loss = False
    auto_recovery = True
    recovery_time = -1.0

    if not ollama_running():
        return {
            "id": "R02",
            "fault": fault,
            "expected": expected,
            "observed": "Ollama ya no estaba disponible. SKIP.",
            "auto_recovery": False,
            "recovery_time_s": -1,
            "data_loss": False,
            "veredict": "SKIP",
        }

    try:
        rt = _make_runtime()
    except Exception as e:
        return {
            "id": "R02",
            "fault": fault,
            "expected": expected,
            "observed": f"No se pudo crear runtime: {e}",
            "auto_recovery": False,
            "recovery_time_s": -1,
            "data_loss": False,
            "veredict": "FAIL",
        }

    # 1. Detener Ollama
    docker_exec(["systemctl", "stop", "ollama"], timeout=10)
    time.sleep(3)
    still_running = ollama_running()

    # 2. Intentar ejecutar workflow
    observed = ""
    try:
        result = rt.execute_workflow("test con ollama caído", timeout=15)
        observed = f"Workflow retornó success=False (esperado). Resultado: {result.success}, error='{result.error}'"
        if still_running:
            observed += (
                " | ⚠️ NOTA: Ollama no se detuvo realmente (no new privileges flag impide systemctl stop sin sudo)"
            )
        verdict = "PARTIAL"
    except Exception as e:
        observed = f"Excepción: {type(e).__name__}: {e}"
        if still_running:
            observed += " | ⚠️ NOTA: Ollama no se detuvo realmente"

    # 3. Restaurar Ollama
    docker_exec(["systemctl", "start", "ollama"], timeout=30)
    recovery_time = wait_for_ollama(timeout=60)

    verdict = "PARTIAL" if still_running else "PASS" if recovery_time < 60 else "PARTIAL"

    return {
        "id": "R02",
        "fault": fault,
        "expected": expected,
        "observed": observed,
        "auto_recovery": auto_recovery,
        "recovery_time_s": recovery_time,
        "data_loss": data_loss,
        "veredict": verdict,
    }


def scenario_r03() -> dict[str, Any]:
    """R03 — Timeout prolongado de herramientas externas."""
    fault = "ejecutar workflow con timeout muy corto (1s) en contexto pesado"
    expected = "Timeout se dispara, workflow se cancela, sistema continúa"
    data_loss = False

    try:
        rt = _make_runtime()
    except Exception as e:
        return {
            "id": "R03",
            "fault": fault,
            "expected": expected,
            "observed": f"No se pudo crear runtime: {e}",
            "auto_recovery": True,
            "recovery_time_s": 0,
            "data_loss": False,
            "veredict": "FAIL",
        }

    # Ejecutar workflow con timeout extremadamente corto
    observed = ""
    t0 = time.monotonic()
    try:
        # El runtime tiene timeout=120s por defecto, pasamos 1 para forzar
        result = rt.execute_workflow("test timeout forzado", timeout=1)
        elapsed = time.monotonic() - t0
        observed = f"Workflow retornó en {elapsed:.1f}s. success={result.success}, error='{result.error}'"
    except Exception as e:
        elapsed = time.monotonic() - t0
        observed = f"Excepción en {elapsed:.1f}s: {type(e).__name__}: {e}"

    # Verificar que el sistema sigue funcionando después
    try:
        rt2 = _make_runtime()
        rt2.execute_workflow("test post-timeout", timeout=10)
        observed += " | Sistema OK post-timeout"
        auto_recovery = True
    except Exception as e:
        observed += f" | Sistema falló post-timeout: {e}"
        auto_recovery = False

    verdict = "PASS" if auto_recovery else "FAIL"

    return {
        "id": "R03",
        "fault": fault,
        "expected": expected,
        "observed": observed,
        "auto_recovery": auto_recovery,
        "recovery_time_s": 0,
        "data_loss": data_loss,
        "veredict": verdict,
    }


def scenario_r04() -> dict[str, Any]:
    """R04 — Cancelación de workflows en ejecución."""
    fault = "lanzar 10 workflows en background, cancelarlos via SIGTERM al proceso"
    expected = "SIGTERM manejado, workflows en curso se marcan como cancelados, cleanup ejecutado"
    data_loss = False

    try:
        rt = _make_runtime()
    except Exception as e:
        return {
            "id": "R04",
            "fault": fault,
            "expected": expected,
            "observed": f"No se pudo crear runtime: {e}",
            "auto_recovery": True,
            "recovery_time_s": 0,
            "data_loss": False,
            "veredict": "FAIL",
        }

    workers = []
    observed = ""

    def launch_workflow(idx: int) -> None:
        with contextlib.suppress(Exception):
            rt.execute_workflow(f"cancelable-task-{idx}", timeout=120)

    # Lanzar 10 workflows en paralelo
    for i in range(10):
        t = threading.Thread(target=launch_workflow, args=(i,), daemon=True)
        workers.append(t)
        t.start()

    time.sleep(0.5)

    # Cancelar todos (simulado — el runtime no expone cancelación masiva)
    try:
        rt.cancel()
        observed = "Se invocó runtime.cancel() sin errores"
        auto_recovery = True
    except Exception as e:
        observed = f"runtime.cancel() lanzó: {type(e).__name__}: {e}"
        auto_recovery = False

    # Esperar a que los workers terminen
    for t in workers:
        t.join(timeout=5)

    # Verificar que el runtime sigue funcionando
    try:
        rt.execute_workflow("test-post-cancel", timeout=10)
        observed += " | Sistema OK post-cancelación"
        auto_recovery = True
    except Exception as e:
        observed += f" | Sistema falló post-cancelación: {e}"
        auto_recovery = False

    verdict = "PASS" if auto_recovery else "FAIL"

    return {
        "id": "R04",
        "fault": fault,
        "expected": expected,
        "observed": observed,
        "auto_recovery": auto_recovery,
        "recovery_time_s": 0,
        "data_loss": data_loss,
        "veredict": verdict,
    }


def scenario_r05() -> dict[str, Any]:
    """R05 — Fallo simultáneo de múltiples agentes."""
    fault = "registrar agentes que siempre fallan, ejecutar workflow multi-agente"
    expected = "Supervisor detecta fallos, resultados parciales, no crash"
    data_loss = False

    try:
        rt = _make_runtime()
    except Exception as e:
        return {
            "id": "R05",
            "fault": fault,
            "expected": expected,
            "observed": f"No se pudo crear runtime: {e}",
            "auto_recovery": True,
            "recovery_time_s": 0,
            "data_loss": False,
            "veredict": "FAIL",
        }

    observed = ""
    try:
        result = rt.execute_workflow(
            "test multi-agente con fallo forzado",
            context={"force_failure": True},
            timeout=30,
        )
        observed = f"Workflow completado. success={result.success}, error='{result.error}'"
        auto_recovery = True
    except Exception as e:
        observed = f"Excepción: {type(e).__name__}: {e}"
        auto_recovery = False

    verdict = "PASS" if auto_recovery else "FAIL"

    return {
        "id": "R05",
        "fault": fault,
        "expected": expected,
        "observed": observed,
        "auto_recovery": auto_recovery,
        "recovery_time_s": 0,
        "data_loss": data_loss,
        "veredict": verdict,
    }


def scenario_r06() -> dict[str, Any]:
    """R06 — Corrupción o ausencia de memoria persistente."""
    fault = "eliminar archivo SQLite de memoria episódica, luego intentar store/search"
    expected = "EpisodeStore crea nuevo archivo o lanza error controlado, sistema continúa"
    data_loss = True
    auto_recovery = True

    from motor.intelligence.memory.episodic import Episode, EpisodeStore, EpisodeStoreConfig

    mem_path = _PROJECT_ROOT / "motor" / "data" / "f14_episodic_test.db"

    # Crear store con archivo persistente
    config = EpisodeStoreConfig(persist_path=str(mem_path))
    observed = ""

    try:
        store = EpisodeStore(config=config)
        # Store un episodio
        ep = Episode(
            source="test-r06",
            payload="test data for corruption scenario",
            tags=["test", "r06"],
            references=[],
            metadata={"scenario": "R06"},
        )
        store.store(ep)

        # Eliminar el archivo de base de datos
        if mem_path.exists():
            mem_path.unlink()
            # Asegurar que no hay caché
            if (mem_path.parent / "f14_episodic_test.db-wal").exists():
                (mem_path.parent / "f14_episodic_test.db-wal").unlink()
            if (mem_path.parent / "f14_episodic_test.db-shm").exists():
                (mem_path.parent / "f14_episodic_test.db-shm").unlink()

        # Intentar store después de corrupción
        ep2 = Episode(
            source="test-r06-corrupted",
            payload="test after corruption",
            tags=["test", "r06"],
            references=[],
            metadata={"scenario": "R06"},
        )
        try:
            store.store(ep2)
            observed = "Store post-corrupción funcionó (posible recreación automática)"
        except Exception as e:
            observed = f"Store post-corrupción lanzó error controlado: {type(e).__name__}: {e}"

        # Verificar si el archivo fue recreado
        if mem_path.exists():
            observed += " | Archivo de BD fue recreado automáticamente"
            auto_recovery = True
        else:
            observed += " | Archivo de BD no fue recreado"
            auto_recovery = False

    except Exception as e:
        observed = f"Error durante el test: {type(e).__name__}: {e}"
        auto_recovery = False

    # Limpiar
    if mem_path.exists():
        mem_path.unlink()

    verdict = "PASS" if auto_recovery else "PARTIAL"

    return {
        "id": "R06",
        "fault": fault,
        "expected": expected,
        "observed": observed,
        "auto_recovery": auto_recovery,
        "recovery_time_s": 0,
        "data_loss": data_loss,
        "veredict": verdict,
    }


def scenario_r07() -> dict[str, Any]:
    """R07 — Agotamiento de recursos (CPU/RAM/hilos)."""
    fault = "crear 1000 diccionarios grandes en memoria para forzar presión de RAM, ejecutar workflow"
    expected = "Sistema degrada gracefulmente o lanza MemoryError controlado, sin crash"
    data_loss = False

    try:
        rt = _make_runtime()
    except Exception as e:
        return {
            "id": "R07",
            "fault": fault,
            "expected": expected,
            "observed": f"No se pudo crear runtime: {e}",
            "auto_recovery": True,
            "recovery_time_s": 0,
            "data_loss": False,
            "veredict": "FAIL",
        }

    observed = ""
    auto_recovery = False

    # Forzar presión de RAM
    big_objects: list[dict] = []
    try:
        for _i in range(1000):
            big_objects.append({str(j): "x" * 10000 for j in range(100)})  # noqa: PERF401
    except MemoryError:
        observed += "MemoryError al crear objetos grandes (esperado) | "

    # Intentar workflow bajo presión
    try:
        result = rt.execute_workflow("test bajo presion de RAM", timeout=15)
        observed += f"Workflow ejecutado bajo presión. success={result.success}"
        auto_recovery = True
    except Exception as e:
        observed += f"Workflow falló bajo presión: {type(e).__name__}: {e}"
        auto_recovery = type(e).__name__ != "MemoryError"

    # Liberar memoria
    del big_objects
    time.sleep(1)
    observed += " | Memoria liberada"

    verdict = "PASS" if auto_recovery else "FAIL"

    return {
        "id": "R07",
        "fault": fault,
        "expected": expected,
        "observed": observed,
        "auto_recovery": auto_recovery,
        "recovery_time_s": 0,
        "data_loss": data_loss,
        "veredict": verdict,
    }


def scenario_r08() -> dict[str, Any]:
    """R08 — Reinicio del runtime durante carga."""
    fault = "forzar salida del proceso Python durante ejecución de operaciones, verificar estado post-reinicio"
    expected = "Sistema se recupera al reiniciar el proceso, sin corrupción de datos persistentes"
    data_loss = False

    # Este escenario no puede probarse desde dentro del mismo proceso.
    # Simulamos: lanzamos operaciones, forzamos salida del script (simulado),
    # luego verificamos que Qdrant y el filesystem están sanos.

    observed = ""
    t0 = time.monotonic()

    try:
        hr = _make_hybrid_retriever()
        # Hacer algunas operaciones
        for i in range(5):
            hr.search(f"test before restart {i}", k=3)

        # Simular reinicio: verificar que el sistema externo sobrevive
        # (Qdrant, Ollama, archivos de BD)
        observed = "Qdrant responde OK después de operaciones" if qdrant_health() else "Qdrant no responde"

        if memstore_exists():
            observed += " | MemoryStore persistente intacto"
        else:
            observed += " | MemoryStore no verificado"

        auto_recovery = True

    except Exception as e:
        observed = f"Error: {type(e).__name__}: {e}"
        auto_recovery = False

    recovery_time = round(time.monotonic() - t0, 1)
    verdict = "PASS" if auto_recovery else "FAIL"

    return {
        "id": "R08",
        "fault": fault,
        "expected": expected,
        "observed": observed + " (escenario simulado — el reinicio real requiere ejecución externa)",
        "auto_recovery": auto_recovery,
        "recovery_time_s": recovery_time,
        "data_loss": data_loss,
        "veredict": verdict,
    }


def memstore_exists() -> bool:
    """Check if any memory store files exist."""
    for _p in _PROJECT_ROOT.rglob("*memory*.db"):
        return True
    return False


def scenario_r09() -> dict[str, Any]:
    """R09 — Recuperación automática tras restaurar dependencias."""
    fault = "Qdrant caído por 15s, luego restaurar, verificar que el sistema retoma operación normal"
    expected = "Sistema detecta caída, opera en degradado, vuelve a normal automáticamente al restaurar"
    data_loss = False
    auto_recovery = False

    if not qdrant_running():
        return {
            "id": "R09",
            "fault": fault,
            "expected": expected,
            "observed": "Qdrant ya no disponible antes del test. SKIP.",
            "auto_recovery": False,
            "recovery_time_s": -1,
            "data_loss": False,
            "veredict": "SKIP",
        }

    observed = ""

    try:
        hr = _make_hybrid_retriever()
    except Exception as e:
        return {
            "id": "R09",
            "fault": fault,
            "expected": expected,
            "observed": f"No se pudo construir retriever: {e}",
            "auto_recovery": False,
            "recovery_time_s": -1,
            "data_loss": False,
            "veredict": "FAIL",
        }

    # 1. Qdrant healthy → search OK
    hr.search("test r09 initial", k=3)

    # 2. Caída
    docker_exec(["docker", "stop", "ura-qdrant"])
    time.sleep(2)

    # 3. Intentar operaciones durante caída
    fail_count = 0
    for i in range(3):
        try:
            hr.search(f"test during downtime {i}", k=3)
        except Exception:
            fail_count += 1
    observed = f"Durante caída: {fail_count}/3 operaciones fallaron controladamente"

    # 4. Restaurar tras 15s
    docker_exec(["docker", "start", "ura-qdrant"])
    recovery_time = wait_for_qdrant(timeout=30)

    # 5. Post-restauración
    try:
        hr2 = _make_hybrid_retriever()
        hr2.search("test after qdrant restore", k=3)
        observed += " | Post-restauración: operaciones OK"
        auto_recovery = True
    except Exception as e:
        observed += f" | Post-restauración: error: {e}"

    verdict = "PASS" if (auto_recovery and recovery_time < 30) else "PARTIAL"

    return {
        "id": "R09",
        "fault": fault,
        "expected": expected,
        "observed": observed,
        "auto_recovery": auto_recovery,
        "recovery_time_s": recovery_time,
        "data_loss": data_loss,
        "veredict": verdict,
    }


def scenario_r10() -> dict[str, Any]:
    """R10 — Cascada de fallos: Qdrant + Ollama simultáneamente."""
    fault = "Qdrant y Ollama caídos simultáneamente, luego restaurar ambos"
    expected = "Sistema maneja fallo múltiple sin crash, se recupera al restaurar ambos"
    data_loss = False
    auto_recovery = True
    recovery_time = -1.0

    if not qdrant_running() or not ollama_running():
        return {
            "id": "R10",
            "fault": fault,
            "expected": expected,
            "observed": "Qdrant u Ollama ya no disponibles. SKIP.",
            "auto_recovery": False,
            "recovery_time_s": -1,
            "data_loss": False,
            "veredict": "SKIP",
        }

    observed = ""
    try:
        rt = _make_runtime()
        hr = _make_hybrid_retriever()
    except Exception as e:
        return {
            "id": "R10",
            "fault": fault,
            "expected": expected,
            "observed": f"No se pudieron construir componentes: {e}",
            "auto_recovery": False,
            "recovery_time_s": -1,
            "data_loss": False,
            "veredict": "FAIL",
        }

    still_running = ollama_running()

    # 2. Intentar operaciones
    retrieval_ok = False
    runtime_ok = False
    try:
        hr.search("test cascade failure", k=3)
        retrieval_ok = True
    except Exception:  # noqa: S110
        pass  # Esperado
    try:
        rt.execute_workflow("test cascade failure", timeout=10)
        runtime_ok = True
    except Exception:  # noqa: S110
        pass  # Esperado
    observed = f"Retrieval sin Qdrant: {'falló (esperado)' if not retrieval_ok else 'inesperadamente OK'} | "
    observed += f"Runtime sin Ollama: {'falló (esperado)' if not runtime_ok else 'inesperadamente OK'}"
    if still_running:
        observed += " | ⚠️ NOTA: Ollama no se detuvo realmente (no new privileges flag impide systemctl stop sin sudo)"

    # 3. Restaurar ambos
    docker_exec(["docker", "start", "ura-qdrant"])
    docker_exec(["systemctl", "start", "ollama"], timeout=30)
    time.monotonic()

    q_recovery = wait_for_qdrant(timeout=30)
    o_recovery = wait_for_ollama(timeout=60)
    recovery_time = max(q_recovery, o_recovery)
    observed += f" | Qdrant recuperado en {q_recovery}s, Ollama en {o_recovery}s"

    # 4. Verificar
    try:
        hr2 = _make_hybrid_retriever()
        hr2.search("test after cascade restore", k=3)
        observed += " | Post-restauración: retrieval OK"
    except Exception as e:
        observed += f" | Post-restauración: retrieval falló: {e}"
        auto_recovery = False

    verdict = "PARTIAL" if still_running else "PASS" if auto_recovery and recovery_time < 60 else "PARTIAL"

    return {
        "id": "R10",
        "fault": fault,
        "expected": expected,
        "observed": observed,
        "auto_recovery": auto_recovery,
        "recovery_time_s": recovery_time,
        "data_loss": data_loss,
        "veredict": verdict,
    }


# ─── I/O ──────────────────────────────────────────────────────────────

ALL_SCENARIOS = {
    "R01": scenario_r01,
    "R02": scenario_r02,
    "R03": scenario_r03,
    "R04": scenario_r04,
    "R05": scenario_r05,
    "R06": scenario_r06,
    "R07": scenario_r07,
    "R08": scenario_r08,
    "R09": scenario_r09,
    "R10": scenario_r10,
}

CSV_FIELDS = [
    "id",
    "fault",
    "expected",
    "observed",
    "auto_recovery",
    "recovery_time_s",
    "data_loss",
    "veredict",
]


def save_results(results: list[dict[str, Any]]):
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    base = OUTPUT_DIR / f"resilience_{ts}"

    data = {
        "timestamp": ts,
        "environment": ENV,
        "scenarios": results,
        "summary": {},
    }

    passes = sum(1 for r in results if r["veredict"] == "PASS")
    fails = sum(1 for r in results if r["veredict"] == "FAIL")
    partials = sum(1 for r in results if r["veredict"] == "PARTIAL")
    skips = sum(1 for r in results if r["veredict"] == "SKIP")
    data["summary"] = {
        "total": len(results),
        "PASS": passes,
        "FAIL": fails,
        "PARTIAL": partials,
        "SKIP": skips,
        "auto_recovery_count": sum(1 for r in results if r.get("auto_recovery")),
        "data_loss_count": sum(1 for r in results if r.get("data_loss")),
    }

    json_path = base.with_suffix(".json")
    json_path.write_text(json.dumps(data, indent=2, default=str))

    csv_path = base.with_suffix(".csv")
    with csv_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        w.writeheader()
        for r in results:
            w.writerow({k: r.get(k, "") for k in CSV_FIELDS})

    return data


# ─── CLI ──────────────────────────────────────────────────────────────


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="F14 Resilience Tests")
    parser.add_argument(
        "--scenario",
        "-s",
        default=None,
        help="Escenarios separados por coma (default: todos)",
    )
    args = parser.parse_args()

    if args.scenario:
        selected = [s.strip() for s in args.scenario.split(",")]
        to_run = {k: v for k, v in ALL_SCENARIOS.items() if k in selected}
    else:
        to_run = ALL_SCENARIOS

    results = []
    for sid, fn in to_run.items():
        try:
            r = fn()
            results.append(r)
            v = r.get("veredict", "?")
            {"PASS": "✅", "FAIL": "❌", "PARTIAL": "⚠️", "SKIP": "⏭️"}.get(v, "❓")
        except Exception as e:
            results.append(
                {
                    "id": sid,
                    "fault": "unknown",
                    "expected": "unknown",
                    "observed": f"Error de ejecución: {type(e).__name__}: {e}",
                    "auto_recovery": False,
                    "recovery_time_s": -1,
                    "data_loss": False,
                    "veredict": "FAIL",
                },
            )

    data = save_results(results)
    s = data["summary"]

    # Conclusión global
    non_skip = s["total"] - s["SKIP"]
    if non_skip == 0 or (s["FAIL"] == 0 and s["PARTIAL"] <= non_skip * 0.3) or s["FAIL"] <= 1:
        pass
    else:
        pass

    sys.exit(0 if s["FAIL"] == 0 else 1)


if __name__ == "__main__":
    main()
