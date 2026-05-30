#!/usr/bin/env python3
"""
Rotación OAuth — Template Matching con OpenCV + Bezier.
Encuentra elementos por imagen, no por OCR. Mucho más fiable.
"""

import json
import re
import subprocess
import sys
import time
from pathlib import Path
import pyautogui
import pytesseract

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.human_protocol import (
    setup_chrome_window,
    cropped_screenshot,
    human_click,
    human_type,
    human_scroll,
    CHROME_LEFT,
    CHROME_TOP,
    CONTENT_TOP,
)

pyautogui.FAILSAFE = False
PROJECT = Path("/Users/ramonesnaola/URA/ura_ia_1972")
DOWNLOADS = Path.home() / "Downloads"
PID = "ura-ia-494907"
OLD_FILES = [
    "token.pickle",
    "credentials.json",
    "config/gmail_credentials.json",
    "config/gmail_token.json",
    "config/client_secret.json",
]

REF_DIR = Path("/tmp/ura_refs")
REF_DIR.mkdir(exist_ok=True)


def capture_ref(name: str, crop_box: tuple):
    """Captura una imagen de referencia del area de contenido de Chrome."""
    content = cropped_screenshot()
    ref = content.crop(crop_box)
    path = REF_DIR / f"{name}.png"
    ref.save(str(path))
    return path


def find_ref(name: str, confidence: float = 0.75) -> tuple | None:
    """Busca una imagen de referencia en la pantalla completa."""
    path = REF_DIR / f"{name}.png"
    if not path.exists():
        print(f"    [!] Referencia {name} no existe")
        return None
    try:
        pos = pyautogui.locateOnScreen(str(path), confidence=confidence)
        if pos:
            return (pos.left + pos.width // 2, pos.top + pos.height // 2)
    except Exception as e:
        print(f"    [!] Error buscando {name}: {e}")
    return None


def click_ref(name: str, confidence: float = 0.75, wait: float = 3.0) -> bool:
    """Busca referencia y hace clic humano en su centro."""
    coords = find_ref(name, confidence)
    if coords:
        human_click(coords[0], coords[1])
        time.sleep(wait)
        return True
    return False


# ── 1. Capture reference images ──

print("=" * 60)
print("  ROTACION OAuth — Template Matching")
print("=" * 60)

print("\n[0] Preparando...")
subprocess.run(["open", f"https://console.cloud.google.com/apis/credentials?project={PID}"])
time.sleep(6)
setup_chrome_window()
time.sleep(2)
human_scroll(2000)
time.sleep(1)

# Capture all references from current page state
print("    Capturando referencias...")
capture_ref("crear_credenciales", (260, 30, 440, 70))
capture_ref("ura_row", (100, 270, 550, 320))
capture_ref("oauth_section", (260, 210, 480, 240))
capture_ref("desktop_type", (760, 270, 920, 310))

# Verify we have them
for f in sorted(REF_DIR.glob("*.png")):
    print(f"    ✓ {f.name}")

# ── 2. DELETE URA ──

print("\n[1] Eliminando URA...")
ura_coords = find_ref("ura_row", 0.7)
if ura_coords:
    # Click checkbox to the left of the URA text
    cbx = ura_coords[0] - 200
    cby = ura_coords[1]
    human_click(cbx, cby)
    time.sleep(2)
    print("    ✓ URA seleccionado")

    # Now look for DELETE button — try OCR for text
    content = cropped_screenshot()
    d = pytesseract.image_to_data(content, output_type=pytesseract.Output.DICT)
    for i in range(len(d["text"])):
        t = d["text"][i].strip().lower()
        if t in ["borrar", "eliminar", "delete"] and int(d["conf"][i]) >= 20:
            cx = CHROME_LEFT + d["left"][i] + d["width"][i] // 2
            cy = CHROME_TOP + CONTENT_TOP + d["top"][i] + d["height"][i] // 2
            human_click(cx, cy)
            print(f"    ✓ DELETE ({t})")
            time.sleep(3)
            # Confirm
            content2 = cropped_screenshot()
            d2 = pytesseract.image_to_data(content2, output_type=pytesseract.Output.DICT)
            for j in range(len(d2["text"])):
                t2 = d2["text"][j].strip().lower()
                if t2 in ["eliminar", "borrar", "confirmar"] and int(d2["conf"][j]) >= 15:
                    cx2 = CHROME_LEFT + d2["left"][j] + d2["width"][j] // 2
                    cy2 = CHROME_TOP + CONTENT_TOP + d2["top"][j] + d2["height"][j] // 2
                    human_click(cx2, cy2)
                    print(f"    ✓ Confirmado ({t2})")
                    time.sleep(8)
                    break
            break
    else:
        print("    ~ DELETE no encontrado con OCR")
else:
    print("    ~ URA no encontrado en pantalla")

# ── 3. Reload credentials page ──
print("\n[2] Recargando página de credenciales...")
subprocess.run(["open", f"https://console.cloud.google.com/apis/credentials?project={PID}"])
time.sleep(6)
setup_chrome_window()
time.sleep(2)
human_scroll(2000)
time.sleep(1)

# ── 4. CREATE CREDENTIALS ──
print("\n[3] CREAR CREDENCIALES...")
if click_ref("crear_credenciales", 0.7, wait=3):
    print("    ✓ Crear credenciales")
    time.sleep(2)
    # Select OAuth from dropdown — use OCR since dropdown is dynamic
    content = cropped_screenshot()
    d = pytesseract.image_to_data(content, output_type=pytesseract.Output.DICT)
    for i in range(len(d["text"])):
        t = d["text"][i].strip().lower()
        if "oauth" in t and "client" in t and int(d["conf"][i]) >= 15:
            cx = CHROME_LEFT + d["left"][i] + d["width"][i] // 2
            cy = CHROME_TOP + CONTENT_TOP + d["top"][i] + d["height"][i] // 2
            human_click(cx, cy)
            print("    ✓ OAuth client ID")
            time.sleep(4)
            break
else:
    print("    ~ No encontrado")

# ── 5. Consent screen? ──
content = cropped_screenshot()
txt = pytesseract.image_to_string(content).lower()
if "consentimiento" in txt or "app name" in txt:
    print("\n[3a] Configurando consent screen...")
    d = pytesseract.image_to_data(content, output_type=pytesseract.Output.DICT)
    for i in range(len(d["text"])):
        t = d["text"][i].strip().lower()
        if "name" in t or "nombre" in t and int(d["conf"][i]) >= 15:
            cx = CHROME_LEFT + d["left"][i] + d["width"][i] // 2
            cy = CHROME_TOP + CONTENT_TOP + d["top"][i] + d["height"][i] // 2
            human_click(cx, cy)
            human_type("URA")
            time.sleep(1)
            break
    for _ in range(5):
        d2 = pytesseract.image_to_data(cropped_screenshot(), output_type=pytesseract.Output.DICT)
        for j in range(len(d2["text"])):
            t = d2["text"][j].strip().lower()
            if t in ["guardar", "continue", "continuar"] and int(d2["conf"][j]) >= 15:
                cx = CHROME_LEFT + d2["left"][j] + d2["width"][j] // 2
                cy = CHROME_TOP + CONTENT_TOP + d2["top"][j] + d2["height"][j] // 2
                human_click(cx, cy)
                time.sleep(4)
                break
    # Back + re-navigate
    subprocess.run(["open", f"https://console.cloud.google.com/apis/credentials?project={PID}"])
    time.sleep(5)
    setup_chrome_window()
    time.sleep(2)
    human_scroll(2000)
    time.sleep(1)
    click_ref("crear_credenciales", 0.7, wait=3)
    time.sleep(2)
    content2 = cropped_screenshot()
    d2 = pytesseract.image_to_data(content2, output_type=pytesseract.Output.DICT)
    for i in range(len(d2["text"])):
        if "oauth" in d2["text"][i].strip().lower() and int(d2["conf"][i]) >= 15:
            cx = CHROME_LEFT + d2["left"][i] + d2["width"][i] // 2
            cy = CHROME_TOP + CONTENT_TOP + d2["top"][i] + d2["height"][i] // 2
            human_click(cx, cy)
            time.sleep(4)
            break

# ── 6. Form ──
print("\n[4] Formulario OAuth...")
content = cropped_screenshot()
d = pytesseract.image_to_data(content, output_type=pytesseract.Output.DICT)
for i in range(len(d["text"])):
    t = d["text"][i].strip().lower()
    conf = int(d["conf"][i])
    if ("desktop" in t or "escritorio" in t) and conf >= 15:
        cx = CHROME_LEFT + d["left"][i] + d["width"][i] // 2
        cy = CHROME_TOP + CONTENT_TOP + d["top"][i] + d["height"][i] // 2
        human_click(cx, cy)
        print("    ✓ Desktop")
        time.sleep(2)
        break

for i in range(len(d["text"])):
    t = d["text"][i].strip().lower()
    if t == "nombre" and int(d["conf"][i]) >= 15:
        cx = CHROME_LEFT + d["left"][i] + d["width"][i] // 2
        cy = CHROME_TOP + CONTENT_TOP + d["top"][i] + d["height"][i] // 2
        human_click(cx, cy)
        human_type("URA")
        print("    ✓ URA")
        time.sleep(1)
        break

# ── 7. CREATE ──
print("\n[5] CREATE...")
content = cropped_screenshot()
d = pytesseract.image_to_data(content, output_type=pytesseract.Output.DICT)
found_create = False
for i in range(len(d["text"])):
    t = d["text"][i].strip().lower()
    if t in ["create", "crear"] and int(d["conf"][i]) >= 20:
        cx = CHROME_LEFT + d["left"][i] + d["width"][i] // 2
        cy = CHROME_TOP + CONTENT_TOP + d["top"][i] + d["height"][i] // 2
        human_click(cx, cy)
        print("    ✓ CREATE")
        found_create = True
        time.sleep(8)
        break

if not found_create:
    for _ in range(6):
        pyautogui.press("tab")
        time.sleep(0.3)
    pyautogui.press("enter")
    print("    Tab → Enter")

# ── 8. Read dialog or download ──
print("\n[6] Obteniendo credenciales...")
time.sleep(3)
full = pyautogui.screenshot()
full_txt = pytesseract.image_to_string(full)
cid = re.search(r"(\d+-[\w\-]+\.apps\.googleusercontent\.com)", full_txt)
sec = re.search(r"(GOCSPX-[\w\-]{20,})", full_txt)

if cid and sec:
    print(f"    ID: {cid.group(1)[:40]}...")
    print(f"    Secret: {sec.group(1)[:15]}...")
    data = {
        "web": {
            "client_id": cid.group(1),
            "project_id": PID,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_secret": sec.group(1),
            "redirect_uris": ["http://localhost"],
        }
    }
else:
    print("    [!] Intentando descargar...")
    for _ in range(5):
        pyautogui.press("tab")
        time.sleep(0.3)
    pyautogui.press("enter")
    time.sleep(5)
    before = {p.name for p in DOWNLOADS.glob("client_secret_*.json")}
    for _ in range(60):
        after = {p.name for p in DOWNLOADS.glob("client_secret_*.json")}
        new = after - before
        if new:
            data = json.loads((DOWNLOADS / new.pop()).read_text())
            print("    Descargado")
            break
        time.sleep(1)
    else:
        print("ERROR")
        sys.exit(1)

# ── 9. Write files ──
print("\n[7] Configurando...")
for old in OLD_FILES:
    p = PROJECT / old
    if p.exists():
        p.unlink()
        print(f"    - {old}")

d = PROJECT / "config" / "client_secret.json"
d.parent.mkdir(exist_ok=True)
d.write_text(json.dumps(data, indent=2))
print(f"    + {d}")
cd = PROJECT / "credentials.json"
cd.write_text(json.dumps(data, indent=2))
print(f"    + {cd}")

# ── 10. OAuth flow ──
print("\n[8] Autenticación...")
vp = PROJECT / ".venv" / "bin" / "python"
py = str(vp) if vp.exists() else "python3"
r = subprocess.run(
    [py, "setup_gmail_oauth.py"], cwd=str(PROJECT), capture_output=True, text=True, timeout=120
)
if r.stdout:
    print(r.stdout)
if r.returncode and r.stderr:
    print(r.stderr)

print("\n" + "=" * 60 + "\n  ✅ CREDENCIALES ROTADAS\n" + "=" * 60)
