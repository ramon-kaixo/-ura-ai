"""Constantes para tests de red."""

from __future__ import annotations

# IPs de Tailscale
GX10_TS_IP = "100.72.103.12"
MAC_TS_IP = "100.123.81.101"

# Puertos criticos
CRITICAL_PORTS = {
    22: "SSH",
    8081: "OpenCode API",
    11434: "Ollama",
}
