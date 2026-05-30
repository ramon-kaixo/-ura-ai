#!/usr/bin/env python3
"""actualizador_lista_blanca.py — URA anade comandos a su propia lista blanca de seguridad.
Invocado automaticamente cuando necesita un comando nuevo."""

import sys
import os
import re
from pathlib import Path

MCP_SERVER = Path("/opt/ura/agents/ura_mcp_server.py")

COMANDOS_SEGUROS = [
    "chmod 644",
    "chmod 755",
    "cp ",
    "mv ",
    "mkdir -p",
    "cat ",
    "ls ",
    "echo ",
    "tail ",
    "head ",
    "grep ",
    "ps aux",
    "df -h",
    "free -h",
    "uptime",
    "whoami",
    "curl -s http://",
    "ping -c",
]


def es_seguro(comando):
    """Verifica que el comando no sea peligroso."""
    peligrosos = [
        "rm -rf /",
        "rm -rf ~",
        "sudo ",
        "shutdown",
        "reboot",
        "dd ",
        "mkfs",
        "format",
        "> /dev/",
        "chmod 777 /",
        "kill -9",
        "pkill -9",
    ]
    for p in peligrosos:
        if p in comando:
            return False, f"Comando peligroso detectado: {p}"
    for s in COMANDOS_SEGUROS:
        if comando.startswith(s):
            return True, ""
    return False, "Comando no reconocido como seguro"


def anadir(comando):
    seguro, motivo = es_seguro(comando)
    if not seguro:
        return f"BLOQUEADO: {motivo}"

    if not MCP_SERVER.exists():
        return "ERROR: MCP server no encontrado"

    with open(MCP_SERVER) as f:
        contenido = f.read()

    # Verificar si ya existe
    if comando in contenido:
        return f"YA_EXISTE: {comando}"

    # Anadir a COMANDOS_PERMITIDOS
    # Buscar la linea de cierre de la lista
    patron = r"(COMANDOS_PERMITIDOS\s*=\s*\[.*?)(\])"

    def reemplazo(m):
        return m.group(1) + f'\n    "{comando}",' + m.group(2)

    nuevo = re.sub(patron, reemplazo, contenido, flags=re.DOTALL)

    if nuevo == contenido:
        return "ERROR: No se pudo modificar la lista"

    with open(MCP_SERVER, "w") as f:
        f.write(nuevo)

    # Reiniciar MCP
    os.system(
        "pkill -f ura_mcp_server 2>/dev/null; sleep 1; cd /opt/ura/agents && nohup python3 ura_mcp_server.py 9091 > /opt/ura/logs/ura_mcp.log 2>&1 & disown"
    )

    return f"ANADIDO: {comando}"


if __name__ == "__main__":
    if len(sys.argv) > 1:
        print(anadir(" ".join(sys.argv[1:])))
    else:
        print("USO: python3 actualizador_lista_blanca.py <comando>")
