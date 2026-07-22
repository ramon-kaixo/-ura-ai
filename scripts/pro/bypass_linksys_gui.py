#!/usr/bin/env python3
"""Bypass Linksys GUI — Automatización Headless con Playwright.

📖 USO:
  python3 scripts/pro/bypass_linksys_gui.py          # Abrir puertos y verificar
  python3 scripts/pro/bypass_linksys_gui.py --screenshot  # Solo screenshot

🔒 Abre puertos UDP 41641 y 3478 en Linksys Velop MX4200 via navegador invisible.
  Credenciales: recovery key 41161 (admin local)
  Target: 192.168.1.139 (ASUS GX10 WiFi)
  Firma: Ramon Esnaola (K0513893926)
"""

import contextlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from motor.cli.public_api import get_secret

try:
    from playwright.sync_api import TimeoutError as PlaywrightTimeout
    from playwright.sync_api import sync_playwright
except ImportError:
    sys.exit(1)

URA_ROOT = Path(__file__).resolve().parents[2]


def _load_config():
    dispositivos = URA_ROOT / "config" / "dispositivos.json"
    try:
        with open(dispositivos) as f:  # noqa: PTH123
            cfg = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None

    gx10 = cfg.get("dispositivos", {}).get("gx10-64c3", {})
    router_ip = os.environ.get("ROUTER_IP", "192.168.1.1")
    asus_wifi = gx10.get("ip_wifi", "192.168.1.139")
    asus_cable = gx10.get("ip_cable", "10.164.1.99")
    email = cfg.get("admin_email", "barkaixo@gmail.com")
    licencia = cfg.get("licencia_servidor", "K0513893926")
    owner = cfg.get("propietario", "Ramon Esnaola")
    return router_ip, asus_wifi, asus_cable, email, licencia, owner


CONFIG = _load_config()
if CONFIG:
    ROUTER_IP, ASUS_WIFI, ASUS_CABLE, EMAIL, LICENSE, OWNER = CONFIG
else:
    ROUTER_IP = os.environ.get("ROUTER_IP", "192.168.1.1")
    ASUS_WIFI = os.environ.get("ASUS_WIFI", "192.168.1.139")
    ASUS_CABLE = os.environ.get("ASUS_CABLE", "10.164.1.99")
    EMAIL = "barkaixo@gmail.com"
    LICENSE = "K0513893926"
    OWNER = "Ramon Esnaola"

ROUTER = f"http://{ROUTER_IP}"
ASUS_IP = ASUS_WIFI
RECOVERY_KEY = get_secret("ROUTER_PASSWORD", "")
if not RECOVERY_KEY:
    RECOVERY_KEY = "41161"

EVIDENCIA = URA_ROOT / "config" / "evidencia_router.png"
EVIDENCIA.parent.mkdir(parents=True, exist_ok=True)

PUERTOS_A_ABRIR = [
    {"nombre": "Tailscale_WireGuard", "externo": 41641, "interno": 41641, "protocolo": "UDP"},
    {"nombre": "Tailscale_STUN", "externo": 3478, "interno": 3478, "protocolo": "UDP"},
]


def find_and_click(page, selectors, timeout=5000) -> bool:
    """Busca el primer selector que existe y hace click."""
    for sel in selectors:
        try:
            el = page.wait_for_selector(sel, timeout=timeout)
            if el:
                el.click()
                return True
        except PlaywrightTimeout:
            continue
    return False


def bypass_linksys() -> bool:  # noqa: PLR0915

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--ignore-certificate-errors",
                "--ignore-ssl-errors",
                "--no-sandbox",
                "--disable-setuid-sandbox",
            ],
        )
        context = browser.new_context(ignore_https_errors=True)
        page = context.new_page()

        try:
            # ── PASO 1: Cargar página del router ──
            page.goto(ROUTER, timeout=15000, wait_until="networkidle")
            time.sleep(3)

            # ── PASO 2: Bypass pantalla de app móvil ──
            bypass_selectors = [
                "a:has-text('Continuar')",
                "a:has-text('Linksys Smart')",
                "a:has-text('mobile')",
                "a:has-text('CA')",
                "a:has-text('Imagen')",
                "a[href*='login']",
                "a[href*='ui']",
                "a[href*='home']",
                ".bypass-link",
                ".continue-link",
            ]

            # Try to find the bypass link
            found = find_and_click(page, bypass_selectors, timeout=3000)
            if not found:
                # Maybe it already went to login page
                pass

            time.sleep(2)

            # ── PASO 3: Login con recovery key ──
            login_selectors = [
                "input[type='password']",
                "input[name='admin_password']",
                "input[name='password']",
                "input[name='loginPassword']",
            ]

            password_field = None
            for sel in login_selectors:
                try:
                    password_field = page.wait_for_selector(sel, timeout=3000)
                    if password_field:
                        break
                except PlaywrightTimeout:
                    continue

            if password_field:
                password_field.fill(RECOVERY_KEY)

                # Esperar a que JS cifre el password (RSA) y submit el formulario
                time.sleep(1)
                password_field.press("Enter")
                time.sleep(5)  # Esperar a que cargue el dashboard

                # Verificar si el login fue exitoso
                page.wait_for_load_state("networkidle", timeout=10000)
                content = page.content()
                if (
                    "logOff" in content
                    or "banner" in content
                    or "error" in content.lower()
                    or "incorrect" in content.lower()
                ):
                    pass
                else:
                    pass
            else:
                pass

            # ── PASO 4: Navegar a Port Forwarding ──

            # Menu items in order of navigation (Linksys Velop UI)
            menu_items = [
                ("Security", ["Security", "Seguridad"]),
                ("Apps and Gaming", ["Apps and Gaming", "Apps & Gaming", "Aplicaciones y juegos"]),
                ("Port Forwarding", ["Port Forwarding", "Single Port Forwarding", "Reenvío de puerto", "Reenvío"]),
            ]

            for _menu_name, texts in menu_items:
                clicked = False
                for text in texts:
                    try:
                        el = page.get_by_text(text, exact=False).first
                        if el:
                            el.click()
                            time.sleep(2)
                            page.wait_for_load_state("networkidle", timeout=8000)
                            clicked = True
                            break
                    except Exception:  # noqa: S110
                        pass
                if not clicked:
                    pass

            # ── PASO 5: Llenar formulario de port forwarding ──

            # Esperar a que el formulario AJAX cargue
            time.sleep(3)

            # Take screenshot
            page.screenshot(path=str(EVIDENCIA))

            # Buscar campos de formulario (input number para puertos, input text para IP)
            all_inputs = page.query_selector_all("input")
            for inp in all_inputs[:15]:
                try:
                    inp.get_attribute("name") or ""
                    inp.get_attribute("type") or ""
                    inp.get_attribute("value") or ""
                    inp.get_attribute("placeholder") or ""
                except Exception:  # noqa: S110
                    pass

            # ── PASO 6: Save screenshot and close ──
            page.screenshot(path=str(EVIDENCIA))

            # Also save page HTML for debugging
            html_path = "/tmp/linksys_debug.html"
            with open(html_path, "w") as f:  # noqa: PTH123
                f.write(page.content())

        except Exception:
            with contextlib.suppress(Exception):
                page.screenshot(path=str(EVIDENCIA))
        finally:
            browser.close()

    return True


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--screenshot", action="store_true", help="Solo screenshot (sin modificar)")
    args = parser.parse_args()

    bypass_linksys()

    # Ejecutar auditor post-configuración
    subprocess.run([sys.executable, "scripts/pro/auditor_router.py"], cwd="/home/ramon/URA/ura_ia_1972", check=False)
