#!/usr/bin/env python3
"""ura_self_modify.py — Permite a URA modificar su propio prompt y tools.
Ejecuta contra la BD de Open WebUI en el GX10.
"""

import subprocess
import sys

GX10 = "ramon@10.164.1.99"
DB_PATH = "/app/backend/data/webui.db"


def ejecutar_remoto(python_code, env=None):
    """Ejecuta codigo Python en el contenedor Open WebUI del GX10."""
    import tempfile
    from pathlib import Path

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(python_code)
        tmp = f.name
    env_args = []
    if env:
        for k, v in env.items():
            env_args.extend(["-e", f"{k}={v}"])
    subprocess.run(["scp", tmp, f"ramon@{GX10.rsplit('@', maxsplit=1)[-1]}:/tmp/"], capture_output=True)
    r = subprocess.run(
        ["ssh", GX10, "docker", "exec", *env_args, "open-webui", "python3", tmp],
        capture_output=True,
        text=True,
        timeout=15,
    )
    Path(tmp).unlink(missing_ok=True)
    return r.stdout, r.stderr


def leer_prompt():
    """Lee el system prompt actual de URA."""
    code = """
import sqlite3, json
conn = sqlite3.connect('/app/backend/data/webui.db')
row = conn.execute("SELECT params FROM model WHERE id='ura'").fetchone()
if row:
    params = json.loads(row[0])
    print(params.get('system', ''))
conn.close()
"""
    out, err = ejecutar_remoto(code)
    return out.strip() or err.strip()


def actualizar_prompt(nuevo_prompt):
    """Actualiza el system prompt de URA en Open WebUI."""
    code = """
import sqlite3, json, os
conn = sqlite3.connect('/app/backend/data/webui.db')
row = conn.execute("SELECT params FROM model WHERE id='ura'").fetchone()
if row:
    params = json.loads(row[0])
    params['system'] = os.environ['URA_NEW_PROMPT']
    params['temperature'] = 0.7
    conn.execute("UPDATE model SET params=?, meta=? WHERE id='ura'",
                 (json.dumps(params), json.dumps(params)))
    conn.commit()
    print('OK: prompt actualizado')
else:
    print('ERROR: modelo URA no encontrado')
conn.close()
"""
    out, err = ejecutar_remoto(code, env={"URA_NEW_PROMPT": nuevo_prompt})
    return out.strip() or err.strip()


def listar_tools():
    """Lista las tools disponibles para URA."""
    code = """
import sqlite3
conn = sqlite3.connect('/app/backend/data/webui.db')
rows = conn.execute("SELECT id, name FROM tool").fetchall()
for r in rows:
    print(f"{r[0]}: {r[1]}")
conn.close()
"""
    out, err = ejecutar_remoto(code)
    return out.strip() or err.strip()


def crear_tool(nombre, descripcion, codigo):
    """Crea una new tool en Open WebUI."""
    import json as _json
    import time

    tool_id = nombre.lower().replace(" ", "_")
    now = int(time.time())
    specs = _json.dumps(
        [
            {
                "name": "ejecutar",
                "description": descripcion,
                "parameters": {"type": "object", "properties": {}},
            },
        ],
    )
    meta = _json.dumps({"description": descripcion})
    code = """
import sqlite3, json, os
conn = sqlite3.connect('/app/backend/data/webui.db')
conn.execute("INSERT OR REPLACE INTO tool (id, user_id, name, content, specs, meta, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
    (os.environ['URA_TOOL_ID'], 'admin', json.loads(os.environ['URA_TOOL_NAME']), json.loads(os.environ['URA_TOOL_CODE']),
     os.environ['URA_TOOL_SPECS'], os.environ['URA_TOOL_META'], int(os.environ['URA_TOOL_NOW']), int(os.environ['URA_TOOL_NOW']))
conn.commit()
print('OK: tool creada')
conn.close()
"""
    out, err = ejecutar_remoto(code, env={
        "URA_TOOL_ID": tool_id,
        "URA_TOOL_NAME": _json.dumps(nombre),
        "URA_TOOL_CODE": _json.dumps(codigo),
        "URA_TOOL_SPECS": specs,
        "URA_TOOL_META": meta,
        "URA_TOOL_NOW": str(now),
    })
    return out.strip() or err.strip()


def reiniciar():
    """Reinicia Open WebUI para aplicar cambios."""
    r = subprocess.run(
        ["ssh", GX10, "docker restart open-webui"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    return r.stdout.strip()


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd in {"leer_prompt", "actualizar_prompt"} or cmd in {"listar_tools", "crear_tool"} or cmd == "reiniciar":
            pass
        else:
            pass
    else:
        pass
