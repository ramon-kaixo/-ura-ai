#!/usr/bin/env python3
"""auto_conciencia.py — URA se auto-evalua y autocorrige usando OpenClaw."""

import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

MCP_URL = "http://127.0.0.1:9091"
LOG = Path.home() / "URA/ura_ia_1972/logs/auto_conciencia.log"
SUGERENCIAS = Path("/opt/ura/data/sugerencias.json")
NOTIFICAR = Path("/opt/ura/scripts/notificar.sh")
LOG.parent.mkdir(parents=True, exist_ok=True)


def mcp(nombre, args=None):
    """Llama al MCP server y devuelve resultado."""
    import urllib.request

    payload = json.dumps({"name": nombre, "arguments": args or {}}).encode()
    inicio = time.time()
    try:
        req = urllib.request.Request(
            f"{MCP_URL}/mcp/call",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            result = json.loads(r.read())
        ms = int((time.time() - inicio) * 1000)
        return ms, result
    except Exception as e:
        ms = int((time.time() - inicio) * 1000)
        return ms, {"ok": False, "error": str(e)}


def log(msg) -> None:
    with open(LOG, "a") as f:
        f.write(f"{datetime.now().isoformat()} - {msg}\n")


def sugerir(problema, solucion) -> None:
    sugs = []
    if SUGERENCIAS.exists():
        with open(SUGERENCIAS) as f:
            sugs = json.load(f)
    sugs.append(
        {
            "timestamp": time.time(),
            "dominio": "auto_conciencia",
            "problema": problema,
            "solucion": solucion,
        },
    )
    with open(SUGERENCIAS, "w") as f:
        json.dump(sugs, f, indent=2)


def notificar(msg) -> None:
    if NOTIFICAR.exists():
        subprocess.run([str(NOTIFICAR), msg])


def test(nombre, accion, args=None):
    ms, r = mcp(accion, args)
    ok = r.get("ok", False) or r.get("success", False)
    ms_str = f"{ms:4d}ms"
    if ok:
        log(f"  [{ms_str}] ✅ {nombre}")
    else:
        log(f"  [{ms_str}] ❌ {nombre}: {r.get('error', 'sin respuesta')}")
    return ok, r


def main() -> int:
    log("=" * 50)
    log("AUTO-CONCIENCIA URA")
    log("=" * 50)

    resultados = []

    # 1. Sistema
    ok, r = test("Estado GX10", "sistema")
    resultados.append(("sistema", ok))

    # 2. Camaras
    ok, r = test("Camaras", "camaras")
    resultados.append(("camaras", ok))

    # 3. Volumen
    ok, r = test("Volumen", "volumen", {"nivel": 50})
    resultados.append(("volumen", ok))

    # 4. Leer archivo via comando
    ok, r = test("Ejecutar comando", "ejecutar", {"comando": "uptime"})
    resultados.append(("comandos", ok))

    # 5. Abrir app
    ok, r = test("Abrir app", "abrir_app", {"nombre": "Safari"})

    # 6. Explorar sistema
    ok, r = test("Explorar sistema", "explorar")
    resultados.append(("explorar", ok))

    # 7. Raton
    ok, r = test("Raton", "raton", {"accion": "posicion"})
    resultados.append(("raton", ok))
    resultados.append(("abrir_app", ok))

    # 6. Explorar sistema
    ok, r = test("Explorar sistema", "explorar")
    resultados.append(("explorar", ok))

    # 7. Raton
    ok, _r = test("Raton", "raton", {"accion": "posicion"})
    resultados.append(("raton", ok))
    if ok:
        time.sleep(1)
        mcp("cerrar_app", {"nombre": "Safari"})

    # Resumen
    exitosos = sum(1 for _, ok in resultados if ok)
    total = len(resultados)

    log("")
    log(f"Resultado: {exitosos}/{total} pruebas superadas")

    if exitosos < total:
        fallos = [n for n, ok in resultados if not ok]
        log(f"Fallos: {', '.join(fallos)}")
        sugerir(f"Auto-conciencia: {total - exitosos} fallos", f"Revisar: {', '.join(fallos)}")
        if exitosos == 0:
            notificar("⚠️ URA: 0 acciones funcionales, revisar MCP")
        return 1

    log("🎉 Todas las capacidades operativas")
    return 0


if __name__ == "__main__":
    sys.exit(main())
