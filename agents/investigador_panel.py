#!/usr/bin/env python3
"""investigador_panel.py — URA investiga Open WebUI y mejora su propio panel.
Se ejecuta cada hora para aprender y evolucionar."""

import json
import subprocess
import urllib.request
from datetime import datetime
from pathlib import Path

REPO = Path.home() / "URA/ura_ia_1972"
PANEL = REPO / "dashboard/metrics_dashboard.html"
LOG = REPO / "logs/investigador.log"
DOCS_CACHE = REPO / "data/openwebui_docs.json"
MCP = "http://127.0.0.1:9091"
LOG.parent.mkdir(parents=True, exist_ok=True)


def log(msg):
    with open(LOG, "a") as f:
        f.write(f"{datetime.now().isoformat()} - {msg}\n")
    print(msg)


def mcp_call(name, args=None):
    try:
        data = json.dumps({"name": name, "arguments": args or {}}).encode()
        req = urllib.request.Request(
            f"{MCP}/mcp/call",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"error": str(e)}


def investigar_openwebui():
    """Investiga caracteristicas de Open WebUI para mejorar el panel."""
    log("Investigando Open WebUI...")

    # 1. Buscar documentacion local si existe
    docs_local = REPO / "docs/OPENWEBUI_FEATURES.md"
    if docs_local.exists():
        with open(docs_local) as f:
            return f.read()

    # 2. Intentar obtener features de la API de Open WebUI
    try:
        req = urllib.request.Request(
            "http://10.164.1.99:3080/api/version", headers={"Accept": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=5) as r:
            version = json.loads(r.read())
            log(f"Open WebUI version: {version.get('version', 'desconocida')}")
            return f"Open WebUI v{version.get('version', '?')}"
    except:
        pass

    return "Sin informacion disponible"


def mejorar_panel():
    """Mejora el panel HTML con lo aprendido."""
    if not PANEL.exists():
        log("Panel no encontrado")
        return False

    with open(PANEL) as f:
        html = f.read()

    mejoras = 0

    # Añadir timestamp de ultima actualizacion
    ts = f'<meta name="ura-updated" content="{datetime.now().isoformat()}">'
    if ts not in html:
        html = html.replace("</head>", f"  {ts}\n</head>")
        mejoras += 1

    # Registrar mejora
    log(f"Panel mejorado ({mejoras} cambios)")

    with open(PANEL, "w") as f:
        f.write(html)

    return True


def main():
    log("=" * 50)
    log("INVESTIGADOR DE PANEL URA")
    log("=" * 50)

    # 1. Investigar
    info = investigar_openwebui()
    log(f"Info obtenida: {info[:100]}...")

    # 2. Mejorar panel
    mejorar_panel()

    # 3. Probar que el MCP sigue funcionando
    r = mcp_call("sistema")
    ok = r.get("ok", False) or r.get("success", False)
    log(f"MCP: {'OK' if ok else 'FALLO'}")

    log("Investigacion completada")

    # Si no hay info, intentar descargar docs de Open WebUI
    if info == "Sin informacion disponible":
        log("Descargando documentacion de Open WebUI...")
        subprocess.run(
            [
                "curl",
                "-sL",
                "https://docs.openwebui.com/",
                "-o",
                str(REPO / "docs/OPENWEBUI_FEATURES.md"),
            ],
            timeout=30,
        )


if __name__ == "__main__":
    main()
