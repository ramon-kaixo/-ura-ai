#!/usr/bin/env python3
"""RPA ZTE F6640 v3 — Router real identificado por capturas.

ZTE F6640 (ZTEGF6640P2N10C)

Layout confirmado por las 4 capturas:
  Barra superior: Internet | Local Network | VoIP | Management
  Menú lateral izquierdo dentro de Local Network:
    Port Forwarding (o Port Mapping / Application)

EJECUTAR EN MAC:
  python3 ~/URA/ura_ia_1972/scripts/pro/rpa_zte_f6640.py
"""

import subprocess
import sys
import time

import pyautogui

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.12


def click(x_pct, y_pct, wait_s=1.0) -> None:
    """Click en coordenadas relativas a la pantalla."""
    w, h = pyautogui.size()
    pyautogui.click(int(w * x_pct), int(h * y_pct))
    time.sleep(wait_s)


def write(text) -> None:
    pyautogui.write(text, interval=0.04)


def press(key, t=1, d=0.15) -> None:
    for _ in range(t):
        pyautogui.press(key)
        time.sleep(d)


def wait(n=1) -> None:
    time.sleep(n)


time.sleep(3)

W, H = pyautogui.size()

try:
    # ═══════════════════════════════════════════════════════════
    # FASE 1: Abrir navegador y login
    # ═══════════════════════════════════════════════════════════
    subprocess.run(["open", "-a", "Safari"])
    wait(3)
    pyautogui.hotkey("command", "l")
    wait(0.5)
    write("http://192.168.1.1")
    press("enter")
    wait(5)

    # Bypass - Tab hasta botón de continuar
    press("tab", 10, 0.12)
    press("enter")
    wait(4)

    # Login: password
    press("tab", 3, 0.12)
    write("admin")
    press("tab")
    write("41161")
    press("enter")
    wait(6)

    # ═══════════════════════════════════════════════════════════
    # FASE 2: Click en pestaña "Local Network"
    # ═══════════════════════════════════════════════════════════
    # Según capturas: Internet | Local Network | VoIP | Management
    # "Local Network" es la 2ª pestaña, aprox 25-35% del ancho, 5-8% alto
    for x_pct in [0.28, 0.32, 0.35]:
        for y_pct in [0.06, 0.07, 0.08]:
            click(x_pct, y_pct, 2.5)

    # ═══════════════════════════════════════════════════════════
    # FASE 3: Click en "Port Forwarding" (menú lateral izquierdo)
    # ═══════════════════════════════════════════════════════════
    # Menú lateral izquierdo ~12-18% del ancho
    for y in [0.22, 0.25, 0.28, 0.30, 0.32, 0.35, 0.38, 0.40, 0.42, 0.45, 0.48]:
        click(0.14, y, 2)

    # ═══════════════════════════════════════════════════════════
    # FASE 4: "Create New Item"
    # ═══════════════════════════════════════════════════════════
    # Botón suele estar arriba-derecha
    for y in [0.18, 0.20, 0.22, 0.24, 0.15, 0.28, 0.30]:
        click(0.75, y, 2)

    # ═══════════════════════════════════════════════════════════
    # FASE 5: REGLA 1 — UDP 41641
    # ═══════════════════════════════════════════════════════════
    # Formulario típico ZTE: Name, Protocol, WAN Port, LAN IP, LAN Port
    # Navegar con Tab
    press("tab", 2)
    write("Ramon_Tailscale")      # Name
    press("tab")
    write("UDP")                   # Protocol (seleccionar UDP)
    press("tab")
    write("41641")                 # WAN Port
    press("tab")
    write("192.168.1.139")         # LAN Host IP
    press("tab")
    write("41641")                 # LAN Port
    # Buscar botón Apply/Save
    press("tab", 4, 0.15)
    press("enter")
    wait(3)

    # Descripción (si hay campo extra)
    press("tab", 2)
    write("Ramon Esnaola - Licencia K0513893926")
    press("tab")
    press("enter")
    wait(3)

    # ═══════════════════════════════════════════════════════════
    # FASE 6: REGLA 2 — UDP 3478
    # ═══════════════════════════════════════════════════════════
    # Volver a "Create New Item"
    for y in [0.18, 0.20, 0.22, 0.24]:
        click(0.75, y, 2)

    press("tab", 2)
    write("Ramon_STUN")            # Name
    press("tab")
    write("UDP")                   # Protocol
    press("tab")
    write("3478")                  # WAN Port
    press("tab")
    write("192.168.1.139")         # LAN Host IP
    press("tab")
    write("3478")                  # LAN Port
    press("tab", 4, 0.15)
    press("enter")
    wait(3)

    # ═══════════════════════════════════════════════════════════
    # FASE 7: Cerrar
    # ═══════════════════════════════════════════════════════════
    pyautogui.hotkey("command", "q")
    wait(1)


except pyautogui.FailSafeException:
    sys.exit(1)
except Exception:
    sys.exit(1)
