#!/usr/bin/env python3
"""MCP server exposing Mochila tools (web_search, page_read, file_read).

Registrar en openclaw.json:
  "mochila-tools": {
    "command": "python3",
    "args": ["-u", "/home/ramon/URA/ura_ia_1972/scripts/pro/mcp_mochila.py"]
  }
"""
import json
import sys

sys.path.insert(0, "/home/ramon/URA/ura_ia_1972")

from mcp.server.fastmcp import FastMCP
from core.mochila.tools import web_search, page_read, file_read

mcp = FastMCP("mochila-tools")


@mcp.tool()
async def mcp_web_search(query: str, max_results: int = 5) -> str:
    """Busca informacion actualizada en internet usando DuckDuckGo."""
    resultado = await web_search(query, max_results)
    return json.dumps(resultado, ensure_ascii=False, indent=2)


@mcp.tool()
async def mcp_page_read(url: str, max_chars: int = 50000) -> str:
    """Lee el contenido textual de una URL."""
    resultado = await page_read(url, max_chars)
    return json.dumps(resultado, ensure_ascii=False, indent=2)


@mcp.tool()
async def mcp_file_read(path: str, max_lines: int = 200) -> str:
    """Lee el contenido de un archivo local del proyecto URA."""
    resultado = await file_read(path, max_lines)
    return json.dumps(resultado, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    mcp.run()
