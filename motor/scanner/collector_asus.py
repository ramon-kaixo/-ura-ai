import logging, subprocess, json

log = logging.getLogger("ura.scanner.asus")

def escanear_asus(config) -> dict:
    r = {"ollama": False, "qdrant": False, "whisper": False, "temp_gpu": 0}
    host = config.asus_host
    port = config.asus_port
    if not host:
        return r
    r["ollama"] = _check_ollama(host)
    r["qdrant"] = _check_qdrant(host)
    r["whisper"] = _check_whisper(host)
    r["temp_gpu"] = _check_temp(host)
    return r

def _check_ollama(host: str) -> bool:
    try:
        r = subprocess.run(["curl", "-sf", f"http://{host}:11434/api/tags"],
                         capture_output=True, timeout=5)
        return r.returncode == 0
    except: return False

def _check_qdrant(host: str) -> bool:
    try:
        r = subprocess.run(["curl", "-sf", f"http://{host}:6333/collections"],
                         capture_output=True, timeout=5)
        return r.returncode == 0
    except: return False

def _check_whisper(host: str) -> bool:
    try:
        r = subprocess.run(["curl", "-sf", f"http://{host}:9090/health"],
                         capture_output=True, timeout=5)
        return r.returncode == 0
    except: return False

def _check_temp(host: str) -> float:
    try:
        r = subprocess.run(["ssh", f"root@{host}", "cat /sys/class/thermal/thermal_zone0/temp"],
                         capture_output=True, text=True, timeout=5)
        return round(int(r.stdout.strip())/1000, 1) if r.stdout.strip() else 0
    except: return 0
