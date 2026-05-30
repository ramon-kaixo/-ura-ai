#!/usr/bin/env python3
"""
Envía una tarea a OpenClaw usando el CLI (único método funcional).
Uso: python3 scripts/enviar_a_openclaw.py "texto de la tarea"
"""

import sys
import subprocess
import os

SESSION_ID = os.getenv("OPENCLAW_SESSION", "ura-default")
TIMEOUT = int(os.getenv("OPENCLAW_TIMEOUT", "120"))


def enviar_tarea(mensaje: str) -> dict:
    try:
        cmd = [
            "openclaw",
            "agent",
            "--agent",
            "main",
            "--session-id",
            SESSION_ID,
            "-m",
            mensaje,
            "--json",
            "--timeout",
            str(TIMEOUT),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT + 10)
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "returncode": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Timeout"}
    except Exception as e:
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print('Uso: python3 enviar_a_openclaw.py "tarea"')
        sys.exit(1)
    tarea = sys.argv[1]
    print(f"Enviando tarea a OpenClaw (session={SESSION_ID}): {tarea[:80]}...")
    resultado = enviar_tarea(tarea)
    if resultado.get("success"):
        print("✅ OpenClaw respondió:")
        print(resultado.get("stdout", ""))
    else:
        print("❌ Error:", resultado.get("error") or resultado.get("stderr"))
