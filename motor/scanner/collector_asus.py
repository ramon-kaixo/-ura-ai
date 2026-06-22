import logging
import os
import subprocess

log = logging.getLogger("ura.scanner.asus")

PUERTO_OLLAMA = 11434
PUERTO_QDRANT = 6333
PUERTO_WHISPER = 9090
OPCIONES_SSH = ["-o", "ConnectTimeout=5", "-o", "StrictHostKeyChecking=accept-new", "-o", "BatchMode=yes"]


def escanear_asus(config) -> dict:
    """Escanea servicios y temperatura en el host ASUS remoto."""
    r = {"ollama": False, "qdrant": False, "whisper": False, "temp_gpu": 0}
    host = config.asus_host
    if not host:
        log.debug("escaneo asus saltado: sin host")
        return r
    r["ollama"] = _check_ollama(host)
    r["qdrant"] = _check_qdrant(host)
    r["whisper"] = _check_whisper(host)
    r["temp_gpu"] = _check_temp(host)
    return r


def _check_ollama(host: str) -> bool:
    """Verifica si Ollama responde en el host remoto."""
    try:
        r = subprocess.run(
            ["curl", "-sf", f"http://{host}:{PUERTO_OLLAMA}/api/tags"],
            capture_output=True,
            timeout=5,
            check=False,
        )
        return r.returncode == 0
    except Exception as e:
        log.debug("ollama check %s falló: %s", host, e)
        return False


def _check_qdrant(host: str) -> bool:
    """Verifica si Qdrant responde en el host remoto."""
    try:
        r = subprocess.run(
            ["curl", "-sf", f"http://{host}:{PUERTO_QDRANT}/collections"],
            capture_output=True,
            timeout=5,
            check=False,
        )
        return r.returncode == 0
    except Exception as e:
        log.debug("qdrant check %s falló: %s", host, e)
        return False


def _check_whisper(host: str) -> bool:
    """Verifica si Whisper responde en el host remoto."""
    try:
        r = subprocess.run(
            ["curl", "-sf", f"http://{host}:{PUERTO_WHISPER}/health"],
            capture_output=True,
            timeout=5,
            check=False,
        )
        return r.returncode == 0
    except Exception as e:
        log.debug("whisper check %s falló: %s", host, e)
        return False


def _check_temp(host: str) -> float:
    """Obtiene temperatura GPU vía SSH remoto."""
    try:
        ssh_user = os.environ.get("URA_SSH_USER", "")
        target = f"{ssh_user}@{host}" if ssh_user else host
        r = subprocess.run(
            ["ssh", *OPCIONES_SSH, target, "cat /sys/class/thermal/thermal_zone0/temp"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        return round(int(r.stdout.strip()) / 1000, 1) if r.stdout.strip() else 0
    except Exception as e:
        log.warning("temp remota fallo %s: %s", host, e)
        return 0
