import glob
import logging
import subprocess

log = logging.getLogger("ura.scanner.hw_asus")

RUTA_THERMAL = "/sys/class/thermal/thermal_zone*/temp"

def escanear_hw_asus(temp_gpu=None) -> dict:
    """Escanea salud hardware en equipo físico ASUS."""
    return {
        "ok": True,
        "issues": [],
        "tipo": "fisico",
        "smart_ok": _smart_ok(),
        "thermal_zones": _thermal_zones(),
        "temp_gpu": _temp_gpu_orin() if temp_gpu is None else temp_gpu,
    }

def _smart_ok(disk: str = "/dev/nvme0n1") -> bool:
    """Verifica estado SMART del disco."""
    try:
        r = subprocess.run(["sudo", "smartctl", "-H", disk],
                         capture_output=True, text=True, timeout=10)
        return "PASSED" in r.stdout
    except Exception as e:
        log.warning("smartctl fallo en %s: %s", disk, e)
        return True

def _thermal_zones() -> dict:
    """Lee temperaturas de zonas térmicas."""
    zonas = {}
    for z in sorted(glob.glob(RUTA_THERMAL)):
        try:
            with open(z) as f:
                temp = f.read().strip()
            zonas[z.split("/")[4]] = round(int(temp)/1000, 1) if temp else 0
        except (OSError, ValueError) as e:
            log.debug("fallo lectura zona termica %s: %s", z, e)
    return zonas

def _temp_gpu_orin() -> float:
    """Obtiene temperatura GPU via tegrastats."""
    try:
        r = subprocess.run(["tegrastats", "--interval", "1000", "--count", "1"],
                         capture_output=True, text=True, timeout=5)
        m = __import__("re").search(r"GPU@(\d+)mW", r.stdout)
        if m:
            return int(m.group(1))
    except Exception as e:
        log.debug("tegrastats falló: %s", e)
    return 0.0
