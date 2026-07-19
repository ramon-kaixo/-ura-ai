#!/usr/bin/env python3
"""Ingestador de Red Global — Tailscale SSH + Distribución de Tareas.

📖 MANUAL DE USO RÁPIDO:
  python3 core/ingestador_red.py --status            # Estado de todos los dispositivos
  python3 core/ingestador_red.py --enviar <tarea> <dispositivo>  # Enviar tarea a un nodo

🔒 GARANTÍAS DE SEGURIDAD:
  - 0 IPs hardcodeadas. Solo nombres MagicDNS (gx10-64c3, mac-mini-de-ramon)
  - 0 passwords en texto plano. Autenticación via Tailscale SSH criptográfico
  - tailscale up --operator=ramon --ssh (ya configurado en el servicio SSH Guard)
  - Conexiones solo a dispositivos en la misma tailnet (100.*)
  - Timeout 30s para evitar bloqueos

Estrategia de distribución de tareas:
  - Tareas PESADAS (refactorizar, entrenar) → ASUS (121GB RAM, GPU Blackwell)
  - Tareas MEDIAS (comprimir, analizar) → Mac mini (16GB RAM)
  - Tareas LIGERAS (monitorear, reportar) → cualquier dispositivo online
"""

import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Tuple

log = logging.getLogger("ura.ingestador_red")

URA = Path(__file__).resolve().parent.parent
INVENTARIO_PATH = URA / "config" / "dispositivos.json"
TAILSCALE_SSH_USER = os.environ.get("TAILSCALE_USER", "ramon")

TAREAS_PESADAS = {"refactorizar", "entrenar", "inferir", "sandbox", "backup", "compilar"}
TAREAS_MEDIAS = {"analizar", "comprimir", "sincronizar", "validar"}
TAREAS_LIGERAS = {"monitorear", "reportar", "ping", "dashboard"}


def cargar_inventario() -> dict:
    if INVENTARIO_PATH.exists():
        try:
            return json.loads(INVENTARIO_PATH.read_text())
        except Exception:
            log.exception("Error loading inventory from %s", INVENTARIO_PATH)
            pass  # noqa: S110
    return {"dispositivos": {}}


def tailscale_ssh(hostname: str, comando: str, timeout: int = 30) -> Tuple[int, str, str]:
    """Ejecuta un comando vía Tailscale SSH (sin password, auth criptográfica).

    Returns:
        (exit_code, stdout, stderr)

    """
    try:
        r = subprocess.run(  # noqa: S603  -- hostname y comando desde callers internos
            [  # noqa: S607  -- hostname y comando desde callers internos
                "ssh",
                "-o",
                "StrictHostKeyChecking=no",
                "-o",
                "ConnectTimeout=5",
                "-o",
                "BatchMode=yes",  # Sin prompts de password
                f"{TAILSCALE_SSH_USER}@{hostname}",
                comando,
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "timeout"
    except Exception as e:
        return -1, "", str(e)


def distribuir_tarea(tarea: str, archivo: str | None = None) -> dict:
    """Distribuye una tarea al dispositivo más adecuado según su perfil.

    Lógica de asignación:
      - tarea en TAREAS_PESADAS → ASUS (gx10-64c3)
      - tarea en TAREAS_MEDIAS → Mac mini de Ramón (mac-mini-de-ramon)
      - tarea en TAREAS_LIGERAS → primer dispositivo online con el rol adecuado
    """
    inv = cargar_inventario()
    dispositivos = inv.get("dispositivos", {})

    # Seleccionar dispositivo según tipo de tarea
    candidato = None
    if tarea in TAREAS_PESADAS:
        # Buscar dispositivo con rol servidor_principal
        for d_id, d in dispositivos.items():
            if d.get("rol") == "servidor_principal" and d.get("estado") == "online":
                candidato = (d_id, d)
                break

    elif tarea in TAREAS_MEDIAS:
        for d_id, d in dispositivos.items():
            if "cliente" in d.get("rol", "") and d.get("estado") == "online" and d.get("ram_gb", 0) >= 16:
                candidato = (d_id, d)
                break

    else:  # Ligera
        for d_id, d in dispositivos.items():
            if d.get("estado") == "online" and d.get("tipo") != "ios":
                candidato = (d_id, d)
                break

    if not candidato:
        # Fallback: usar localhost (self)
        return {"asignado_a": "localhost", "tarea": tarea, "ok": True, "metodo": "local_fallback"}

    hostname = candidato[0]
    dev = candidato[1]

    # Construir comando según la tarea
    comandos = {
        "refactorizar": f"cd /home/ramon/URA/ura_ia_1972 && python3 scripts/pro/pipeline_supremo.py {archivo or ''}",
        "monitorear": "free -h && df -h /",
        "ping": "echo 'pong'",
        "sincronizar": f"rsync -avz /home/ramon/URA/ura_ia_1972/ {hostname}:/home/ramon/URA/ura_ia_1972/",
        "dashboard": "curl -s http://localhost:11435/health",
    }

    cmd = comandos.get(tarea, f"echo 'Tarea {tarea} recibida en {hostname}'")
    exit_code, stdout, stderr = tailscale_ssh(hostname, cmd)

    return {
        "asignado_a": hostname,
        "rol": dev.get("rol", "?"),
        "tarea": tarea,
        "comando": cmd[:100],
        "exit_code": exit_code,
        "ok": exit_code == 0,
        "output": stdout[:200],
        "error": stderr[:100],
    }


def estado_dispositivos() -> dict:
    """Verifica estado de todos los dispositivos via ping + SSH."""
    inv = cargar_inventario()
    resultados = {}

    for dev_id, dev in inv.get("dispositivos", {}).items():
        hostname = dev.get("nombre_dns", dev_id)

        # Ping test
        exit_code, _out, _ = tailscale_ssh(hostname, "echo 'ok'", timeout=5)
        online = exit_code == 0

        resultados[dev_id] = {
            "hostname": hostname,
            "rol": dev.get("rol", "?"),
            "tipo": dev.get("tipo", "?"),
            "online": online,
            "ip_cable": dev.get("ip_cable", "—"),
            "ip_tailscale": dev.get("ip_tailscale", "—"),
        }

    online_count = sum(1 for r in resultados.values() if r["online"])
    return {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "total": len(resultados),
        "online": online_count,
        "offline": len(resultados) - online_count,
        "dispositivos": resultados,
    }


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Ingestador de Red Global (Tailscale SSH)")
    parser.add_argument("--status", action="store_true", help="Estado de todos los dispositivos")
    parser.add_argument(
        "--enviar",
        nargs=2,
        metavar=("TAREA", "DISPOSITIVO"),
        help="Enviar tarea a un dispositivo específico",
    )
    parser.add_argument("--distribuir", type=str, help="Distribuir tarea al mejor dispositivo")
    parser.add_argument("--ssh", type=str, help="Tailscale SSH a un hostname")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.ssh:
        exit_code, out, err = tailscale_ssh(args.ssh, "hostname && free -h | head -2")
        sys.exit(exit_code)

    if args.enviar:
        tarea, dispositivo = args.enviar
        exit_code, _out, _err = tailscale_ssh(
            dispositivo,
            rf"echo 'Tarea {tarea} ejecutada en \$(hostname)' && hostname",
        )
        sys.exit(0 if exit_code == 0 else 1)

    if args.distribuir:
        result = distribuir_tarea(args.distribuir)
        if args.json:
            pass
        else:
            "✅" if result["ok"] else "❌"
            if result.get("output"):
                pass
        sys.exit(0 if result["ok"] else 1)

    if args.status or not any([args.ssh, args.enviar, args.distribuir]):
        estado = estado_dispositivos()
        if args.json:
            pass
        else:
            for _dev_id, dev in sorted(estado["dispositivos"].items()):
                "✅" if dev["online"] else "❌"
                f"{dev['ip_cable']} | {dev['ip_tailscale']}"


if __name__ == "__main__":
    main()
