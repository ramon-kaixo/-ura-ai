"""Endpoint unificado de estado del sistema."""
import subprocess
from pathlib import Path


def _ram_info() -> dict:
    try:
        out = subprocess.run(["free", "-g"], capture_output=True, text=True, timeout=5)
        for line in out.stdout.splitlines():
            if "Mem:" in line:
                parts = line.split()
                total = int(parts[1]) if len(parts) > 1 else 0
                used = int(parts[2]) if len(parts) > 2 else 0
                return {"total_gb": total, "usado_gb": used, "libre_gb": total - used, "riesgo": "alto" if used > total * 0.95 else "medio" if used > total * 0.85 else "bajo"}
    except Exception:
        pass
    return {"error": "free -g not available"}


def _fs_bug_status() -> dict:
    repo = Path("/home/ramon/URA/ura_ia_1972")
    missing = 0
    critical = [
        "core/mochila/mochila_server.py", "core/mochila/tools.py",
        "core/memoria/ficha.py", "core/memoria/ingesto.py",
        "core/memoria/compresor.py", "core/memoria/qdrant_store.py",
        "tests/test_mochila.py",
    ]
    for f in critical:
        if not (repo / f).exists():
            missing += 1
    return {"archivos_criticos_perdidos": missing, "estado": "OK" if missing == 0 else "DEGRADADO"}


def _timer_status(name: str) -> str:
    try:
        out = subprocess.run(["systemctl", "is-active", name], capture_output=True, text=True, timeout=5)
        return out.stdout.strip()
    except Exception:
        return "unknown"



def _alemania_status() -> dict:
    try:
        estado = json.loads(Path.home().joinpath(".nervioso/alertas/estado_alemania.json").read_text())
        return estado
    except Exception:
        return {"global": "unknown", "ips": {}, "servicios": {}}


def _tunnel_status() -> dict:
    try:
        import subprocess
        r = subprocess.run(["systemctl", "is-active", "ura-hetzner-tunnel"], capture_output=True, text=True, timeout=5)
        active = r.stdout.strip() == "active"
    except Exception:
        active = False
    searxng_ok = False
    try:
        import httpx
        resp = httpx.get("http://127.0.0.1:8888/search?q=health&format=json", timeout=5)
        searxng_ok = resp.status_code == 200
    except Exception:
        pass
    return {"tunnel_active": active, "searxng_accessible": searxng_ok}

def _openclaw_status() -> dict:
    try:
        import httpx
        resp = httpx.get("http://10.164.1.99:18789/health", timeout=5)
        return {"ok": resp.status_code == 200, "detalle": resp.json() if resp.status_code == 200 else resp.text[:100]}
    except Exception as e:
        return {"ok": False, "detalle": str(e)[:100]}


async def system_status(providers: dict, cost_tracker, circuit_breaker, tools_count: int, router) -> dict:
    return {
        "mochila": {
            "providers": list(providers.keys()),
            "tools": tools_count,
            "rutas": list(router.rutas.keys()),
        },
        "circuit_breaker": {p: circuit_breaker.estado(p) for p in providers},
        "cost_hoy": cost_tracker.resumen_hoy(),
        "openclaw": _openclaw_status(),
        "ram": _ram_info(),
        "fs_bug": _fs_bug_status(),
        "alemania": _alemania_status(),
        "tunnel_hetzner": _tunnel_status(),
        "timers": {
            "guard": _timer_status("ura-mochila-guard.timer"),
            "backup": _timer_status("ura-qdrant-backup.timer"),
            "cola": _timer_status("ura-cola-nocturna.timer"),
            "vigilante": _timer_status("ura-memoria-vigilante.timer"),
            "watchdog": _timer_status("ura-watch-inbox.service"),
        },
    }
