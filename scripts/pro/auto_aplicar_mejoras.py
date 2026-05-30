#!/usr/bin/env python3
"""auto_aplicar_mejoras.py — URA aplica automaticamente las mejoras sugeridas a su prompt."""

import json
import os
import subprocess
from datetime import datetime
from pathlib import Path

SUGERENCIAS = Path("/opt/ura/data/sugerencias.json")
GX10_SSH = ["ssh", "ramon@10.164.1.99"]
LOG = Path.home() / "URA/ura_ia_1972/logs/auto_mejoras.log"
LOG.parent.mkdir(parents=True, exist_ok=True)


def log(msg):
    with open(LOG, "a") as f:
        f.write(f"{datetime.now().isoformat()} - {msg}\n")
    print(msg)


def ejecutar_remoto(python_code):
    """Ejecuta codigo Python en el contenedor Open WebUI del GX10 via scp + docker."""
    import tempfile

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(python_code)
        tmp = f.name
    try:
        # SCP al GX10, luego docker cp al contenedor
        subprocess.run(
            ["scp", tmp, "ramon@10.164.1.99:/tmp/ura_script.py"], capture_output=True, timeout=10
        )
        subprocess.run(
            GX10_SSH + ["docker", "cp", "/tmp/ura_script.py", "open-webui:/tmp/"],
            capture_output=True,
            timeout=10,
        )
        r = subprocess.run(
            GX10_SSH + ["docker", "exec", "open-webui", "python3", "/tmp/ura_script.py"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        return r.stdout.strip(), r.stderr.strip()
    finally:
        os.unlink(tmp)


def aplicar_mejoras():
    """Lee sugerencias y actualiza el prompt de URA en Open WebUI."""
    if not SUGERENCIAS.exists():
        log("No hay sugerencias para aplicar")
        return False

    with open(SUGERENCIAS) as f:
        sugs = json.load(f)

    # Filtrar solo sugerencias de meta_mejora no aplicadas
    pendientes = [
        s
        for s in sugs
        if s.get("dominio") in ("meta_mejora", "reflexion") and not s.get("aplicada", False)
    ]

    if not pendientes:
        log("No hay sugerencias pendientes de aplicar")
        return False

    log(f"Hay {len(pendientes)} sugerencias pendientes")

    # Leer prompt actual via archivo
    code_leer = """
import sqlite3, json
conn = sqlite3.connect('/app/backend/data/webui.db')
row = conn.execute("SELECT params FROM model WHERE id='ura'").fetchone()
if row:
    params = json.loads(row[0])
    with open('/tmp/ura_prompt_actual.txt', 'w') as f:
        f.write(params.get('system', ''))
    print('OK')
else:
    print('ERROR: modelo no encontrado')
conn.close()
"""
    with open("/tmp/ura_read_prompt.py", "w") as f:
        f.write(code_leer)
    subprocess.run(
        ["scp", "/tmp/ura_read_prompt.py", "ramon@10.164.1.99:/tmp/ura_read.py"],
        capture_output=True,
        timeout=10,
    )
    os.unlink("/tmp/ura_read_prompt.py")

    subprocess.run(
        GX10_SSH + ["docker", "cp", "/tmp/ura_read.py", "open-webui:/tmp/"],
        capture_output=True,
        timeout=10,
    )
    r = subprocess.run(
        GX10_SSH + ["docker", "exec", "open-webui", "python3", "/tmp/ura_read.py"],
        capture_output=True,
        text=True,
        timeout=15,
    )
    r2 = subprocess.run(
        GX10_SSH
        + ["docker", "cp", "open-webui:/tmp/ura_prompt_actual.txt", "/tmp/ura_prompt_actual.txt"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    subprocess.run(
        ["scp", "ramon@10.164.1.99:/tmp/ura_prompt_actual.txt", "/tmp/ura_prompt_actual.txt"],
        capture_output=True,
        timeout=10,
    )

    try:
        with open("/tmp/ura_prompt_actual.txt") as f:
            prompt_actual = f.read()
    except Exception as e:
        log(f"Error leyendo prompt remoto: {e}")
        return False

    mejoras = 0
    for s in pendientes:
        s.get("problema", "")
        solucion = s.get("solucion", "")
        if solucion and solucion not in prompt_actual:
            prompt_actual += f"\n# Mejora auto: {solucion}"
            s["aplicada"] = True
            s["aplicada_en"] = datetime.now().isoformat()
            mejoras += 1
            log(f"✅ Aplicada: {solucion[:80]}")

    if mejoras == 0:
        log("Las sugerencias ya estaban aplicadas o no se pudieron integrar")
        return False

    # Guardar prompt en archivo temporal y enviarlo
    prompt_path = "/tmp/ura_prompt_actualizado.txt"
    with open(prompt_path, "w") as f:
        f.write(prompt_actual)

    subprocess.run(
        ["scp", prompt_path, "ramon@10.164.1.99:/tmp/ura_prompt.txt"],
        capture_output=True,
        timeout=10,
    )
    os.unlink(prompt_path)

    # Copiar prompt al contenedor PRIMERO
    subprocess.run(
        GX10_SSH + ["docker", "cp", "/tmp/ura_prompt.txt", "open-webui:/tmp/"],
        capture_output=True,
        timeout=10,
    )

    # Luego ejecutar script de actualizacion
    code = """
import sqlite3, json
with open('/tmp/ura_prompt.txt') as f:
    nuevo_prompt = f.read()
conn = sqlite3.connect('/app/backend/data/webui.db')
params = json.loads(conn.execute("SELECT params FROM model WHERE id='ura'").fetchone()[0])
params['system'] = nuevo_prompt
conn.execute("UPDATE model SET params=? WHERE id='ura'", (json.dumps(params),))
conn.commit()
conn.close()
print('OK')
"""
    tmp = "/tmp/ura_update_prompt.py"
    with open(tmp, "w") as f:
        f.write(code)
    subprocess.run(
        ["scp", tmp, "ramon@10.164.1.99:/tmp/ura_update.py"], capture_output=True, timeout=10
    )
    os.unlink(tmp)

    r = subprocess.run(
        GX10_SSH + ["docker", "cp", "/tmp/ura_update.py", "open-webui:/tmp/"],
        capture_output=True,
        timeout=10,
    )
    r = subprocess.run(
        GX10_SSH + ["docker", "exec", "open-webui", "python3", "/tmp/ura_update.py"],
        capture_output=True,
        text=True,
        timeout=15,
    )

    out = r.stdout.strip()
    err = r.stderr.strip()

    if "OK" in out or not err:
        log(f"✅ Prompt actualizado con {mejoras} mejoras")
        with open(SUGERENCIAS, "w") as f:
            json.dump(sugs, f, indent=2)
        subprocess.run(GX10_SSH + ["docker", "restart", "open-webui"], timeout=30)
        log("Open WebUI reiniciado")
        return True
    else:
        log(f"Error: {err}")
        return False


if __name__ == "__main__":
    aplicar_mejoras()
