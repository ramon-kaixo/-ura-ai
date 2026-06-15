import logging, subprocess, re

log = logging.getLogger("ura.scanner.hw_vm")

def escanear_hw_vm() -> dict:
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
    try:
        r = subprocess.run(["dmesg", "--level=err", "--since", "1 hour ago"], capture_output=True, text=True, timeout=5)
        lines = [l for l in r.stdout.strip().split("\n") if l and "usb" not in l.lower()]
        return lines[-5:] if lines else []
    except: return []

def _io_stats() -> dict:
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
    except: pass
    return {}

def _virtio_check() -> bool:
    try:
        r = subprocess.run(["lsmod"], capture_output=True, text=True, timeout=3)
        return "virtio" in r.stdout
    except: return False

def _journal_integrity() -> int:
    try:
        r = subprocess.run(["journalctl", "--verify"], capture_output=True, text=True, timeout=10)
        return r.stdout.count("PASS") if "PASS" in r.stdout else 0
    except: return 0
