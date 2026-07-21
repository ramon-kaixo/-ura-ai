#!/usr/bin/env python3
"""MCP stdio server wrapping mochila tools + HybridMemory for OpenClaw."""

import asyncio
import json
import os
import sys
import traceback
from pathlib import Path

from core.mochila.tools import TOOL_SCHEMAS, ejecutar_tool
from motor.intelligence.memory.hybrid import HybridMemory
from motor.intelligence.memory.record import MemoryType

SERVER_NAME = "ura-mcp"
SERVER_VERSION = "2.0.0"

_db_path = os.environ.get("URA_MEMORY_DB", str(Path.home() / ".ura" / "memory.db"))
_memory = HybridMemory(db_path=_db_path)

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
        "name": "memory_stats",
        "description": "Estadísticas de la memoria híbrida",
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
_ALL_TOOL_NAMES = {t["name"] for t in _ALL_TOOLS}


async def _handle_initialize(params: dict) -> dict:
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
        elif name == "memory_stats":
            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(_memory.health(), ensure_ascii=False),
                    }
                ]
            }
        result = await ejecutar_tool(name, arguments)
        return {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]}
    except Exception as e:
        return {
            "isError": True,
            "content": [{"type": "text", "text": json.dumps({"error": str(e)}, ensure_ascii=False)}],
        }


async def main() -> None:
    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    await asyncio.get_event_loop().connect_read_pipe(lambda: protocol, sys.stdin)

    while True:
        try:
            line = await reader.readline()
            if not line:
                break
            decoded = line.decode("utf-8").strip()
            if not decoded:
                continue
            msg = json.loads(decoded)
            method = msg.get("method", "")
            msg_id = msg.get("id")
            params = msg.get("params", {})

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

            if response.get("id") is not None:
                sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
                sys.stdout.flush()

        except json.JSONDecodeError:
            continue
        except Exception:
            traceback.print_exc(file=sys.stderr)
            sys.stderr.flush()
            try:
                err_response = {
                    "jsonrpc": "2.0",
                    "id": msg.get("id") if "msg" in dir() else None,
                    "error": {"code": -32603, "message": "Internal error"},
                }
                if err_response.get("id") is not None:
                    sys.stdout.write(json.dumps(err_response, ensure_ascii=False) + "\n")
                    sys.stdout.flush()
            except Exception:  # noqa: S110
                pass


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception:
        traceback.print_exc(file=sys.stderr)
        sys.stderr.flush()
    sys.exit(0)
