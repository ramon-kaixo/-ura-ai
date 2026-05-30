#!/usr/bin/env python3
"""agente_lectura.py — Solo lectura. Ejecuta comandos seguros y devuelve salida."""

import subprocess
import sys
import shlex

COMANDOS_PERMITIDOS = {
    "cat",
    "curl",
    "uptime",
    "df",
    "tail",
    "ls",
    "pgrep",
    "ps",
    "grep",
    "head",
    "echo",
    "hostname",
    "date",
    "whoami",
    "free",
    "uname",
}


def ejecutar(comando_str):
    partes = shlex.split(comando_str)
    if not partes:
        return "Comando vacio"
    if partes[0] not in COMANDOS_PERMITIDOS:
        return f"Comando no permitido: {partes[0]}"
    try:
        r = subprocess.run(comando_str, shell=True, capture_output=True, text=True, timeout=30)
        return r.stdout[:5000] if r.returncode == 0 else f"Error: {r.stderr[:500]}"
    except Exception as e:
        return f"Error: {e}"


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("USO: agente_lectura.py <comando>")
        sys.exit(1)
    print(ejecutar(" ".join(sys.argv[1:])))
