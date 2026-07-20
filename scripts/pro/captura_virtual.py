"""captura_virtual.py — Captura programatica en Xvfb :99."""  # noqa: INP001

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

DISPLAY = ":99"
OUT_DIR = Path("/tmp/ura-capturas")


class CapturaVirtual:
    def __init__(self, display: str = DISPLAY) -> None:
        self.display = display
        self.env = {**os.environ, "DISPLAY": display}
        OUT_DIR.mkdir(parents=True, exist_ok=True)

    def capturar(self, nombre: str = "captura") -> Path:
        ts = int(time.time())
        tmp = OUT_DIR / f".{nombre}_{ts}.png"
        final = OUT_DIR / f"{nombre}_{ts}.png"
        subprocess.run(["scrot", str(tmp)], env=self.env, capture_output=True, timeout=10, check=False)
        if tmp.exists():
            tmp.rename(final)
        return final if final.exists() else Path()

    def abrir(self, cmd: list[str]) -> subprocess.Popen:
        return subprocess.Popen(cmd, env=self.env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def ventanas(self) -> list[str]:
        r = subprocess.run(
            ["xdotool", "search", "--onlyvisible", "."],
            env=self.env,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        return [w for w in r.stdout.strip().split("\n") if w]

    def cerrar_ventana(self, wid: str) -> None:
        subprocess.run(["xdotool", "windowkill", wid], env=self.env, capture_output=True, timeout=5, check=False)

    def limpiar(self) -> None:
        for w in self.ventanas():
            self.cerrar_ventana(w)


if __name__ == "__main__":
    c = CapturaVirtual()
    cmd = sys.argv[1:]
    if cmd:
        proc = c.abrir(cmd)
        time.sleep(3)
        out = c.capturar("lanzamiento")
        proc.terminate()
    else:
        out = c.capturar("test")
