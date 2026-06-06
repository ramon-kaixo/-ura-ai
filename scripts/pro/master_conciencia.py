#!/usr/bin/env python3
"""master_conciencia.py — Prueba todas las acciones de URA y verifica que funcionan.
Ejecuta cada accion real y reporta si tuvo exito o no.
"""

import json
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

MCP_URL = "http://127.0.0.1:9091"
try:
    with open(Path(__file__).resolve().parents[2] / "config" / "dispositivos.json") as f:
        cfg = json.load(f)
    GX10 = cfg.get("dispositivos", {}).get("gx10-64c3", {}).get("ip_cable", "10.164.1.99")
except (FileNotFoundError, json.JSONDecodeError):
    GX10 = "10.164.1.99"
LOG = Path.home() / "URA/ura_ia_1972/logs/master_conciencia.log"
LOG.parent.mkdir(parents=True, exist_ok=True)

TEST_ACTIONS = [
    ("📡 Sistema GX10", {"name": "sistema", "arguments": {}}),
    ("📷 Camaras", {"name": "camaras", "arguments": {}}),
    ("🔊 Subir volumen 75", {"name": "volumen", "arguments": {"nivel": 75}}),
    ("🔊 Bajar volumen 50", {"name": "volumen", "arguments": {"nivel": 50}}),
    ("🔊 Volumen 100", {"name": "volumen", "arguments": {"nivel": 100}}),
    ("🌐 Abrir Safari", {"name": "abrir_app", "arguments": {"nombre": "Safari"}}),
    ("❌ Cerrar Safari", {"name": "cerrar_app", "arguments": {"nombre": "Safari"}}),
    ("💻 Comando uptime", {"name": "ejecutar", "arguments": {"comando": "uptime"}}),
]


def test_api(desc, payload, url=MCP_URL):
    try:
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            f"{url}/mcp/call",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            result = json.loads(r.read())
            ok = result.get("ok", False)
            log = f"{'✅' if ok else '❌'} {desc}"
            if ok:
                log += f" → {str(result.get('resultado', ''))[:80]}"
            else:
                log += f" → {result.get('error', 'sin respuesta')}"
            with open(LOG, "a") as f:
                f.write(f"{datetime.now().isoformat()} - {log}\n")
            return ok
    except Exception as e:
        log = f"❌ {desc} → Error: {e}"
        with open(LOG, "a") as f:
            f.write(f"{datetime.now().isoformat()} - {log}\n")
        return False


def main() -> None:

    # 1. Test conexion MCP
    try:
        r = urllib.request.urlopen(f"{MCP_URL}/", timeout=5)
        json.loads(r.read())
    except Exception:
        sys.exit(1)

    # 2. Ejecutar tests
    resultados = []
    for desc, payload in TEST_ACTIONS:
        ok = test_api(desc, payload)
        resultados.append(ok)
        if "volumen" in desc.lower():
            import time

            time.sleep(0.5)  # Pausa entre cambios de volumen

    # 3. Resumen
    exitosos = sum(resultados)
    total = len(resultados)
    if exitosos == total:
        pass
    else:
        pass

    # 4. Dejar volumen en 50 al final
    test_api("Volumen final 50%", {"accion": "volumen", "args": [50]})

    sys.exit(0 if exitosos == total else 1)


if __name__ == "__main__":
    main()
