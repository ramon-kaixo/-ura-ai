#!/usr/bin/env python3
"""Test e2e CentralRouter en GX10."""

import asyncio
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "core")
sys.path.insert(0, "agents")

from core.central_router import CentralRouter


async def test_e2e():
    r = CentralRouter()

    # Test 1: Chat
    res = await r.process_request("hola, ¿como estas?")
    assert res["intent"] == "chat", f"Expected chat, got {res['intent']}"
    print(f"[1/7] Chat OK: {res['response'][:40]}...")

    # Test 2: Factura
    res2 = await r.process_request("crea una factura para cliente Perez")
    assert "factura" in res2["intent"]
    print(f"[2/7] Factura OK: intent={res2['intent']}")

    # Test 3: Cocina
    res3 = await r.process_request("dame una receta de paella")
    assert "cocina" in res3["intent"]
    print(f"[3/7] Cocina OK: intent={res3['intent']}")

    # Test 4: Lista agentes
    agents = r.list_agents()
    print(f"[4/7] List agents OK: {len(agents)} agentes")

    # Test 5: Metadata
    meta = r._get_agent_metadata(
        "cocina_espanola", "agents.agente_cocina_espanola.AgenteCocinaEspanola"
    )
    print(f"[5/7] Metadata OK: {meta['intent']}")

    # Test 6: Similar agent
    sim = r._find_similar_agent("cocina_espanola")
    print(f"[6/7] Similar agent OK: {sim}")

    # Test 7: Status
    status = r.get_status()
    print(f"[7/7] Status OK: intents={status['intents']}, agents={status['agents']}")

    print("\n=== TODOS LOS TESTS PASARON ===")


asyncio.run(test_e2e())
