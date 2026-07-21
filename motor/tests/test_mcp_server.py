"""Tests de integración para MCP Server.

Verifica el protocolo JSON-RPC 2.0 y la integración con HybridMemory.
Ejecuta los handlers directamente (sin stdio).
"""

from __future__ import annotations

import json

from motor.intelligence.memory.hybrid import HybridMemory
from motor.intelligence.memory.record import MemoryType

# Usar HybridMemory en memoria para los tests
_memory = HybridMemory(db_path=":memory:")


def _make_msg(method: str, params: dict | None = None, msg_id: int | str = 1) -> str:
    msg: dict = {"jsonrpc": "2.0", "method": method, "id": msg_id}
    if params:
        msg["params"] = params
    return json.dumps(msg)


async def _call(method: str, params: dict | None = None) -> dict:
    """Simula una llamada al MCP server."""
    from scripts.pro.mcp_mochila import _handle_initialize, _handle_tools_list, _handle_tools_call

    if method == "initialize":
        result = await _handle_initialize(params or {"protocolVersion": "2024-11-05"})
        return {"jsonrpc": "2.0", "result": result}
    elif method == "tools/list":
        result = await _handle_tools_list(params or {})
        return {"jsonrpc": "2.0", "result": result}
    elif method == "memory_store":
        result = await _handle_tools_call({"name": "memory_store", "arguments": params or {}})
        return {"jsonrpc": "2.0", "result": result}
    elif method == "memory_search":
        result = await _handle_tools_call({"name": "memory_search", "arguments": params or {}})
        return {"jsonrpc": "2.0", "result": result}
    elif method == "memory_stats":
        result = await _handle_tools_call({"name": "memory_stats", "arguments": params or {}})
        return {"jsonrpc": "2.0", "result": result}
    elif method == "ura_health":
        result = await _handle_tools_call({"name": "ura_health", "arguments": params or {}})
        return {"jsonrpc": "2.0", "result": result}
    elif method == "memory_investigate":
        result = await _handle_tools_call({"name": "memory_investigate", "arguments": params or {}})
        return {"jsonrpc": "2.0", "result": result}
    return {"jsonrpc": "2.0", "error": {"code": -32601, "message": "unknown method"}}


def test_initialize():
    import asyncio

    resp = asyncio.run(_call("initialize", {"protocolVersion": "2024-11-05"}))
    assert "result" in resp
    info = resp["result"]["serverInfo"]
    assert info["name"] == "ura-mcp"
    assert info["version"] == "2.0.0"


def test_tools_list():
    import asyncio

    resp = asyncio.run(_call("tools/list"))
    assert "result" in resp
    tools = resp["result"]["tools"]
    names = [t["name"] for t in tools]
    assert "memory_store" in names
    assert "memory_search" in names
    assert "memory_stats" in names
    assert "ura_health" in names
    assert len(tools) >= 7  # 4 memory + mochila tools


def test_memory_store():
    import asyncio

    resp = asyncio.run(_call("memory_store", {"payload": "test memory"}))
    assert "result" in resp
    assert "id" in resp["result"]["content"][0]["text"]
    rid = json.loads(resp["result"]["content"][0]["text"])["id"]
    assert len(rid) == 32  # uuid4 hex


def test_memory_search():
    import asyncio

    # Store first
    asyncio.run(_call("memory_store", {"payload": "el cielo es azul"}))

    # Search
    resp = asyncio.run(_call("memory_search", {"query": "cielo", "k": 5}))
    assert "result" in resp
    results = json.loads(resp["result"]["content"][0]["text"])
    assert len(results) >= 1
    assert "azul" in results[0]["payload"]


def test_memory_search_empty_query():
    import asyncio

    resp = asyncio.run(_call("memory_search", {"query": "", "k": 5}))
    assert "result" in resp
    results = json.loads(resp["result"]["content"][0]["text"])
    assert len(results) == 0


def test_memory_stats():
    import asyncio

    resp = asyncio.run(_call("memory_stats"))
    assert "result" in resp
    stats = json.loads(resp["result"]["content"][0]["text"])
    assert "total_records" in stats
    assert "vector_store_ok" in stats


def test_ura_health():
    import asyncio

    resp = asyncio.run(_call("ura_health"))
    assert "result" in resp
    health = json.loads(resp["result"]["content"][0]["text"])
    assert "global" in health
    assert "components" in health


def test_memory_search_with_type():
    import asyncio

    asyncio.run(_call("memory_store", {
        "payload": "working data",
        "memory_type": "working",
    }))
    asyncio.run(_call("memory_store", {
        "payload": "semantic knowledge",
        "memory_type": "semantic",
    }))

    working = asyncio.run(_call("memory_search", {
        "query": "data",
        "k": 5,
        "memory_type": "working",
    }))
    working_results = json.loads(working["result"]["content"][0]["text"])
    assert len(working_results) >= 1
    assert "working" in working_results[0]["payload"]


def test_memory_store_with_metadata():
    import asyncio

    resp = asyncio.run(_call("memory_store", {
        "payload": "metadatos",
        "metadata": {"source": "test", "tags": ["a", "b"]},
        "memory_type": "semantic",
    }))
    assert "result" in resp
    rid = json.loads(resp["result"]["content"][0]["text"])["id"]
    assert rid


def test_memory_investigate():
    import asyncio

    # Store some context first
    asyncio.run(_call("memory_store", {"payload": "la inteligencia artificial permite procesar lenguaje natural"}))
    asyncio.run(_call("memory_store", {"payload": "los modelos transformers revolucionaron el NLP en 2017"}))
    asyncio.run(_call("memory_store", {"payload": "python es el lenguaje mas usado para IA y ML"}))

    # Investigate
    resp = asyncio.run(_call("memory_investigate", {"question": "inteligencia artificial", "k": 3}))
    assert "result" in resp
    data = json.loads(resp["result"]["content"][0]["text"])
    assert "id" in data
    assert "synthesis" in data
    assert data["sources_count"] >= 1
    assert "inteligencia" in data["synthesis"].lower()


def test_memory_investigate_no_results():
    import asyncio

    resp = asyncio.run(_call("memory_investigate", {"question": "zzzzyxwvutsrqponmlkji", "k": 3}))
    assert "result" in resp
    data = json.loads(resp["result"]["content"][0]["text"])
    assert data["sources_count"] == 0, f"Esperaba 0 fuentes, obtuvo {data['sources_count']}"
