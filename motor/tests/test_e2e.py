"""End-to-end test: verifica que los componentes principales funcionan juntos.

Flujo:
1. Crea una instancia de HybridMemory en memoria
2. Almacena un registro via la API interna
3. Verifica que el registro es buscable
4. Simula el MCP server (store + search)
5. Verifica que los endpoints del dashboard devuelven datos coherentes

No requiere servidores externos (todo en memoria).
"""

from __future__ import annotations

import json

from motor.intelligence.memory.hybrid import HybridMemory
from motor.intelligence.memory.record import MemoryType
from motor.observability.health import HealthRegistry


def test_hybrid_memory_store_and_search():
    """Test básico: almacenar y buscar en HybridMemory."""
    mem = HybridMemory(db_path=":memory:")

    rid = mem.store(payload="prueba de integración extremo a extremo", metadata={"source": "e2e"})
    assert rid
    assert len(rid) == 32

    results = mem.search("integración", k=5)
    assert len(results) >= 1
    assert results[0].id == rid


def test_hybrid_memory_with_types():
    """Test: almacenar con diferentes MemoryType y filtrar."""
    mem = HybridMemory(db_path=":memory:")

    mem.store(
        payload="datos de trabajo",
        memory_type=MemoryType.WORKING,
        metadata={"type": "working"},
    )
    mem.store(
        payload="conocimiento semántico",
        memory_type=MemoryType.SEMANTIC,
        metadata={"type": "semantic"},
    )

    working = mem.search("datos", k=5, memory_type=MemoryType.WORKING)
    assert len(working) >= 1
    assert working[0].metadata.get("type") == "working"

    semantic = mem.search("conocimiento", k=5, memory_type=MemoryType.SEMANTIC)
    assert len(semantic) >= 1
    assert semantic[0].metadata.get("type") == "semantic"


def test_hybrid_memory_delete_and_count():
    """Test: eliminar registros y verificar conteo."""
    mem = HybridMemory(db_path=":memory:")
    assert mem.count() == 0

    rid1 = mem.store(payload="registro 1")
    rid2 = mem.store(payload="registro 2")
    assert mem.count() == 2

    assert mem.delete(rid1)
    assert mem.count() == 1

    assert mem.delete(rid2)
    assert mem.count() == 0


def test_hybrid_memory_health():
    """Test: health() sin vector store debe indicar vector_store_ok=False."""
    mem = HybridMemory(db_path=":memory:")
    h = mem.health()
    assert "total_records" in h
    assert "vector_store_ok" in h
    assert h["vector_store_ok"] is False


def test_health_registry():
    """Test: HealthRegistry reporta estado correctamente."""
    hr = HealthRegistry()
    hr.register_component("test_component")
    hr.set_healthy("test_component")

    snap = hr.snapshot()
    assert snap["global"] == "healthy"
    assert "test_component" in snap["components"]

    hr.set_degraded("test_component", "prueba degradación")
    snap = hr.snapshot()
    assert snap["global"] == "degraded"

# Retirado 2026-08-09 (TASK-20260809-002): test_mcp_memory_tools y test_mcp_ura_health
# probaban scripts.pro.mcp_mochila, archivado en la purga 38b7921c (.attic/tools).
# Sin consumidores vivos; bloqueaban la recolección de pytest/mutmut.
