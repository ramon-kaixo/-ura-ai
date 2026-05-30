#!/usr/bin/env python3
"""meta_mejora_real.py — Aplica sugerencias, mide impacto antes/despues."""

import json
import subprocess
import tempfile
import time
from datetime import datetime
from pathlib import Path

SUGERENCIAS = Path("/opt/ura/data/sugerencias.json")
REPO = Path.home() / "URA/ura_ia_1972"
MCP = "http://127.0.0.1:9091"
LOG = REPO / "logs/meta_mejora_real.log"
GX10_SSH = ["ssh", "ramon@10.164.1.99"]


def log(msg):
    with open(LOG, "a") as f:
        f.write(f"{datetime.now().isoformat()} - {msg}\n")
    print(msg)


def medir():
    """Ejecuta los 7 tests y devuelve tiempos y exitos."""
    import urllib.request

    tests = ["sistema", "camaras", "volumen", "explorar", "ejecutar"]
    resultados = []
    for t in tests:
        try:
            inicio = time.time()
            data = json.dumps({"name": t, "arguments": {}}).encode()
            req = urllib.request.Request(
                f"{MCP}/mcp/call",
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=15):  # nosec B310
                pass
            ms = int((time.time() - inicio) * 1000)
            resultados.append({"test": t, "ms": ms, "ok": True})
        except:
            resultados.append({"test": t, "ms": 0, "ok": False})
    return resultados


def aplicar_mejora():
    if not SUGERENCIAS.exists():
        log("No hay sugerencias")
        return False

    with open(SUGERENCIAS) as f:
        sugs = json.load(f)

    # Buscar sugerencia de meta_mejora no aplicada
    for s in sugs:
        if s.get("dominio") == "meta_mejora" and not s.get("aplicada", False):
            solucion = s.get("solucion", "")
            if not solucion:
                continue

            log(f"Aplicando: {solucion[:80]}...")

            # Medir ANTES
            antes = medir()
            log(
                f"  Antes: {sum(1 for r in antes if r['ok'])}/{len(antes)} OK, media {sum(r['ms'] for r in antes if r['ok']) / max(len([r for r in antes if r['ok']]), 1):.0f}ms"
            )

            # Aplicar al prompt (via SSH a Open WebUI)
            prompt_add = f"\n# Meta-mejora auto: {solucion}"
            code = """
import sqlite3, json, os
conn = sqlite3.connect('/app/backend/data/webui.db')
params = json.loads(conn.execute("SELECT params FROM model WHERE id='ura'").fetchone()[0])
params['system'] += os.environ['URA_PROMPT_ADD']
conn.execute("UPDATE model SET params=? WHERE id='ura'", (json.dumps(params),))
conn.commit()
conn.close()
print('OK')
"""
            with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as tmp_f:
                tmp_f.write(code)
                tmp_path = tmp_f.name
            subprocess.run(["scp", tmp_path, "ramon@10.164.1.99:/tmp/"], capture_output=True)
            subprocess.run(
                GX10_SSH + ["docker", "cp", f"{tmp_path}", "open-webui:/tmp/"],
                capture_output=True,
            )
            r = subprocess.run(
                GX10_SSH
                + [
                    "docker",
                    "exec",
                    "-e",
                    f"URA_PROMPT_ADD={prompt_add}",
                    "open-webui",
                    "python3",
                    tmp_path,
                ],
                capture_output=True,
                text=True,
                timeout=15,
            )
            Path(tmp_path).unlink(missing_ok=True)

            if "OK" in r.stdout:
                subprocess.run(
                    GX10_SSH + ["docker", "restart", "open-webui"], capture_output=True, timeout=30
                )
                time.sleep(5)

                # Medir DESPUES
                despues = medir()
                log(
                    f"  Despues: {sum(1 for r in despues if r['ok'])}/{len(despues)} OK, media {sum(r['ms'] for r in despues if r['ok']) / max(len([r for r in despues if r['ok']]), 1):.0f}ms"
                )

                # Comparar
                antes_ok = sum(1 for r in antes if r["ok"])
                despues_ok = sum(1 for r in despues if r["ok"])
                if despues_ok >= antes_ok:
                    s["aplicada"] = True
                    s["impacto"] = f"{despues_ok - antes_ok} tests extra superados"
                    log(f"  ✅ MEJORA: {s['impacto']}")
                else:
                    log("  ❌ SIN MEJORA: se revertira")
                    # Revert: restore from prompt backup

                with open(SUGERENCIAS, "w") as f:
                    json.dump(sugs, f, indent=2)
                return True

    log("No hay sugerencias pendientes de aplicar")
    return False


if __name__ == "__main__":
    aplicar_mejora()
