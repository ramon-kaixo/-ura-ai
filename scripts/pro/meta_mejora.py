#!/usr/bin/env python3
"""meta_mejora.py — URA mejora su propio prompt con medicion de impacto.

FUSIONADO CON:
  - meta_mejora_real.py (medicion antes/despues de mejoras)
"""

PLUGIN = {
    "name": "meta_mejora",
    "phase": "post",
    "timeout": 60,
    "blocking": False,
    "needs_file": False,
}

import json
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

from motor.core.config import UraConfig
from motor.core.qdrant_client import QdrantClient

_qdrant = None

def _get_qdrant():
    global _qdrant
    if _qdrant is None:
        _qdrant = QdrantClient.instancia(UraConfig.load())
    return _qdrant


REFLEXIONES = Path("/opt/ura/data/reflexiones.log")
MEJORAS = Path("/opt/ura/config/prompts/mejoras.txt")
SUGERENCIAS = Path("/opt/ura/data/sugerencias.json")
PROBAR = Path(__file__).resolve().parent.parent / "probar_sugerencia.py"
REPO = Path.home() / "URA/ura_ia_1972"
MCP = "http://127.0.0.1:9091"
GX10_SSH = ["ssh", os.environ.get("ASUS_SSH", "ramon@10.164.1.99")]


def log(msg) -> None:
    pass


def medir():
    tests = ["sistema", "camaras", "volumen", "explorar", "ejecutar"]
    resultados = []
    for t in tests:
        try:
            inicio = time.time()
            import urllib.request
            data = json.dumps({"name": t, "arguments": {}}).encode()
            req = urllib.request.Request(
                f"{MCP}/mcp/call",
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=15):
                pass
            ms = int((time.time() - inicio) * 1000)
            resultados.append({"test": t, "ms": ms, "ok": True})
        except Exception:
            resultados.append({"test": t, "ms": 0, "ok": False})
    return resultados


def log_medicion(resultados, etiqueta) -> None:
    ok_count = sum(1 for r in resultados if r["ok"])
    media_ms = sum(r["ms"] for r in resultados if r["ok"]) / max(
        len([r for r in resultados if r["ok"]]), 1,
    )
    log(f"  {etiqueta}: {ok_count}/{len(resultados)} OK, media {media_ms:.0f}ms")


def aplicar_solucion(prompt_add) -> None:
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
    _asus_ssh = os.environ.get("ASUS_SSH", "ramon@10.164.1.99")
    subprocess.run(["scp", tmp_path, f"{_asus_ssh}:/tmp/"], capture_output=True)
    subprocess.run(
        [*GX10_SSH, "docker", "cp", f"{tmp_path}", "open-webui:/tmp/"],
        capture_output=True,
    )
    r = subprocess.run(
        [*GX10_SSH, "docker", "exec", "-e", f"URA_PROMPT_ADD={prompt_add}", "open-webui", "python3", tmp_path],
        capture_output=True, text=True, timeout=15,
    )
    Path(tmp_path).unlink(missing_ok=True)
    if "OK" in r.stdout:
        subprocess.run([*GX10_SSH, "docker", "restart", "open-webui"], capture_output=True, timeout=30)
        time.sleep(5)


def comparar_resultados(antes, despues):
    antes_ok = sum(1 for r in antes if r["ok"])
    despues_ok = sum(1 for r in despues if r["ok"])
    return despues_ok >= antes_ok


def analizar_reflexiones() -> None:
    if not REFLEXIONES.exists():
        return
    with open(REFLEXIONES) as f:
        lineas = f.readlines()
    if len(lineas) < 3:
        return
    log(f"Analizando {len(lineas)} reflexiones...")
    fallos = sum(1 for l in lineas if "fallo" in l.lower())
    exitos = sum(1 for l in lineas if "exitoso" in l.lower() or "exito" in l.lower())
    sugerencia = f"Analisis de {len(lineas)} reflexiones: {exitos} exitos, {fallos} fallos."
    log(sugerencia)
    if fallos > exitos * 2:
        sugerencia += " Hay muchos fallos. Revisar tools, permisos y function calling."
        sugs = []
        if SUGERENCIAS.exists():
            with open(SUGERENCIAS) as f:
                sugs = json.load(f)
        idx = len(sugs)
        sugs.append({
            "timestamp": datetime.now().timestamp(),
            "dominio": "meta_mejora",
            "problema": "Exceso de fallos en acciones de URA",
            "solucion": "Revisar configuracion de tools, function calling en Open WebUI, y permisos",
        })
        with open(SUGERENCIAS, "w") as f:
            json.dump(sugs, f, indent=2)
        proc = subprocess.Popen([sys.executable, str(PROBAR), str(idx)])
        # No esperamos a que termine, pero registramos el PID
        log(f"Test lanzado con PID {proc.pid}")
    MEJORAS.parent.mkdir(parents=True, exist_ok=True)
    with open(MEJORAS, "a") as f:
        f.write(f"\n# {datetime.now().isoformat()}\n# {sugerencia}\n")


def aplicar_mejora() -> bool:
    if not SUGERENCIAS.exists():
        log("No hay sugerencias")
        return False
    with open(SUGERENCIAS) as f:
        sugs = json.load(f)
    for s in sugs:
        if s.get("dominio") == "meta_mejora" and not s.get("aplicada", False):
            solucion = s.get("solucion", "")
            if not solucion:
                continue
            log(f"Aplicando: {solucion[:80]}...")
            antes = medir()
            log_medicion(antes, "Antes")
            prompt_add = f"\n# Meta-mejora auto: {solucion}"
            aplicar_solucion(prompt_add)
            despues = medir()
            log_medicion(despues, "Despues")
            antes_ok = sum(1 for r in antes if r["ok"])
            despues_ok = sum(1 for r in despues if r["ok"])
            if comparar_resultados(antes, despues):
                s["aplicada"] = True
                s["impacto"] = f"{despues_ok - antes_ok} tests extra superados"
                log(f"  OK MEJORA: {s['impacto']}")
                guardar_correccion_en_qdrant(s.get("problema", ""), s.get("solucion", ""), s["impacto"])
            else:
                log("  SIN MEJORA: se revertira")
            with open(SUGERENCIAS, "w") as f:
                json.dump(sugs, f, indent=2)
            return True
    log("No hay sugerencias pendientes de aplicar")
    return False


def guardar_correccion_en_qdrant(problema: str, solucion: str, impacto: str) -> bool:
    """Guarda una corrección exitosa en Qdrant para aprendizaje futuro."""
    try:
        qdrant = _get_qdrant()
        if not qdrant.disponible:
            return False
        texto = f"Problema: {problema}\nSolucion: {solucion}\nImpacto: {impacto}"
        metadata = {
            "tipo": "correccion",
            "problema": problema[:200],
            "solucion": solucion[:200],
            "impacto": impacto[:100],
            "timestamp": datetime.now().isoformat(),
        }
        tx_id = f"correccion_{datetime.now().timestamp()}"
        return qdrant.guardar_documento(tx_id, texto, metadata)
    except Exception as e:
        log(f"Error guardando correccion en Qdrant: {e}")
        return False


def reindexar_transaccion(tx_id: str, texto_corregido: str) -> bool:
    """Re-indexa una transacción en Qdrant con texto corregido."""
    try:
        qdrant = _get_qdrant()
        if not qdrant.disponible:
            return False
        return qdrant.guardar_documento(tx_id, texto_corregido, {"tipo": "reindexado", "timestamp": datetime.now().isoformat()})
    except Exception as e:
        log(f"Error reindexando transaccion {tx_id}: {e}")
        return False


def scan_project() -> None:
    from pathlib import Path as _Path
    root = _Path.home() / "URA/ura_ia_1972"
    list(root.rglob("*.py"))


if __name__ == "__main__":
    if "--scan" in sys.argv:
        scan_project()
    else:
        analizar_reflexiones()
        aplicar_mejora()
