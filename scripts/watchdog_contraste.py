#!/usr/bin/env python3
"""Watchdog para proxy_contraste — restart automático si cae.

Se ejecuta como daemon con setsid. Verifica cada 30s que uvicorn
esté vivo y respondiendo, y lo relanza si es necesario.
"""

import os
import subprocess
import sys
import time

UVICORN_BIN = "/home/ramon/.local/bin/uvicorn"
WORKDIR = "/opt/ura/agents"
PORT = "8002"
CHECK_URL = "http://127.0.0.1:8002/health"
POLL_INTERVAL = 30


def is_alive() -> bool:
    """Check if uvicorn is responding on port."""
    try:
        import urllib.request

        req = urllib.request.Request(CHECK_URL)  # noqa: S310
        with urllib.request.urlopen(req, timeout=5) as resp:  # noqa: S310
            return resp.status == 200
    except Exception:
        return False


def restart() -> bool:
    """Kill existing uvicorn processes and start fresh."""
    subprocess.run(
        ["pkill", "-f", "uvicorn proxy_contraste"],  # noqa: S607
        capture_output=True,
        check=False,
    )
    time.sleep(2)
    proc = subprocess.Popen(  # noqa: S603
        [
            UVICORN_BIN,
            "proxy_contraste:app",
            "--host",
            "0.0.0.0",  # noqa: S104
            "--port",
            PORT,
            "--workers",
            "1",
        ],
        cwd=WORKDIR,
        stdout=open("/tmp/ura-contraste.log", "a"),  # noqa: PTH123, S108, SIM115
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
    )
    return proc.poll() is None


def main() -> None:
    sys.stdout.write(f"watchdog_contraste iniciado (PID {os.getpid()}, cada {POLL_INTERVAL}s)\n")
    sys.stdout.flush()

    while True:
        time.sleep(POLL_INTERVAL)
        if is_alive():
            continue
        sys.stdout.write(f"[{time.strftime('%H:%M:%S')}] proxy_contraste caído. Relanzando...\n")
        sys.stdout.flush()
        if restart():
            sys.stdout.write(f"[{time.strftime('%H:%M:%S')}] Relanzado.\n")
            sys.stdout.flush()
        else:
            sys.stdout.write(f"[{time.strftime('%H:%M:%S')}] ERROR: No se pudo relanzar.\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
