#!/usr/bin/env python3
"""Genera inventario inicial del codigo URA."""

import hashlib
import json
from pathlib import Path
from datetime import datetime

PROYECTO = Path.home() / "URA" / "ura_ia_1972"
INVENTARIO = PROYECTO / "data" / "inventario" / "inventario_codigo.json"
CARPETAS = ["core", "agents", "services", "handlers", "ui", "dashboard", "api", "scripts"]
EXCLUIR = ["__pycache__", ".pyc", "archive/", "venv/", ".venv/", "node_modules"]


def md5(ruta):
    h = hashlib.md5(usedforsecurity=False)
    with open(ruta, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            h.update(chunk)
    return h.hexdigest()


def lineas(ruta):
    try:
        with open(ruta, encoding="utf-8") as f:
            return sum(1 for _ in f)
    except BaseException:
        return 0


def excluir(ruta):
    return any(e in str(ruta) for e in EXCLUIR)


inv = {"version": 1, "generado": datetime.now().isoformat(), "total_archivos": 0, "archivos": {}}
for carpeta in CARPETAS:
    cp = PROYECTO / carpeta
    if not cp.exists():
        continue
    for ruta in cp.rglob("*.py"):
        if excluir(ruta):
            continue
        rel = str(ruta.relative_to(PROYECTO))
        try:
            st = ruta.stat()
            inv["archivos"][rel] = {
                "tamaño_bytes": st.st_size,
                "hash_md5": md5(ruta),
                "lineas": lineas(ruta),
                "ultima_modificacion": datetime.fromtimestamp(st.st_mtime).isoformat(),
                "estado": "produccion",
                "version": "1.0",
            }
        except Exception as e:
            print(f"Error {ruta}: {e}")

inv["total_archivos"] = len(inv["archivos"])
INVENTARIO.parent.mkdir(parents=True, exist_ok=True)
INVENTARIO.write_text(json.dumps(inv, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"Total: {inv['total_archivos']} archivos")
for c in CARPETAS:
    n = sum(1 for r in inv["archivos"] if r.startswith(c + "/"))
    if n:
        print(f"  {c}/: {n}")
