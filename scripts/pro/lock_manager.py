#!/usr/bin/env python3
"""Lock Manager — Cerrojo de exclusión mutua para operaciones GPU.

Previene colisiones entre la tuneladora, el crontab y ejecuciones manuales
durante la recuperación del bug de power cap (rmmod/modprobe de NVIDIA).

USO:
    from lock_manager import acquire_gpu_lock, release_gpu_lock

    fp = acquire_gpu_lock()       # Lanza RuntimeError si timeout
    try:
        # operación crítica (rmmod/modprobe)
    finally:
        release_gpu_lock(fp)
"""

import fcntl
import time

LOCK_FILE = "/tmp/gpu_health_tuneladora.lock"  # noqa: S108


def acquire_gpu_lock(lock_file: str = LOCK_FILE, timeout: int = 30):
    """Adquiere un cerrojo exclusivo (LOCK_EX) sobre lock_file.

    Usa LOCK_NB para no bloquear el hilo; reintenta cada 1s hasta `timeout`.
    Lanza RuntimeError si no puede adquirirlo en el tiempo límite.

    Args:
        lock_file: Ruta al archivo de lock (/tmp/...).
        timeout: Segundos máximos de espera (default 10).

    Returns:
        File object con el lock adquirido (pasar a release_gpu_lock).

    Raises:
        RuntimeError: Si no se pudo adquirir el lock en `timeout` segundos.

    """
    fp = open(lock_file, "w")  # noqa: PTH123, SIM115
    start = time.time()
    while True:
        try:
            fcntl.flock(fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return fp
        except (OSError, BlockingIOError):
            if time.time() - start > timeout:
                fp.close()
                msg = f"No se pudo adquirir el cerrojo {lock_file} en {timeout}s (recurso retenido por otro proceso)"
                raise RuntimeError(  # noqa: B904
                    msg,
                )
            time.sleep(1)


def release_gpu_lock(fp) -> None:
    """Libera el cerrojo (LOCK_UN) y cierra el descriptor.

    Args:
        fp: File object retornado por acquire_gpu_lock (puede ser None).

    """
    if fp:
        try:
            fcntl.flock(fp, fcntl.LOCK_UN)
        finally:
            fp.close()
