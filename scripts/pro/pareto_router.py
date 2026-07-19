#!/usr/bin/env python3
"""Pareto Router — Distribución 20/80 de datos en el ecosistema URA.

📖 MANUAL DE USO RÁPIDO:
  python3 scripts/pro/pareto_router.py --clasificar    # Clasificar datos del pipeline
  python3 scripts/pro/pareto_router.py --sync-criticos  # Sincronizar 20% crítico a Mac+Hetzner
  python3 scripts/pro/pareto_router.py --purge-cache    # Purgar caché si RAM >85%

🔒 PRINCIPIO 20/80:
  ASUS (128GB RAM): 100% IA pesada (Ollama) + 100% análisis vídeo
  Solo 20% datos críticos → sincronizar al exterior (alertas, conciencia, reglas)
  80% datos pesados → cache local ASUS o Hetzner (backups, logs, snapshots, vídeo)
  DERP relays: PROHIBIDOS para ASUS→Hetzner. Forzar conexión directa.
"""

PLUGIN = {
    "name": "pareto_router",
    "phase": "post",
    "timeout": 30,
    "blocking": False,
    "needs_file": False,
}

import json
import os
import subprocess
import sys
import time
from pathlib import Path

try:
    import psutil
except ImportError:
    psutil = None

URA = Path("/home/ramon/URA/ura_ia_1972")
NERVIOSO = URA / ".nervioso"
MAC_IP = os.environ.get("MAC_IP", "10.164.1.26")
HETZNER = os.environ.get("HETZNER_HOST", "hetzner-escudo")

# Clasificación de datos 20/80
DATOS_CRITICOS = {  # 20% — sincronizar siempre
    ".nervioso/conciencia.json": {"peso": "1KB", "frecuencia": "cada_ciclo"},
    ".nervioso/watermarks.json": {"peso": "2KB", "frecuencia": "cada_ciclo"},
    ".nervioso/reglas_auto.json": {"peso": "3KB", "frecuencia": "cada_6h"},
    ".nervioso/chunk_config.json": {"peso": "2KB", "frecuencia": "cada_6h"},
    "docs/pro/reports/": {"peso": "~100KB", "frecuencia": "diario"},
    "config/dispositivos.json": {"peso": "2KB", "frecuencia": "on_change"},
    "config/infra_config.json": {"peso": "1KB", "frecuencia": "on_change"},
}

DATOS_PESADOS = {  # 80% — cache local o Hetzner, no saturar subida
    "backups/": {"peso": "~500MB", "frecuencia": "diario", "destino": "hetzner"},
    "logs/": {"peso": "~50MB/día", "frecuencia": "diario", "destino": "hetzner"},
    ".nervioso/sistema_map.json": {"peso": "2MB", "frecuencia": "semanal", "destino": "local"},
    ".nervioso/hashes_history.jsonl": {"peso": "~1MB", "frecuencia": "cada_ciclo", "destino": "local"},
    "/vids/camaras/": {"peso": "~10GB/día", "frecuencia": "continuo", "destino": "local+hetzner"},
}


def _free_ram_mb() -> int:
    if psutil:
        return psutil.virtual_memory().available // (1024 * 1024)
    try:
        with open("/proc/meminfo") as f:  # noqa: PTH123
            for line in f:
                if "MemAvailable" in line:
                    return int(line.split()[1]) // 1024
    except Exception:  # noqa: S110
        pass
    return 8192


def sync_criticos():
    """Sincroniza los datos del 20% crítico a Mac y Hetzner."""
    synced = 0
    errors = 0

    for path in DATOS_CRITICOS:
        src = URA / path
        if not src.exists():
            continue

        try:
            # Sync a Mac (cable directo)
            r = subprocess.run(  # noqa: S603
                [  # noqa: S607
                    "rsync",
                    "-avz",
                    "--timeout=10",
                    str(src),
                    f"ramon@{MAC_IP}:/Users/ramonesnaola/URA/ura_ia_1972/{path}",
                ],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            if r.returncode == 0:
                synced += 1
            else:
                errors += 1
        except Exception:
            errors += 1

        # Sync a Hetzner (via Tailscale, solo si online)
        try:
            r = subprocess.run(
                ["tailscale", "status", "--json"],  # noqa: S607
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            peers = json.loads(r.stdout).get("Peer", {})
            hetzner_online = any(
                "hetzner" in p.get("DNSName", "").lower() and p.get("Online", False) for p in peers.values()
            )
        except Exception:
            hetzner_online = False

        if hetzner_online:
            try:
                r = subprocess.run(  # noqa: S603
                    ["rsync", "-avz", "--timeout=15", str(src), f"ramon@{HETZNER}:{src}"],  # noqa: S607
                    capture_output=True,
                    text=True,
                    timeout=30,
                    check=False,
                )
                if r.returncode == 0:
                    pass
                else:
                    pass
            except Exception:  # noqa: S110
                pass

    return {"synced": synced, "errors": errors}


def check_ram_purge():
    """Si RAM >85%, purgar caché de datos pesados."""
    ram_free = _free_ram_mb()
    ram_total = 121920  # 128GB
    ram_pct = 100 - (ram_free / ram_total * 100)

    if ram_pct > 85:
        purged = 0
        for path in DATOS_PESADOS:
            target = URA / path.rstrip("/")
            if target.exists() and target.is_dir():
                # Solo purgar archivos > 7 días
                cutoff = time.time() - 7 * 86400
                for f in target.rglob("*"):
                    if f.is_file() and f.stat().st_mtime < cutoff:
                        try:
                            f.unlink()
                            purged += 1
                        except Exception:  # noqa: S110
                            pass
        return {"ram_pct": ram_pct, "purged": purged, "ram_free_mb": ram_free}
    return {"ram_pct": ram_pct, "purged": 0, "ram_free_mb": ram_free, "status": "ok"}


def clasificar_datos() -> dict:
    """Clasifica todos los datos del pipeline en 20% crítico vs 80% pesado."""
    total_criticos = sum(
        Path(URA / p).stat().st_size if (URA / p).exists() else 0 for p in DATOS_CRITICOS if not p.endswith("/")
    )
    total_pesados_est = sum(
        int(
            info["peso"]
            .replace("KB", "000")
            .replace("MB", "000000")
            .replace("GB", "000000000")
            .replace("~", "")
            .split("/")[0],
        )
        for info in DATOS_PESADOS.values()
    )

    return {
        "criticos_KB": total_criticos // 1024,
        "pesados_MB_estimado": total_pesados_est // 1024 // 1024,
        "ratio": f"{total_criticos}/{total_pesados_est + total_criticos:.0f}",
        "datos_criticos": len(DATOS_CRITICOS),
        "datos_pesados": len(DATOS_PESADOS),
    }


def scan_project() -> None:
    from pathlib import Path as _Path

    root = _Path.home() / "URA/ura_ia_1972"
    list(root.rglob("*.py"))


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Pareto Router — Distribución 20/80 de datos")
    parser.add_argument("--scan", action="store_true", help="Escanear todo el proyecto")
    parser.add_argument("--clasificar", action="store_true", help="Clasificar datos del pipeline")
    parser.add_argument("--sync-criticos", action="store_true", help="Sincronizar 20% crítico")
    parser.add_argument("--purge-cache", action="store_true", help="Purgar caché si RAM >85%")
    parser.add_argument("--status", action="store_true", help="Estado general del Pareto")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.scan:
        scan_project()
        return

    if args.sync_criticos:
        result = sync_criticos()
        sys.exit(0 if result["errors"] == 0 else 1)

    if args.purge_cache:
        result = check_ram_purge()
        if args.json:
            pass
        else:
            pass
        sys.exit(0 if result.get("ram_pct", 0) < 85 else 1)

    if args.clasificar:
        result = clasificar_datos()
        if args.json:
            pass
        else:
            for _path, _info in DATOS_CRITICOS.items():
                pass
            for _path, _info in DATOS_PESADOS.items():
                pass

    if args.status or not any([args.clasificar, args.sync_criticos, args.purge_cache]):
        clasificar_datos()
        check_ram_purge()


if __name__ == "__main__":
    main()
