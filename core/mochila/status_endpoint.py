"""Endpoint unificado de estado del sistema — async."""

import asyncio
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

import httpx


async def _ram_info() -> dict:
    try:
        proc = await asyncio.create_subprocess_exec(
            "free",
            "-g",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
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
    except Exception as e:
        logger.warning("_ram_info: %s", e)
    return {"error": "free -g not available"}


def _fs_bug_status() -> dict:
    repo = Path("/home/ramon/URA/ura_ia_1972")
    critical = [
        "core/mochila/mochila_server.py",
        "core/mochila/tools.py",
        "core/memoria/ficha.py",
        "core/memoria/ingesto.py",
        "core/memoria/compresor.py",
        "core/memoria/qdrant_store.py",
        "tests/test_mochila.py",
    ]
    missing = sum(1 for f in critical if not (repo / f).exists())
    return {"archivos_criticos_perdidos": missing, "estado": "OK" if missing == 0 else "DEGRADADO"}


async def _timer_status(name: str) -> str:
    try:
        proc = await asyncio.create_subprocess_exec(
            "systemctl",
            "is-active",
            name,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5)
        return stdout.decode().strip()
    except Exception:
        return "unknown"


async def _alemania_status() -> dict:
    try:
        return json.loads(Path.home().joinpath(".nervioso/alertas/estado_alemania.json").read_text())
    except Exception:
        return {"global": "unknown", "ips": {}, "servicios": {}}


async def _tunnel_status() -> dict:
    active = False
    try:
        proc = await asyncio.create_subprocess_exec(
            "systemctl",
            "is-active",
            "ura-hetzner-tunnel",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5)
        active = stdout.decode().strip() == "active"
    except Exception as e:
        logger.warning("_external_services tunnel: %s", e)
    searxng_ok = False
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get("http://127.0.0.1:8888/search?q=health&format=json")
            searxng_ok = resp.status_code == 200
    except Exception as e:
        logger.warning("_external_services searxng: %s", e)
    return {"tunnel_active": active, "searxng_accessible": searxng_ok}


async def system_status(providers: dict, cost_tracker, circuit_breaker, tools_count: int, router) -> dict:
    ram, alem, tunnel, timers_list = await asyncio.gather(
        _ram_info(),
        _alemania_status(),
        _tunnel_status(),
        asyncio.gather(
            _timer_status("ura-mochila-guard.timer"),
            _timer_status("ura-qdrant-backup.timer"),
            _timer_status("ura-cola-nocturna.timer"),
            _timer_status("ura-memoria-vigilante.timer"),
            _timer_status("ura-watch-inbox.service"),
            return_exceptions=True,
        ),
        return_exceptions=True,
    )

    def _to(r):
        return r if not isinstance(r, BaseException) else {"ok": False, "detalle": str(r)}

    return {
        "mochila": {
            "providers": list(providers.keys()),
            "tools": tools_count,
            "rutas": list(router.rutas.keys()),
        },
        "circuit_breaker": {p: circuit_breaker.estado(p) for p in providers},
        "cost_hoy": cost_tracker.resumen_hoy(),
        "ram": _to(ram),
        "fs_bug": _fs_bug_status(),
        "alemania": _to(alem),
        "tunnel_hetzner": _to(tunnel),
        "timers": {
            "guard": _to(timers_list[0]) if len(timers_list) > 0 else {"ok": False, "detalle": "no data"},
            "backup": _to(timers_list[1]) if len(timers_list) > 1 else {"ok": False, "detalle": "no data"},
            "cola": _to(timers_list[2]) if len(timers_list) > 2 else {"ok": False, "detalle": "no data"},
            "vigilante": _to(timers_list[3]) if len(timers_list) > 3 else {"ok": False, "detalle": "no data"},
            "watchdog": _to(timers_list[4]) if len(timers_list) > 4 else {"ok": False, "detalle": "no data"},
        },
    }
