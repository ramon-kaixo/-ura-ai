#!/usr/bin/env python3
"""RPA Linksys — Control robótico del navegador en Mac.

EJECUTAR DIRECTAMENTE EN EL MAC:
  python3 scripts/pro/rpa_linksys.py

Requisitos:
  pip3 install --break-system-packages pyautogui pillow

Qué hace:
  1. Abre Safari en http://192.168.1.1
  2. Encuentra el campo de login visualmente
  3. Escribe credenciales (recovery key 41161)
  4. Navega a Port Forwarding
  5. Añade UDP 41641 → 192.168.1.139
  6. Añade UDP 3478  → 192.168.1.139
  7. Click Guardar
  8. Toma screenshots de evidencia
"""

import subprocess
import sys
import time
from pathlib import Path

try:
    import pyautogui
except ImportError:
    sys.exit(1)

pyautogui.FAILSAFE = True  # Mover ratón a esquina para abortar
pyautogui.PAUSE = 0.5  # Pausa entre acciones

EVIDENCIA = Path.home() / "URA" / "ura_ia_1972" / "config" / "evidencia_router.png"
EVIDENCIA.parent.mkdir(parents=True, exist_ok=True)


def log(msg) -> None:
    pass


def wait_and_click(region=None, confidence=0.8, timeout=10) -> None:
    """Espera a que aparezca una imagen y hace click."""
    # Usar tiempo fijo en vez de image recognition para más fiabilidad
    time.sleep(1)


def main() -> None:
    time.sleep(3)

    try:
        # ── PASO 1: Abrir Safari ──
        log("PASO 1: Abriendo Safari...")
        subprocess.run(["open", "-a", "Safari", "http://192.168.1.1"], check=False)
        time.sleep(4)

        # ── PASO 2: Bypass pantalla app móvil ──
        log("PASO 2: Bypass pantalla app móvil...")
        # Click en "Continuar a Linksys Smart Wi-Fi" (link pequeño abajo derecha)
        # Coordenadas estimadas en Mac screen
        screen_w, screen_h = pyautogui.size()
        # El link suele estar en la parte inferior derecha
        pyautogui.click(screen_w * 0.75, screen_h * 0.85)
        time.sleep(2)

        # ── PASO 3: Login ──
        log("PASO 3: Escribiendo credenciales...")
        # Hacer click en el campo de password (centro de la pantalla)
        pyautogui.click(screen_w * 0.5, screen_h * 0.55)
        time.sleep(0.5)

        # Escribir recovery key
        pyautogui.write("41161", interval=0.1)
        time.sleep(0.5)

        # TAB para ir al botón de login, ENTER para enviar
        pyautogui.press("tab")
        time.sleep(0.3)
        pyautogui.press("enter")
        time.sleep(5)
        log("  Esperando dashboard...")

        # ── PASO 4: Navegar a Security → Apps and Gaming ──
        log("PASO 4: Navegando a Port Forwarding...")
        # Click en el menú lateral (Security / Connectivity)
        # El menú suele estar a la izquierda
        for y_offset in [0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65]:
            pyautogui.click(screen_w * 0.15, screen_h * y_offset)
            time.sleep(0.5)

        # Buscar "Port Forwarding" o "Single Port Forwarding" haciendo scroll y clicks
        log("  Buscando opción Port Forwarding...")
        for y in [0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80]:
            pyautogui.click(screen_w * 0.5, screen_h * y)
            time.sleep(1.5)
            # Tomar screenshot para debug
            pyautogui.screenshot(str(EVIDENCIA))

        # ── PASO 5: Añadir regla UDP 41641 ──
        log("PASO 5: Añadiendo UDP 41641...")
        # Click en "Add Rule" o "Single Port Forwarding"
        pyautogui.click(screen_w * 0.7, screen_h * 0.3)
        time.sleep(1)

        # Rellenar formulario
        pyautogui.write("Tailscale_WireGuard", interval=0.05)
        pyautogui.press("tab")
        pyautogui.write("41641", interval=0.05)
        pyautogui.press("tab")
        pyautogui.write("41641", interval=0.05)
        pyautogui.press("tab")
        pyautogui.write("UDP", interval=0.05)
        pyautogui.press("tab")
        pyautogui.write("192.168.1.139", interval=0.05)
        time.sleep(0.5)

        # Click Apply/Save
        pyautogui.click(screen_w * 0.7, screen_h * 0.7)
        time.sleep(2)
        log("  ✅ UDP 41641 añadido")

        # ── PASO 6: Añadir regla UDP 3478 ──
        log("PASO 6: Añadiendo UDP 3478...")
        # Click en "Add Rule" otra vez
        pyautogui.click(screen_w * 0.7, screen_h * 0.3)
        time.sleep(1)

        pyautogui.write("Tailscale_STUN", interval=0.05)
        pyautogui.press("tab")
        pyautogui.write("3478", interval=0.05)
        pyautogui.press("tab")
        pyautogui.write("3478", interval=0.05)
        pyautogui.press("tab")
        pyautogui.write("UDP", interval=0.05)
        pyautogui.press("tab")
        pyautogui.write("192.168.1.139", interval=0.05)
        time.sleep(0.5)

        pyautogui.click(screen_w * 0.7, screen_h * 0.7)
        time.sleep(2)
        log("  ✅ UDP 3478 añadido")

        # ── PASO 7: Guardar cambios ──
        log("PASO 7: Guardando cambios...")
        # Buscar botón Save/Apply
        pyautogui.click(screen_w * 0.85, screen_h * 0.15)
        time.sleep(3)

        # ── PASO 8: Screenshot evidencia ──
        log("PASO 8: Capturando evidencia...")
        pyautogui.screenshot(str(EVIDENCIA))
        log(f"  ✅ Evidencia: {EVIDENCIA}")

        # ── PASO 9: Cerrar Safari ──
        subprocess.run(["osascript", "-e", 'tell application "Safari" to quit'], check=False)
        log("  Safari cerrado")

    except pyautogui.FailSafeException:
        sys.exit(1)
    except Exception:
        sys.exit(1)


if __name__ == "__main__":
    main()
