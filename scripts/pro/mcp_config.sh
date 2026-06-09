#!/bin/bash
# MCP Config for Claude Desktop + OpenCode
# Instala y levanta servidores MCP

echo "[1/2] Instalando server-filesystem..."
npm install -g @modelcontextprotocol/server-filesystem 2>/dev/null && echo "  OK"

echo "[2/2] Generando config..."
mkdir -p "$HOME/.config/Claude"
cat > "$HOME/.config/Claude/claude_desktop_config.json" << 'JSON'
{
  "mcpServers": {
    "ura-files": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/home/ramon/URA/ura_ia_1972"]
    }
  }
}
JSON
echo "  Config en ~/.config/Claude/claude_desktop_config.json"
echo "  Lanzar: nohup npx @modelcontextprotocol/server-filesystem /home/ramon/URA/ura_ia_1972 &"
