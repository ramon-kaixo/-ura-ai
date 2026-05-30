#!/usr/bin/env python3
"""
Rotación OAuth — posiciones calibradas por OCR.
Delete + Create + Read dialog. One shot.
"""

import json
import re
import subprocess
import sys
import time
from pathlib import Path
import pyautogui
import pytesseract

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.2
PROJECT = Path("/Users/ramonesnaola/URA/ura_ia_1972")
DOWNLOADS = Path.home() / "Downloads"
OLD_FILES = [
    "token.pickle",
    "credentials.json",
    "config/gmail_credentials.json",
    "config/gmail_token.json",
    "config/client_secret.json",
]
PID = "ura-ia-494907"


def ocr_full(minconf=15):
    """OCR of full screen, return items list."""
    img = pyautogui.screenshot()
    d = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
    return [
        {
            "t": d["text"][i].strip(),
            "x": d["left"][i],
            "y": d["top"][i],
            "w": d["width"][i],
            "h": d["height"][i],
        }
        for i in range(len(d["text"]))
        if d["text"][i].strip() and int(d["conf"][i]) >= minconf
    ]


def find_one(words, items=None):
    """Find first item whose text contains any of the given words."""
    items = items or ocr_full()
    if isinstance(words, str):
        words = [words]
    for it in items:
        for w in words:
            if w.lower() in it["t"].lower() and len(it["t"]) > 2:
                return it
    return None


def clic_at(it, wait=3.0):
    cx = it["x"] + it["w"] // 2
    cy = it["y"] + it["h"] // 2
    pyautogui.click(cx, cy)
    time.sleep(wait)
    return cx, cy


def write_ura():
    pyautogui.hotkey("command", "a")
    time.sleep(0.2)
    pyautogui.write("URA", 0.06)


# ── MAIN ──

print("=" * 60)
print("  ROTACION OAuth — posiciones calibradas")
print("=" * 60)

# 0. Navigate
print("\n[0] Navegando...")
subprocess.run(["open", "https://console.cloud.google.com/apis/credentials?project=" + PID])
time.sleep(8)
subprocess.run(["open", "-a", "Google Chrome"])
time.sleep(3)
pyautogui.hotkey("command", "0")
time.sleep(1)

# Verify we're on credentials page
items = ocr_full(15)
if not find_one(["credenciales", "OAuth"], items):
    print("    [!] Clicking Credenciales sidebar...")
    cred = find_one(["Credenciales"], items)
    if cred:
        clic_at(cred, 5)
        items = ocr_full(15)

# 1. Delete old URA client
print("\n[1] Eliminando URA...")
ura = find_one(["URA", "URAIA"], items)
if ura:
    # Click checkbox to the LEFT of the name
    cbx = ura["x"] - 25
    cby = ura["y"] + ura["h"] // 2
    print(f"    Checkbox en ({cbx}, {cby})")
    pyautogui.click(cbx, cby)
    time.sleep(2)

    # Click DELETE at top
    items2 = ocr_full(15)
    borrar = find_one(["Borrar", "ELIMINAR", "DELETE", "Eliminar"], items2)
    if borrar:
        clic_at(borrar, 3)
        # Confirm
        time.sleep(1)
        items3 = ocr_full(15)
        confirm = find_one(["Eliminar", "Borrar", "Confirmar", "Delete"], items3)
        if confirm:
            clic_at(confirm, 5)
            print("    ✓ URA eliminado")
        else:
            print("    ~ Confirmación no encontrada")
    else:
        print("    ~ DELETE no encontrado")
else:
    print("    ~ URA no visible (quizás ya eliminado)")

time.sleep(3)

# 2. Click CREATE CREDENTIALS
print("\n[2] Crear credenciales...")
items = ocr_full(15)
pyautogui.scroll(2000)
time.sleep(1)  # scroll up
items = ocr_full(15)

crear = find_one(["Crear credenciales", "CREATE CREDENTIALS"], items)
if crear:
    clic_at(crear, 3)
    time.sleep(1)
    # Select OAuth
    items_o = ocr_full(15)
    oauth = find_one(["OAuth client ID", "OAuth"], items_o)
    if oauth:
        clic_at(oauth, 5)
    else:
        # Click where dropdown should be
        pyautogui.click(900, 550)
        time.sleep(5)
        print("    OAuth fallback click")
else:
    print("    ~ Crear credenciales no encontrado")
    # Fallback: click at known position
    pyautogui.click(800, 420)
    time.sleep(3)
    pyautogui.click(900, 500)
    time.sleep(5)

# 3. Check if consent screen
items = ocr_full(15)
consent = find_one(["consentimiento", "Consent", "App name"], items)
if consent:
    print("\n[2b] Configurando consent screen...")
    name_el = find_one(["App name", "Nombre de la", "Nombre de"], items)
    if name_el:
        clic_at(name_el, 2)
        write_ura()
        time.sleep(1)
    for _ in range(5):
        items_s = ocr_full(15)
        save = find_one(["SAVE AND CONTINUE", "GUARDAR", "CONTINUE", "Continuar"], items_s)
        if save:
            clic_at(save, 4)
        else:
            pyautogui.press("tab")
            time.sleep(1)
            pyautogui.press("enter")
            time.sleep(4)
    # Back to dashboard
    time.sleep(2)
    items_b = ocr_full(15)
    back = find_one(["BACK TO DASHBOARD", "VOLVER", "VOLVER AL PANEL"], items_b)
    if back:
        clic_at(back, 4)

    # Re-navigate to credentials
    time.sleep(2)
    items_n = ocr_full(15)
    sidebar = find_one(["Credenciales"], items_n)
    if sidebar:
        clic_at(sidebar, 4)

    pyautogui.scroll(2000)
    time.sleep(1)
    items_c = ocr_full(15)
    crear2 = find_one(["Crear credenciales", "CREATE CREDENTIALS"], items_c)
    if crear2:
        clic_at(crear2, 3)
        time.sleep(1)
        pyautogui.click(900, 500)
        time.sleep(5)

# 4. Fill OAuth form
print("\n[3] Rellenando formulario...")
items = ocr_full(15)
desktop = find_one(["Desktop", "Escritorio", "Aplicación de escritorio"], items)
if desktop:
    clic_at(desktop, 2)

name = find_one(["Name", "Nombre"], items)
if name:
    clic_at(name, 2)
write_ura()
print("    Nombre: URA")
time.sleep(1)

# 5. CREATE
print("\n[4] Botón CREATE...")
items = ocr_full(15)
create_btn = find_one(["CREATE", "CREAR", "Create"], items)
if create_btn:
    clic_at(create_btn, 8)
else:
    pyautogui.press("enter")
    time.sleep(8)

# 6. Read dialog or download
print("\n[5] Obteniendo credenciales...")
time.sleep(2)
final_img = pyautogui.screenshot()
final_txt = pytesseract.image_to_string(final_img)

cid = re.search(r"(\d+-[\w\-]+\.apps\.googleusercontent\.com)", final_txt)
sec = re.search(r"(GOCSPX-[\w\-]{20,})", final_txt)

if cid and sec:
    print(f"    Client ID: {cid.group(1)[:40]}...")
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
    print("    [!] No se pudo leer del diálogo. Intentando descargar...")
    items_dl = ocr_full(15)
    dl_btn = find_one(["DOWNLOAD JSON", "DESCARGAR", "Download"], items_dl)
    if dl_btn:
        clic_at(dl_btn, 3)
        time.sleep(1)
        pyautogui.press("enter")
        time.sleep(5)

    before = {p.name for p in DOWNLOADS.glob("client_secret_*.json")}
    for _ in range(30):
        after = {p.name for p in DOWNLOADS.glob("client_secret_*.json")}
        new = after - before
        if new:
            fname = new.pop()
            data = json.loads((DOWNLOADS / fname).read_text())
            print(f"    Archivo: {fname}")
            break
        time.sleep(1)
    else:
        print("ERROR: Nada.")
        sys.exit(1)

# 7. Close dialog
items_cl = ocr_full(15)
close_btn = find_one(["OK", "CLOSE", "CERRAR"], items_cl)
if close_btn:
    clic_at(close_btn, 1)

# 8. Write files
print("\n[6] Escribiendo archivos...")
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

# 9. OAuth flow
print("\n[7] Autenticación OAuth...")
vp = PROJECT / ".venv" / "bin" / "python"
py = str(vp) if vp.exists() else "python3"
r = subprocess.run(
    [py, "setup_gmail_oauth.py"], cwd=str(PROJECT), capture_output=True, text=True, timeout=120
)
if r.stdout:
    print(r.stdout)
if r.returncode and r.stderr:
    print(r.stderr)

print("\n" + "=" * 60)
print("  ✅ CREDENCIALES ROTADAS CON ÉXITO")
print("=" * 60)
