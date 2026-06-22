"""Endpoint unificado de estado del sistema — async."""

import json
from pathlib import Path

import asyncio
import httpx


async def _ram_info() -> dict:
    try:
        proc = await asyncio.create_subprocess_exec(
            "free", "-g", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError:
        return {"error": "free not available"}
    try:
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5)
        for line in stdout.decode().splitlines():
            if "Mem:" in line:
                parts = line.split()
                total = int(parts[1]) if len(parts) > 1 else 0
                used = int(parts[2]) if len(parts) > 2 else 0
                riesgo = "alto" if used > total * 0.95 else "medio" if used > total * 0.85 else "bajo"
                return {"total_gb": total, "usado_gb": used, "libre_gb": total - used, "riesgo": riesgo}
    except Exception:
        pass
    return {"error": "free -g not available"}


def _fs_bug_status() -> dict:
    repo = Path("/home/ramon/URA/ura_ia_1972")
    critical = [
        "core/mochila/mochila_server.py", "core/mochila/tools.py",
        "core/memoria/ficha.py", "core/memoria/ingesto.py",
        "core/memoria/compresor.py", "core/memoria/qdrant_store.py",
        "tests/test_mochila.py",
    ]
    missing = sum(1 for f in critical if not (repo / f).exists())
    return {"archivos_criticos_perdidos": missing, "estado": "OK" if missing == 0 else "DEGRADADO"}


async def _timer_status(name: str) -> str:
    try:
        proc = await asyncio.create_subprocess_exec(
            "systemctl", "is-active", name,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5)
        return stdout.decode().strip()
    except Exception:
        return "unknown"


async def _alemania_status() -> dict:
    try:
        estado = json.loads(Path.home().joinpath(".nervioso/alertas/estado_alemania.json").read_text())
        return estado
    except Exception:
        return {"global": "unknown", "ips": {}, "servicios": {}}


async def _tunnel_status() -> dict:
    active = False
    try:
        proc = await asyncio.create_subprocess_exec(
            "systemctl", "is-active", "ura-hetzner-tunnel",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5)
        active = stdout.decode().strip() == "active"
    except Exception:
        pass
    searxng_ok = False
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get("http://127.0.0.1:8888/search?q=health&format=json")
            searxng_ok = resp.status_code == 200
    except Exception:
        pass
    return {"tunnel_active": active, "searxng_accessible": searxng_ok}


async def _openclaw_status() -> dict:
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get("http://10.164.1.99:18789/health")
            if resp.status_code == 200:
                return {"ok": True, "detalle": resp.json()}
            return {"ok": False, "detalle": resp.text[:100]}
    except Exception as e:
        return {"ok": False, "detalle": str(e)[:100]}


async def system_status(providers: dict, cost_tracker, circuit_breaker, tools_count: int, router) -> dict:
    openclaw, ram, alem, tunnel, timers_list = await asyncio.gather(
        _openclaw_status(),
        _ram_info(),
        _alemania_status(),
        _tunnel_status(),
        asyncio.gather(
            _timer_status("ura-mochila-guard.timer"),
            _timer_status("ura-qdrant-backup.timer"),
            _timer_status("ura-cola-nocturna.timer"),
            _timer_status("ura-memoria-vigilante.timer"),
            _timer_status("ura-watch-inbox.service"),
        ),
    )

    return {
        "mochila": {
            "providers": list(providers.keys()),
            "tools": tools_count,
            "rutas": list(router.rutas.keys()),
        },
        "circuit_breaker": {p: circuit_breaker.estado(p) for p in providers},
        "cost_hoy": cost_tracker.resumen_hoy(),
        "openclaw": openclaw,
        "ram": ram,
        "fs_bug": _fs_bug_status(),
        "alemania": alem,
        "tunnel_hetzner": tunnel,
        "timers": {
            "guard": timers_list[0],
            "backup": timers_list[1],
            "cola": timers_list[2],
            "vigilante": timers_list[3],
            "watchdog": timers_list[4],
        },
    }
