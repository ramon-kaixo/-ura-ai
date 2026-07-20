#!/usr/bin/env python3
"""RPA Linksys v2 — Navegación por TECLADO (sin depender de screenshots).

EJECUTAR EN MAC:
  python3 ~/URA/ura_ia_1972/scripts/pro/rpa_linksys_v2.py

Usa solo teclado (Tab, Enter, flechas) para navegar.
Más fiable que clicks ciegos con coordenadas estimadas.
"""

import subprocess
import time

import pyautogui

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.15


def press(key, times=1, delay=0.1) -> None:
    for _ in range(times):
        pyautogui.press(key)
        time.sleep(delay)


def write(text, delay=0.05) -> None:
    pyautogui.write(text, interval=delay)


def wait(n) -> None:
    time.sleep(n)


wait(3)

try:
    # ── 1. Abrir Safari ──
    subprocess.run(["open", "-a", "Safari"], check=False)
    wait(3)
    # Cmd+L para barra de URL
    pyautogui.hotkey("command", "l")
    wait(0.5)
    write("http://192.168.1.1")
    pyautogui.press("enter")
    wait(5)

    # ── 2. Bypass pantalla app ──
    # Presionar Tab varias veces para llegar al link "Continuar"
    press("tab", 12, 0.1)
    pyautogui.press("enter")
    wait(4)

    # ── 3. Login ──
    # Tab hasta el campo de password (el login suele tener 2 campos: usuario + password)
    press("tab", 3)
    write("admin")
    press("tab")
    write("41161")
    pyautogui.press("enter")
    wait(6)  # Esperar a que cargue el dashboard

    # ── 4. Navegar a Security/Apps and Gaming ──
    # Los menús de Linksys suelen ser accesibles por Tab
    # Recorrer todos los enlaces con Tab
    for _ in range(20):
        pyautogui.press("tab")
        time.sleep(0.2)
    # Volver al inicio del menú
    press("tab", 5, 0.3)

    # ── 5. Intentar llegar a Port Forwarding ──
    # Estrategia: hacer Tab hasta encontrar algo, luego flechas
    for attempt in range(3):
        if attempt == 0:
            # Navegar sección por sección con Tab + Space/Enter
            for _i in range(8):
                press("tab", 3, 0.2)
                pyautogui.press("enter")
                wait(2)

        elif attempt == 1:
            # Usar flechas para navegar dentro del menú
            for _i in range(5):
                press("down", 5, 0.15)
                pyautogui.press("enter")
                wait(1.5)

        elif attempt == 2:
            # Click en diferentes zonas del menú lateral
            w, h = pyautogui.size()
            for y_pct in [0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.55]:
                pyautogui.click(w * 0.12, h * y_pct)
                wait(1)

    # ── 6. Rellenar formulario Port Forwarding ──

    # Regla 1: UDP 41641
    w, h = pyautogui.size()
    # Intentar encontrar botón "Add" o "Single Port Forwarding"
    for y_pct in [0.45, 0.50, 0.55, 0.60]:
        pyautogui.click(w * 0.5, h * y_pct)
        wait(1.5)

    # Rellenar campos con Tab
    write("Tailscale_WireGuard")
    press("tab")
    write("41641")
    press("tab")
    write("41641")
    press("tab")
    write("UDP")
    press("tab")
    write("192.168.1.139")
    press("tab", 3)
    pyautogui.press("enter")
    wait(2)

    # Regla 2: UDP 3478
    # Click en Add Rule otra vez
    pyautogui.click(w * 0.5, h * 0.45)
    wait(1.5)

    write("Tailscale_STUN")
    press("tab")
    write("3478")
    press("tab")
    write("3478")
    press("tab")
    write("UDP")
    press("tab")
    write("192.168.1.139")
    press("tab", 3)
    pyautogui.press("enter")
    wait(2)

    # ── 7. Cerrar ──
    pyautogui.hotkey("command", "q")
    wait(1)


except pyautogui.FailSafeException:
    pass
except Exception:  # noqa: S110
    pass
