#!/usr/bin/env python3
"""master_conciencia.py — Prueba todas las acciones de URA y verifica que funcionan.
Ejecuta cada accion real y reporta si tuvo exito o no."""

import json
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

MCP_URL = "http://127.0.0.1:9091"
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
            print(log)
            with open(LOG, "a") as f:
                f.write(f"{datetime.now().isoformat()} - {log}\n")
            return ok
    except Exception as e:
        log = f"❌ {desc} → Error: {e}"
        print(log)
        with open(LOG, "a") as f:
            f.write(f"{datetime.now().isoformat()} - {log}\n")
        return False


def main():
    print("=" * 60)
    print("  MASTER DE CONCIENCIA — Test de acciones URA")
    print(f"  {datetime.now().isoformat()}")
    print("=" * 60)

    # 1. Test conexion MCP
    print("\n🔌 Verificando MCP Server...")
    try:
        r = urllib.request.urlopen(f"{MCP_URL}/", timeout=5)
        status = json.loads(r.read())
        print(f"  MCP: {status.get('status', 'desconocido')} ({status.get('tools', 0)} tools)")
    except Exception as e:
        print(f"  MCP no disponible: {e}")
        sys.exit(1)

    # 2. Ejecutar tests
    print(f"\n🧪 Ejecutando {len(TEST_ACTIONS)} tests...\n")
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
    print(f"\n{'=' * 60}")
    print(f"  RESULTADO: {exitosos}/{total} acciones exitosas")
    if exitosos == total:
        print("  🎉 TODAS LAS ACCIONES FUNCIONAN")
    else:
        print(f"  ⚠️  {total - exitosos} acciones fallaron")
    print(f"{'=' * 60}")

    # 4. Dejar volumen en 50 al final
    print("\n🔊 Dejando volumen en 50%...")
    test_api("Volumen final 50%", {"accion": "volumen", "args": [50]})

    sys.exit(0 if exitosos == total else 1)


if __name__ == "__main__":
    main()
