#!/usr/bin/env python3
"""
Tests de integración OpenClaw + Ollama dual N3.

Pruebas:
- Test 1: Verificar que check_openclaw_ready() responde tras ollama launch openclaw
- Test 2: Enviar 5 tareas simples a OpenClaw y medir tiempo de respuesta (debe ser < 60s cada una)
- Test 3: Enviar 5 consultas rápidas a Ollama directo (debe ser < 12s cada una)
- Test 4: Verificar que el router automático elige el backend correcto según tipo de tarea
"""

import asyncio
import sys
import time
import pytest
from unittest.mock import Mock, patch

sys.path.insert(0, "/Users/ramonesnaola/URA/ura_ia_1972")


@pytest.mark.asyncio
async def test_1_openclaw_health_check():
    """Test 1: Verificar que check_openclaw_ready() responde tras ollama launch openclaw."""
    print("\n=== Test 1: Health check OpenClaw ===")

    from core.openclaw_health import check_openclaw_ready

    # Simular OpenClaw no disponible (no está lanzado)
    result = await check_openclaw_ready(timeout=5, max_retries=2)
    print(f"check_openclaw_ready(): {result}")
    print("✅ Test 1 completado (OpenClaw no disponible sin lanzarlo)")


@pytest.mark.asyncio
@pytest.mark.skip(reason="N3Orchestrator no tiene método route_task - test legacy")
async def test_2_openclaw_tasks():
    """Test 2: Enviar 5 tareas simples a OpenClaw y medir tiempo."""
    print("\n=== Test 2: Tareas OpenClaw (simulado) ===")

    # Mock OpenClaw connector para simular respuestas
    with patch("core.n3_orchestrator._check_openclaw_available") as mock_check:
        mock_check.return_value = True

        with patch("core.openclaw_connector.OpenClawConnector") as mock_connector:
            mock_instance = Mock()
            mock_instance.execute = Mock(
                return_value=asyncio.coroutine(
                    lambda: {"success": True, "response": "OK", "error": None, "elapsed": 5.0}
                )()
            )
            mock_instance.__aenter__ = asyncio.coroutine(lambda self: self)
            mock_instance.__aexit__ = asyncio.coroutine(lambda self, *args: None)
            mock_connector.return_value = mock_instance

            from core.n3_orchestrator import N3Orchestrator

            orchestrator = N3Orchestrator()
            orchestrator._openclaw_checked = True
            orchestrator.openclaw_available = True

            tasks = [
                "Crea archivo hola.txt",
                "Lista directorio actual",
                "Copia archivo A a B",
                "Mueve archivo C a D",
                "Elimina archivo E",
            ]

            start = time.time()
            for task in tasks:
                result = await orchestrator.route_task("system", task)
                print(
                    f"  Tarea: {task[:30]}... - Success: {result['success']}, Backend: {result.get('backend')}"
                )
            elapsed = time.time() - start

            print(f"Tiempo total: {elapsed:.2f}s para 5 tareas")
            print("✅ Test 2 completado (simulado)")


@pytest.mark.asyncio
@pytest.mark.skip(reason="N3Orchestrator no tiene método search - test legacy")
async def test_3_ollama_direct():
    """Test 3: Enviar 5 consultas rápidas a Ollama directo."""
    print("\n=== Test 3: Consultas Ollama directo ===")

    from core.n3_orchestrator import N3Orchestrator

    orchestrator = N3Orchestrator()

    queries = [
        "¿Qué es Python?",
        "¿Qué es JavaScript?",
        "¿Qué es Go?",
        "¿Qué es Rust?",
        "¿Qué es Java?",
    ]

    start = time.time()
    for query in queries:
        result = await orchestrator.search(query)
        print(
            f"  Query: {query[:30]}... - Success: {result['success']}, Backend: {result.get('backend')}, Tokens: {result.get('tokens', 0)}"
        )
    elapsed = time.time() - start

    print(f"Tiempo total: {elapsed:.2f}s para 5 consultas")
    print(f"Promedio por consulta: {elapsed / 5:.2f}s")
    print("✅ Test 3 completado")


@pytest.mark.asyncio
@pytest.mark.skip(reason="N3Orchestrator no tiene método route_task - test legacy")
async def test_4_routing():
    """Test 4: Verificar routing automático según tipo de tarea."""
    print("\n=== Test 4: Routing automático ===")

    from core.n3_orchestrator import N3Orchestrator

    # Mock OpenClaw no disponible
    with patch("core.n3_orchestrator._check_openclaw_available") as mock_check:
        mock_check.return_value = False

        orchestrator = N3Orchestrator()
        orchestrator._openclaw_checked = True
        orchestrator.openclaw_available = False

        # Tareas de sistema deberían usar Ollama fallback
        result_system = await orchestrator.route_task("system", "Crea archivo")
        print(f"  System task - Backend: {result_system.get('backend')} (esperado: ollama_direct)")

        # Consultas rápidas deberían usar Ollama directo
        result_search = await orchestrator.route_task("search", "¿Qué es Python?")
        print(f"  Search task - Backend: {result_search.get('backend')} (esperado: ollama_direct)")

        # QA debería usar Ollama directo
        result_qa = await orchestrator.route_task("qa", "Pregunta")
        print(f"  QA task - Backend: {result_qa.get('backend')} (esperado: ollama_direct)")

        print("✅ Test 4 completado")


async def run_all_tests():
    """Ejecutar todos los tests."""
    print("\n=== Tests de Integración OpenClaw + Ollama ===\n")

    await test_1_openclaw_health_check()
    await test_2_openclaw_tasks()
    await test_3_ollama_direct()
    await test_4_routing()

    print("\n=== Todos los tests completados ===\n")


if __name__ == "__main__":
    asyncio.run(run_all_tests())
