#!/usr/bin/env python3
"""ura_watch_asus.py — Vigila ASUS GX10 desde Mac, envía WoL si no responde.
Se ejecuta vía launchd cada 2 minutos.

ASUS MAC: 30:c5:99:c0:64:c3
Check via: Tailscale (100.72.103.12) o Ethernet (10.164.1.99)
"""

import os
import socket
import subprocess
import time

ASUS_MAC = "30:c5:99:c0:64:c3"
ASUS_IPS = ["100.72.103.12", os.environ.get("ASUS_HOST", "10.164.1.99")]
PING_COUNT = 2
PING_TIMEOUT = 5
MAX_FAILS = 3
FAIL_LOG = "/tmp/ura_asus_watch_fail"
LOG = "/Users/ramonesnaola/URA/logs/ura_asus_watch.log"


def log(msg: str) -> None:
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, "a") as f:
        f.write(line + "\n")


def ping(ip: str) -> bool:
    r = subprocess.run(
        ["ping", "-c", str(PING_COUNT), "-t", str(PING_TIMEOUT), ip],
        capture_output=True,
        timeout=10,
        check=False,
    )
    return r.returncode == 0


def send_wol(mac: str) -> bool:
    mac_bytes = bytes.fromhex(mac.replace(":", ""))
    magic = b"\xff" * 6 + mac_bytes * 16
    for broadcast in ["10.164.1.255", "192.168.1.255"]:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            s.sendto(magic, (broadcast, 9))
            s.close()
            log(f"  WoL enviado a {broadcast}")
        except Exception as e:
            log(f"  WoL error en {broadcast}: {e}")
    return True


def main() -> None:
    log("=== ASUS Watch ===")

    # Intentar ping por Tailscale y Ethernet
    alive = any(ping(ip) for ip in ASUS_IPS)

    if alive:
        log("ASUS responde")
        try:
            os.remove(FAIL_LOG)
        except FileNotFoundError:
            pass
        return

    # No responde — incrementar contador
    fails = 0
    try:
        with open(FAIL_LOG) as f:
            fails = int(f.read().strip())
    except (FileNotFoundError, ValueError):
        fails = 0
    fails += 1

    log(f"ASUS no responde #{fails}/{MAX_FAILS}")
    with open(FAIL_LOG, "w") as f:
        f.write(str(fails))

    if fails >= MAX_FAILS:
        log("Enviando WoL...")
        send_wol(ASUS_MAC)
        os.remove(FAIL_LOG)
        log("WoL enviado")


if __name__ == "__main__":
    main()
