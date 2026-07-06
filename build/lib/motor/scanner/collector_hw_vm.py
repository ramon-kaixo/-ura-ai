import logging

from motor.core.executor import SubprocessExecutor

log = logging.getLogger("ura.scanner.hw_vm")
_executor = SubprocessExecutor()


def escanear_hw_vm() -> dict:
    """Escanea salud hardware en entorno VM."""
    return {
        "ok": True,
        "issues": [],
        "tipo": "vm",
        "dmesg_errors": _dmesg_errors(),
        "io_stats": _io_stats(),
        "virtio_ok": _virtio_check(),
        "journal_corrupt": _journal_integrity(),
    }


def _dmesg_errors() -> list:
    """Obtiene errores del kernel de la última hora."""
    try:
        r = _executor.run(["dmesg", "--level=err", "--since", "1 hour ago"], timeout=5)
        lines = [l for l in r.stdout.strip().split("\n") if l and "usb" not in l.lower()]
        return lines[-5:] if lines else []
    except Exception as e:
        log.debug("dmesg falló: %s", e)
        return []


def _io_stats() -> dict:
    """Lee estadísticas de IO del disco principal."""
    try:
        with open("/proc/diskstats") as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 14 and "sda" in parts[2]:
                    return {
                        "reads": int(parts[3]),
                        "writes": int(parts[7]),
                        "time_io_ms": int(parts[12]),
                    }
    except Exception as e:
        log.debug("io_stats falló: %s", e)
    return {}


def _virtio_check() -> bool:
    """Verifica si el módulo virtio está cargado."""
    try:
        r = _executor.run(["lsmod"], timeout=3)
        return "virtio" in r.stdout
    except Exception as e:
        log.debug("virtio check falló: %s", e)
        return False


def _journal_integrity() -> int:
    """Verifica integridad del journald."""
    try:
        r = _executor.run(["journalctl", "--verify"], timeout=10)
        return r.stdout.count("PASS") if "PASS" in r.stdout else 0
    except Exception as e:
        log.debug("journalctl --verify falló: %s", e)
        return 0
