#!/usr/bin/env python3
"""MCP stdio server wrapping mochila tools for OpenClaw."""

import asyncio
import json
import sys
import traceback

from core.mochila.tools import TOOL_SCHEMAS, ejecutar_tool

SERVER_NAME = "mochila-tools"
SERVER_VERSION = "1.0.0"


def _openai_to_mcp(schema: dict) -> dict:
    func = schema["function"]
    params = func.get("parameters", {})
    return {
        "name": func["name"],
        "description": func.get("description", ""),
        "inputSchema": {
            "type": "object",
            "properties": params.get("properties", {}),
            "required": params.get("required", []),
        },
    }


def _build_tools() -> list[dict]:
    return [_openai_to_mcp(s) for s in TOOL_SCHEMAS]


_MCP_TOOLS = _build_tools()

TOOL_NAME_MAP = {t["name"] for t in _MCP_TOOLS}


async def _handle_initialize(params: dict) -> dict:
    return {
        "protocolVersion": params.get("protocolVersion", "2024-11-05"),
        "capabilities": {"tools": {}},
        "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
    }


async def _handle_tools_list(params: dict) -> dict:
    return {"tools": _MCP_TOOLS}


async def _handle_tools_call(params: dict) -> dict:
    name = params.get("name", "")
    arguments = params.get("arguments", {})
    try:
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
