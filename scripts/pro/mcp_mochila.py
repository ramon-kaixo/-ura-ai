#!/usr/bin/env python3
"""MCP stdio server wrapping mochila tools + HybridMemory for OpenClaw."""

import asyncio
import json
import os
import sys
import time
import traceback
from pathlib import Path

from core.mochila.tools import TOOL_SCHEMAS, ejecutar_tool
from motor.intelligence.memory.hybrid import HybridMemory
from motor.intelligence.memory.record import MemoryType
from motor.observability.health import HealthRegistry

SERVER_NAME = "ura-mcp"
SERVER_VERSION = "2.0.0"

_db_path = os.environ.get("URA_MEMORY_DB", str(Path.home() / ".ura" / "memory.db"))
_memory = HybridMemory(db_path=_db_path)
_health = HealthRegistry()
_health.register_component("mcp_server")
_health.register_component("hybrid_memory")

# Rate limiter: 60 calls/min
_RATE_LIMIT = 60
_RATE_WINDOW = 60.0
_call_times: list[float] = []


def _check_rate_limit() -> bool:
    now = time.monotonic()
    global _call_times
    _call_times = [t for t in _call_times if now - t < _RATE_WINDOW]
    if len(_call_times) >= _RATE_LIMIT:
        return False
    _call_times.append(now)
    return True

_MEMORY_TOOL_SCHEMAS = [
    {
        "name": "memory_store",
        "description": "Almacena un texto en la memoria híbrida con metadatos",
        "inputSchema": {
            "type": "object",
            "properties": {
                "payload": {"type": "string", "description": "Texto a almacenar"},
                "memory_type": {
                    "type": "string",
                    "enum": [t.value for t in MemoryType],
                    "description": "Tipo de memoria",
                },
                "metadata": {
                    "type": "object",
                    "description": "Metadatos adicionales (source, tags, etc.)",
                },
            },
            "required": ["payload"],
        },
    },
    {
        "name": "memory_search",
        "description": "Busca en la memoria híbrida por texto completo",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Consulta de búsqueda"},
                "k": {"type": "integer", "description": "Máximo de resultados", "default": 10},
                "memory_type": {
                    "type": "string",
                    "enum": [t.value for t in MemoryType],
                    "description": "Filtrar por tipo de memoria",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "memory_investigate",
        "description": "Investiga un tema: busca en memoria, sintetiza y almacena el resultado",
        "inputSchema": {
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "Pregunta o tema a investigar"},
                "k": {"type": "integer", "description": "Máximo de fuentes locales", "default": 5},
            },
            "required": ["question"],
        },
    },
    {
        "name": "memory_research",
        "description": "Investigación completa: web + memoria híbrida + síntesis",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Consulta de investigación"},
                "web_results": {"type": "integer", "description": "Resultados web", "default": 5},
                "local_results": {"type": "integer", "description": "Resultados en memoria", "default": 5},
            },
            "required": ["query"],
        },
    },
    {
        "name": "memory_stats",
        "description": "Estadísticas de la memoria híbrida",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "ura_health",
        "description": "Estado de salud de todos los componentes del sistema",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
]

_ALL_TOOLS = _MEMORY_TOOL_SCHEMAS + [
    {
        "name": s["function"]["name"],
        "description": s["function"].get("description", ""),
        "inputSchema": s["function"].get("parameters", {}),
    }
    for s in TOOL_SCHEMAS
]


async def _handle_initialize(params: dict) -> dict:
    _health.set_healthy("mcp_server")
    mem_health = _memory.health()
    if mem_health.get("total_records", -1) >= 0 and mem_health.get("vector_store_ok", True):
        _health.set_healthy("hybrid_memory", f"{mem_health.get('total_records', 0)} registros")
    else:
        _health.set_degraded("hybrid_memory", str(mem_health))
    return {
        "protocolVersion": params.get("protocolVersion", "2024-11-05"),
        "capabilities": {"tools": {}},
        "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
    }


async def _handle_tools_list(params: dict) -> dict:
    return {"tools": _ALL_TOOLS}


async def _handle_tools_call(params: dict) -> dict:
    name = params.get("name", "")
    arguments = params.get("arguments", {})
    try:
        if name == "memory_store":
            rid = _memory.store(
                payload=arguments["payload"],
                memory_type=MemoryType(arguments.get("memory_type", "working")),
                metadata=arguments.get("metadata"),
            )
            _health.set_healthy("hybrid_memory", f"{_memory.count()} registros")
            return {"content": [{"type": "text", "text": json.dumps({"id": rid}, ensure_ascii=False)}]}
        elif name == "memory_search":
            results = _memory.search(
                query=arguments["query"],
                k=arguments.get("k", 10),
                memory_type=MemoryType(arguments["memory_type"]) if arguments.get("memory_type") else None,
            )
            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(
                            [
                                {"id": r.id, "payload": r.payload[:500], "type": r.type.value, "metadata": r.metadata}
                                for r in results
                            ],
                            ensure_ascii=False,
                        ),
                    }
                ]
            }
        elif name == "memory_investigate":
            question = arguments.get("question", "")
            k = arguments.get("k", 5)
            sources = _memory.search(query=question, k=k)
            context = "\n".join(f"- {s.payload[:300]}" for s in sources) if sources else "Sin fuentes disponibles."
            synthesis = (
                f"## Investigación: {question}\n\n"
                f"### Fuentes consultadas ({len(sources)})\n{context}\n\n"
                f"### Síntesis\n"
                f"Se consultaron {len(sources)} fuentes en la memoria híbrida. "
                + ("La información disponible sugiere que este tema tiene cobertura documental."
                   if sources else "No se encontraron fuentes relevantes en la memoria.")
            )
            rid = ""
            if sources:
                rid = _memory.store(
                    payload=synthesis,
                    memory_type=MemoryType.SEMANTIC,
                    metadata={"type": "research", "question": question, "sources": len(sources)},
                )
            return {
                "content": [
                    {"type": "text", "text": json.dumps({
                        "id": rid,
                        "synthesis": synthesis,
                        "sources_count": len(sources),
                    }, ensure_ascii=False)}
                ]
            }
        elif name == "memory_research":
            query = arguments.get("query", "")
            web_k = arguments.get("web_results", 5)
            local_k = arguments.get("local_results", 5)

            web_results: list[dict] = []
            try:
                wr = await ejecutar_tool("web_search", {"query": query, "max_results": web_k})
            except Exception:
                wr = {"error": "web_search not available", "results": []}
            if isinstance(wr, dict):
                for item in (wr.get("results", []) if isinstance(wr.get("results"), list) else []):
                    web_results.append({"source": "web", "title": item.get("title", ""), "snippet": item.get("snippet", "")[:300]})

            local_sources = _memory.search(query=query, k=local_k)
            local_results = [{"source": "memory", "title": s.payload[:100], "snippet": s.payload[:300]} for s in local_sources]

            all_sources = web_results + local_results
            synthesis_lines = [f"## Investigación: {query}", "",
                               f"### Fuentes ({len(all_sources)})", ""]
            for src in all_sources:
                synthesis_lines.append(f"- [{src['source']}] {src['title']}")
                if src.get("snippet"):
                    synthesis_lines.append(f"  {src['snippet']}")
            synthesis_lines.extend(["", "### Síntesis",
                                    f"Se consultaron {len(web_results)} fuentes web y {len(local_results)} fuentes locales."])

            synthesis = "\n".join(synthesis_lines)
            rid = _memory.store(
                payload=synthesis,
                memory_type=MemoryType.SEMANTIC,
                metadata={"type": "research_web", "query": query, "web_sources": len(web_results), "local_sources": len(local_results)},
            )
            return {
                "content": [
                    {"type": "text", "text": json.dumps({
                        "id": rid,
                        "synthesis": synthesis,
                        "web_sources": len(web_results),
                        "local_sources": len(local_results),
                    }, ensure_ascii=False)}
                ]
            }
        elif name == "memory_stats":
            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(_memory.health(), ensure_ascii=False),
                    }
                ]
            }
        elif name == "ura_health":
            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(_health.snapshot(), ensure_ascii=False),
                    }
                ]
            }
        result = await ejecutar_tool(name, arguments)
        return {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]}
    except Exception as e:
        import logging as _logging

        _logging.getLogger("ura.mcp").exception("Tool call failed: %s", name)
        return {
            "isError": True,
            "content": [{"type": "text", "text": json.dumps({"error": str(e)}, ensure_ascii=False)}],
        }


async def _send(response: dict) -> bool:
    """Envía respuesta JSON-RPC. Retorna False si stdout está roto."""
    if response.get("id") is None:
        return True
    try:
        sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
        sys.stdout.flush()
        return True
    except OSError:
        return False


async def main() -> None:
    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    stdin_pipe = getattr(sys.stdin.buffer, "raw", sys.stdin.buffer)
    await asyncio.get_event_loop().connect_read_pipe(lambda: protocol, stdin_pipe)

    msg: dict | None = None
    while True:
        try:
            line = await reader.readline()
            if not line:
                break
            decoded = line.decode("utf-8").strip()
            if not decoded:
                continue
            try:
                msg = json.loads(decoded)
            except json.JSONDecodeError:
                if not await _send({
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32700, "message": "Parse error"},
                }):
                    break
                continue
            if not isinstance(msg, dict):
                if not await _send({
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32600, "message": "Invalid Request"},
                }):
                    break
                continue

            method = msg.get("method", "")
            msg_id = msg.get("id")
            params = msg.get("params", {})

            if method != "initialize" and not _check_rate_limit():
                if not await _send({
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {"code": -32000, "message": "Rate limit exceeded (60/min)"},
                }):
                    break
                continue

            if method == "initialize":
                result = await _handle_initialize(params)
                response = {"jsonrpc": "2.0", "id": msg_id, "result": result}
            elif method == "notifications/initialized":
                continue
            elif method == "tools/list":
                result = await _handle_tools_list(params)
                response = {"jsonrpc": "2.0", "id": msg_id, "result": result}
            elif method == "tools/call":
                result = await _handle_tools_call(params)
                response = {"jsonrpc": "2.0", "id": msg_id, "result": result}
            else:
                response = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {"code": -32601, "message": f"Method not found: {method}"},
                }

            if not await _send(response):
                break

        except Exception:
            traceback.print_exc(file=sys.stderr)
            sys.stderr.flush()
            err_response = {
                "jsonrpc": "2.0",
                "id": msg.get("id") if msg and isinstance(msg, dict) else None,
                "error": {"code": -32603, "message": "Internal error"},
            }
            if not await _send(err_response):
                break


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, asyncio.CancelledError):
        sys.exit(0)
    except Exception:
        traceback.print_exc(file=sys.stderr)
        sys.stderr.flush()
    sys.exit(0)
