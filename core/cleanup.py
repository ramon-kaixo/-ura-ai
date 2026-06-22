#!/usr/bin/env python3
"""cleanup.py — Protocolo Matar/Cerrar determinista.

Ejecutar antes de cualquier restart para garantizar que no queden
recursos huérfanos (sockets, locks, SHM, procesos hijos).

Uso:
    cleanup(fault_id="ERR_042", affected={"ports": [8080], "pids": [12345]})
    cleanup.all()  # limpieza completa de todo el sistema
"""

import json
import logging
import os
import signal
import subprocess
import time
from pathlib import Path

logger = logging.getLogger("ura.cleanup")

LOCKS_CONOCIDOS = [
    "/tmp/ura_debate.lock",
    "/tmp/ura_state.json",
    "/tmp/tailscale-selfheal.lock",
    "/tmp/ura-events.pub",
]
SHM_PREFIX = "ura_"


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def kill_proceso(pid: int, nombre: str = "") -> bool:
    if not _pid_alive(pid):
        return True
    log_prefix = f"PID {pid}" + (f" ({nombre})" if nombre else "")
    try:
        os.kill(pid, signal.SIGTERM)
        logger.info("SIGTERM -> %s", log_prefix)
        time.sleep(2)
        if _pid_alive(pid):
            os.kill(pid, signal.SIGKILL)
            logger.info("SIGKILL -> %s", log_prefix)
            time.sleep(1)
        return not _pid_alive(pid)
    except OSError as e:
        logger.warning("Error matando %s: %s", log_prefix, e)
        return False


def purgar_puerto(port: int, protocol: str = "tcp") -> bool:
    try:
        r = subprocess.run(
            ["fuser", "-k", f"{port}/{protocol}"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if r.returncode == 0:
            logger.info("fuser -k %d/%s -> OK", port, protocol)
        else:
            logger.debug("fuser -k %d/%s: sin procesos", port, protocol)
        time.sleep(0.5)
        return True
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        logger.warning("fuser no disponible: %s", e)
        return False


EXIT_CODE_DIR = Path("/tmp/ura_exit_codes")


def guardar_codigo_exit(service: str, exit_code: int, signal: int = 0) -> None:
    """Guarda el codigo de salida de un servicio para post-mortem.

    El watermark_aggregator lee estos archivos para clasificar el fallo.
    """
    EXIT_CODE_DIR.mkdir(parents=True, exist_ok=True)
    info = {
        "service": service,
        "exit_code": exit_code,
        "signal": signal,
        "oom_killed": exit_code == 137 if signal == 0 else False,
        "segfault": exit_code == 139 if signal == 0 else False,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    path = EXIT_CODE_DIR / f"{service}.json"
    path.write_text(json.dumps(info, indent=2))
    logger.warning("Exit code guardado: %s -> %d", service, exit_code)


def leer_codigo_exit(service: str) -> dict | None:
    """Lee el ultimo codigo de salida de un servicio."""
    path = EXIT_CODE_DIR / f"{service}.json"
    if path.exists():
        try:
            return json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            return None
    return None


def limpiar_locks(locks: list[str] | None = None) -> None:
    targets = locks or LOCKS_CONOCIDOS
    for lck in targets:
        p = Path(lck)
        if p.exists():
            try:
                p.unlink()
                logger.info("Lock eliminado: %s", lck)
            except OSError as e:
                logger.warning("No se pudo eliminar lock %s: %s", lck, e)


def limpiar_shm(prefix: str = SHM_PREFIX) -> None:
    try:
        r = subprocess.run(
            ["ipcs", "-m"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        for line in r.stdout.split("\n")[3:]:
            parts = line.split()
            if len(parts) >= 5 and parts[4].startswith(prefix):
                shmid = parts[1]
                subprocess.run(
                    ["ipcrm", "-m", shmid],
                    capture_output=True,
                    timeout=3,
                    check=False,
                )
                logger.info("SHM eliminado: id=%s key=%s", shmid, parts[0])
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        logger.warning("ipcs no disponible: %s", e)
    for f in Path("/dev/shm").glob(f"{prefix}*"):
        try:
            f.unlink()
            logger.info("/dev/shm/%s eliminado", f.name)
        except OSError as e:
            logger.warning("Error eliminando /dev/shm/%s: %s", f.name, e)


def check_vram_post_kill() -> dict:
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-compute-apps=used_memory", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        total = sum(int(line.strip()) for line in r.stdout.strip().split("\n") if line.strip().isdigit())
        if total > 0:
            logger.warning("VRAM post-kill: %d MB todavia en uso", total)
        else:
            logger.info("VRAM post-kill: limpia")
        return {"vram_mb": total, "limpia": total == 0}
    except (subprocess.TimeoutExpired, FileNotFoundError, ValueError) as e:
        logger.warning("VRAM check no disponible: %s", e)
        return {"vram_mb": -1, "limpia": False, "error": str(e)}


def cleanup(
    fault_id: str = "",
    affected: dict | None = None,
    verify: bool = True,
) -> dict:
    """Protocolo completo de limpieza.

    Args:
        fault_id: Identificador del fallo (para log)
        affected: Dict con "ports", "pids", "locks", "shm_segments"
        verify: Si True, verifica post-cleanup

    Returns:
        Dict con resultados de cada paso

    """
    affected = affected or {}
    resultado = {"fault_id": fault_id, "pasos": {}}

    logger.info("=== CLEANUP %s ===", fault_id or "manual")

    # 1. Matar PIDs (SIGTERM → SIGKILL)
    for pid_info in affected.get("pids", []):
        if isinstance(pid_info, dict):
            pid, nombre = pid_info.get("pid"), pid_info.get("name", "")
        else:
            pid, nombre = pid_info, ""
        ok = kill_proceso(pid, nombre)
        resultado["pasos"][f"kill_{pid}"] = ok

    # 2. Purgar puertos
    for port in affected.get("ports", []):
        ok = purgar_puerto(port)
        resultado["pasos"][f"fuser_{port}"] = ok

    # 3. Limpiar locks
    limpiar_locks(affected.get("locks"))
    resultado["pasos"]["locks"] = True

    # 4. Limpiar SHM
    if affected.get("shm_segments"):
        limpiar_shm()
    resultado["pasos"]["shm"] = True

    # 5. Verificar VRAM
    if verify:
        vram = check_vram_post_kill()
        resultado["vram"] = vram

    logger.info("=== CLEANUP %s COMPLETADO ===", fault_id or "manual")
    return resultado


def cleanup_all() -> dict:
    """Limpieza completa de todo el sistema."""
    return cleanup(
        fault_id="cleanup_all",
        affected={
            "ports": [8081, 4096, 9099, 11434, 11435],
            "pids": [],
            "locks": LOCKS_CONOCIDOS,
            "shm_segments": [SHM_PREFIX],
        },
    )


if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    parser = argparse.ArgumentParser(description="URA Cleanup — Protocolo Matar/Cerrar")
    parser.add_argument("--all", action="store_true", help="Limpieza completa")
    parser.add_argument("--port", type=int, help="Puerto especifico a limpiar")
    parser.add_argument("--pid", type=int, help="PID especifico a matar")
    args = parser.parse_args()

    if args.all:
        cleanup_all()
    elif args.port:
        purgar_puerto(args.port)
    elif args.pid:
        kill_proceso(args.pid)
    else:
        parser.print_help()
