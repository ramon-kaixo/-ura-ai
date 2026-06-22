from datetime import UTC

#!/usr/bin/env python3
"""plan_validator.py — Inyección de contexto real del sistema en el debate.

Recolecta:
  - Estado de servicios (systemd)
  - VRAM disponible (nvidia-smi)
  - Último health check de mochila
  - Estado de Alemania (si existe)
  - Circuit breaker states

Uso:
  python3 plan_validator.py                      # imprime JSON con contexto
  echo '{"plan": "..."}' | python3 plan_validator.py --debate  # contexto + debate
"""
import json
import logging
import os
import subprocess
import sys

logger = logging.getLogger("ura.debate.validator")

SERVICES = [
    "ura-mochila.service",
    "ura-heartbeat.service",
    "ollama.service",
    "ura-llama-server.service",
]

STATE_FILES = {
    "hetzner": "/tmp/ura_hetzner_state.json",
    "snc": "/tmp/ura_snc_state.json",
}


def get_service_status(service: str) -> dict:
    try:
        res = subprocess.run(
            ["systemctl", "is-active", service],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        pid = subprocess.run(
            ["systemctl", "show", service, "-p", "MainPID"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        pid_str = pid.stdout.strip().replace("MainPID=", "")
        return {
            "name": service,
            "active": res.stdout.strip(),
            "pid": int(pid_str) if pid_str.isdigit() else None,
        }
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        return {"name": service, "active": "unknown", "error": str(e)}


def get_vram() -> dict | None:
    try:
        res = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.total,memory.used,memory.free", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if res.returncode != 0:
            return None
        parts = res.stdout.strip().split(", ")
        if len(parts) >= 3:
            return {
                "total_mb": int(parts[0]),
                "used_mb": int(parts[1]),
                "free_mb": int(parts[2]),
                "used_pct": round(int(parts[1]) / int(parts[0]) * 100, 1) if int(parts[0]) > 0 else 0,
            }
    except (subprocess.TimeoutExpired, FileNotFoundError, ValueError, IndexError):
        return None
    return None


def load_state_file(path: str) -> dict | None:
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def collect_context() -> dict:
    services = [get_service_status(s) for s in SERVICES]
    vram = get_vram()
    hetzner = load_state_file(STATE_FILES["hetzner"])
    snc = load_state_file(STATE_FILES["snc"])

    context = {
        "services": services,
        "vram": vram or {"error": "nvidia-smi no disponible"},
    }
    if hetzner:
        context["hetzner"] = hetzner
    if snc:
        context["snc_mode"] = snc.get("mode", "NORMAL")

    return context


def format_context_for_prompt(context: dict) -> str:
    parts = []
    parts.append("=== SERVICIOS ===")
    for svc in context.get("services", []):
        pid = f" (PID {svc['pid']})" if svc.get("pid") else ""
        parts.append(f"  {svc['name']}: {svc['active']}{pid}")

    vram = context.get("vram")
    if vram and "error" not in vram:
        parts.append("\n=== VRAM ===")
        parts.append(f"  Total: {vram['total_mb']} MB")
        parts.append(f"  Usado: {vram['used_mb']} MB ({vram['used_pct']}%)")
        parts.append(f"  Libre: {vram['free_mb']} MB")
    else:
        parts.append("\n=== VRAM ===")
        parts.append(f"  {vram.get('error', 'No data')}")

    hetzner = context.get("hetzner")
    if hetzner:
        parts.append("\n=== ALEMANIA (Hetzner) ===")
        parts.append(f"  {json.dumps(hetzner, indent=2)}")

    snc = context.get("snc_mode")
    if snc:
        parts.append(f"\n=== MODO SNC: {snc} ===")

    parts.append(f"\n  Timestamp: {__import__('datetime').datetime.now(UTC).isoformat()}")
    return "\n".join(parts)


def main():
    context = collect_context()

    if len(sys.argv) > 1 and sys.argv[1] == "--debate":
        data = json.loads(sys.stdin.read())
        data["context"] = context
        import asyncio

        from core.debate.debate_engine import run_debate
        from core.debate.lockfile import DebateLock

        async def _run():
            with DebateLock():
                return await run_debate(data.get("plan", ""), context)

        result = asyncio.run(_run())
        log.info(json.dumps(result, ensure_ascii=False, indent=2))
        verdict = result.get("verdict", "")
        if verdict == "CONSENSUS":
            sys.exit(0)
        elif verdict == "HUMAN_ARBITRATION":
            sys.exit(2)
        else:
            sys.exit(1)
    else:
        log.info(json.dumps(context, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    main()
