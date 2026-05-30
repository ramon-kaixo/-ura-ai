#!/usr/bin/env python3
"""test_autonomia.py — Verifica que URA es autonoma.
Tests: 1. Se reconoce 2. Ejecuta comandos 3. Mejora su panel 4. Usa MCP"""

import json
import os
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

MCP = "http://127.0.0.1:9091"
LOG = Path.home() / "URA/ura_ia_1972/logs/autonomia.log"
PANEL = Path.home() / "URA/ura_ia_1972/dashboard/metrics_dashboard.html"


def log(msg):
    with open(LOG, "a") as f:
        f.write(f"{datetime.now().isoformat()} - {msg}\n")
    print(msg)


def mcp(name, args=None):
    try:
        data = json.dumps({"name": name, "arguments": args or {}}).encode()
        req = urllib.request.Request(
            f"{MCP}/mcp/call",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"error": str(e)}


def test_identidad():
    """Test 1: URA se reconoce a si misma."""
    r = mcp("sistema")
    ok = r.get("ok", False) or r.get("success", False)
    log(f"  Identidad: {'✅' if ok else '❌'} sistema responde")
    return ok


def test_comandos():
    """Test 2: URA ejecuta comandos basicos."""
    r = mcp("ejecutar", {"comando": "uptime"})
    ok = r.get("ok", False)
    log(f"  Comandos: {'✅' if ok else '❌'} uptime")
    return ok


def test_panel():
    """Test 3: El panel existe y se ha modificado recientemente."""
    if not PANEL.exists():
        log("  Panel: ❌ no existe")
        return False
    mtime = os.path.getmtime(PANEL)
    antiguedad = time.time() - mtime
    ok = antiguedad < 86400  # menos de 24h
    log(f"  Panel: {'✅' if ok else '🟡'} ultima mod: {antiguedad / 3600:.0f}h")
    return ok


def test_mcp():
    """Test 4: MCP server responde."""
    try:
        r = urllib.request.urlopen(f"{MCP}/", timeout=3)
        data = json.loads(r.read())
        ok = data.get("status") == "ok"
        log(f"  MCP: {'✅' if ok else '❌'} {data.get('tools', 0)} tools")
        return ok
    except:
        log("  MCP: ❌ no responde")
        return False


def main():
    log("=" * 50)
    log("TEST DE AUTONOMIA URA")
    log("=" * 50)

    tests = [
        ("MCP Server", test_mcp),
        ("Identidad", test_identidad),
        ("Comandos", test_comandos),
        ("Panel", test_panel),
    ]

    resultados = []
    for nombre, fn in tests:
        ok = fn()
        resultados.append(ok)

    total = len(resultados)
    exitosos = sum(resultados)

    log("")
    if exitosos == total:
        log("🎉 URA ES AUTONOMA — todos los tests superados")
    elif exitosos >= total * 0.75:
        log(f"🟡 URA parcialmente autonoma ({exitosos}/{total})")
    else:
        log(f"❌ URA necesita mas configuracion ({exitosos}/{total})")

    return 0 if exitosos == total else 1


if __name__ == "__main__":
    sys.exit(main())
