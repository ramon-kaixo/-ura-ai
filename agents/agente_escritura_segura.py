#!/usr/bin/env python3
"""agente_escritura_segura.py — Escribe archivos solo en rutas permitidas."""

import os
import sys

RUTAS_PERMITIDAS = [
    "/opt/ura/www/",
    "/opt/ura/config/prompts/",
    "/opt/ura/data/",
    os.path.expanduser("~/URA/ura_ia_1972/dashboard/"),
    os.path.expanduser("~/URA/ura_ia_1972/config/"),
]


def escribir(archivo, contenido):
    archivo = os.path.abspath(os.path.expanduser(archivo))
    permitido = any(archivo.startswith(r) for r in RUTAS_PERMITIDAS)
    if not permitido:
        return f"Ruta no permitida: {archivo}"
    if ".." in archivo:
        return "Ruta invalida: contiene .."
    try:
        os.makedirs(os.path.dirname(archivo), exist_ok=True)
        with open(archivo, "w") as f:
            f.write(contenido)
        return f"OK: {archivo} escrito ({len(contenido)} bytes)"
    except Exception as e:
        return f"Error: {e}"


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("USO: agente_escritura_segura.py <archivo> <contenido>")
        sys.exit(1)
    archivo = sys.argv[1]
    contenido = " ".join(sys.argv[2:])
    print(escribir(archivo, contenido))
