#!/usr/bin/env python3
"""
Rotación OAuth con AppleScript — URA controla tu Chrome directamente.
Ejecuta JavaScript en la página de Google Cloud Console que ya tienes abierta.
Sin coordenadas de pantalla, sin Playwright aparte.
"""

import subprocess
import sys
import time
import shutil
from pathlib import Path

PROJECT_DIR = Path("/Users/ramonesnaola/URA/ura_ia_1972")
DOWNLOADS = Path.home() / "Downloads"
OLD_FILES = [
    "token.pickle",
    "credentials.json",
    "config/gmail_credentials.json",
    "config/gmail_token.json",
    "config/client_secret.json",
]


def run_js(js_code: str) -> str:
    """Ejecuta JavaScript en la pestaña activa de Chrome vía AppleScript."""
    escaped = js_code.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")
    script = f"""
    tell application "Google Chrome"
        set jsResult to execute active tab of front window javascript "{escaped}"
        return jsResult
    end tell
    """
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        text=True,
        timeout=10,
    )
    return result.stdout.strip()


def click_text(text: str) -> bool:
    """Busca y hace clic en un elemento que contenga el texto dado."""
    js = f"""
    (function() {{
        var els = document.querySelectorAll('button, a, span, div[role="button"], div[role="menuitem"], li[role="menuitem"], mat-option');
        for (var el of els) {{
            if (el.textContent && el.textContent.includes('{text}') && el.offsetParent !== null) {{
                el.click();
                return 'clicked:' + el.textContent.trim().substring(0,50);
            }}
        }}
        return 'not_found';
    }})()
    """
    result = run_js(js)
    if result.startswith("clicked:"):
        print(f"     Clic en: {text}")
        return True
    return False


def fill_input(value: str) -> bool:
    """Rellena el primer input de texto visible."""
    js = f"""
    (function() {{
        var inputs = document.querySelectorAll('input:not([type="hidden"]):not([type="checkbox"]):not([type="radio"]):not([type="submit"])');
        for (var inp of inputs) {{
            if (inp.offsetParent !== null) {{
                inp.focus();
                inp.value = '{value}';
                inp.dispatchEvent(new Event('input', {{ bubbles: true }}));
                inp.dispatchEvent(new Event('change', {{ bubbles: true }}));
                return 'filled:' + (inp.name || inp.id || inp.placeholder || 'input');
            }}
        }}
        return 'not_found';
    }})()
    """
    result = run_js(js)
    if result.startswith("filled:"):
        print(f"     Escrito: {value}")
        return True
    return False


def page_text() -> str:
    """Devuelve texto visible de la página para diagnóstico."""
    js = """
    (function() {
        return document.body ? document.body.innerText.substring(0, 500) : 'no body';
    })()
    """
    return run_js(js)


def count_oauth_clients() -> int:
    """Cuenta cuántos clientes OAuth hay en la tabla."""
    js = """
    (function() {
        var rows = document.querySelectorAll('tr, [role="row"]');
        var count = 0;
        var names = [];
        for (var row of rows) {
            var txt = row.textContent || '';
            if (txt.includes('OAuth') && txt.includes('URA')) names.push(txt.substring(0,80));
            if (txt.includes('OAuth')) count++;
        }
        return names.length + ' URA clients, ' + count + ' total OAuth';
    })()
    """
    return run_js(js)


# ── MAIN ────────────────────────────────────────────────────

print("=" * 60)
print("  ROTACION OAuth - URA controla tu Chrome")
print("=" * 60)
print()

# Diagnóstico: ¿qué página está abierta?
text = page_text()
if "credentials" not in text.lower() and "oauth" not in text.lower():
    print("AVISO: No parece que estes en la pagina de credenciales de Google Cloud.")
    print("Abre https://console.cloud.google.com/apis/credentials")
    print("Contenido actual:", text[:200])
    sys.exit(1)

print("Pagina de credenciales detectada.")
print(f"Estado: {count_oauth_clients()}")
print()

# 1. Eliminar cliente viejo URA
print("1/4  Eliminando cliente OAuth 'URA' viejo...")

# Hacer clic en el checkbox de la fila de URA
js_select_ura = """
(function() {
    var rows = document.querySelectorAll('tr, [role="row"]');
    for (var row of rows) {
        if (row.textContent && row.textContent.includes('URA')) {
            var cb = row.querySelector('input[type="checkbox"], [role="checkbox"], mat-checkbox');
            if (cb) { cb.click(); return 'checked URA row'; }
        }
    }
    return 'could not find URA checkbox';
})()
"""
result = run_js(js_select_ura)
print(f"     {result}")
time.sleep(1)

# Clic en DELETE de la toolbar
click_text("DELETE")
time.sleep(2)

# Confirmar eliminación
click_text("DELETE")
click_text("ELIMINAR")
click_text("Confirm")
time.sleep(3)
print("     Cliente viejo eliminado")

# 2. CREAR CREDENCIALES
print()
print("2/4  Abriendo CREAR CREDENCIALES...")
click_text("CREATE CREDENTIALS")
click_text("CREAR CREDENCIALES")
time.sleep(2)

print("3/4  Seleccionando OAuth client ID...")
click_text("OAuth client ID")
click_text("OAuth 2.0 Client ID")
click_text("ID de cliente de OAuth")
time.sleep(2)

# 3. Rellenar formulario
print("     Seleccionando 'Aplicacion de escritorio'...")
click_text("Desktop app")
click_text("Desktop application")
click_text("Aplicación de escritorio")

# Si es un dropdown (mat-select), intentar expandirlo
js_expand_dropdown = """
(function() {
    var selects = document.querySelectorAll('mat-select, select');
    for (var sel of selects) {
        if (sel.offsetParent !== null) { sel.click(); return 'dropdown opened'; }
    }
    return 'no dropdown found';
})()
"""
run_js(js_expand_dropdown)
time.sleep(1)
click_text("Desktop app")
click_text("Desktop")

print("     Escribiendo nombre 'URA'...")
fill_input("URA")
time.sleep(1)

# 4. CREAR y descargar
print()
print("4/4  Creando credencial...")
click_text("CREATE")
click_text("CREAR")
time.sleep(3)

print("     Descargando JSON...")
click_text("DOWNLOAD JSON")
click_text("DESCARGAR JSON")
click_text("Download")

print()
print("Esperando que se descargue el archivo...")

# Esperar a que aparezca el archivo
before = {p.name for p in DOWNLOADS.glob("client_secret_*.json")}
timeout = 60
start = time.time()
new_file = None

while time.time() - start < timeout:
    after = {p.name for p in DOWNLOADS.glob("client_secret_*.json")}
    new = after - before
    if new:
        name = new.pop()
        new_file = DOWNLOADS / name
        print(f"     Detectado: {name}")
        break
    time.sleep(1)

if not new_file:
    print("ERROR: No se detecto la descarga.")
    print("Si ves el boton DOWNLOAD JSON, haz clic manual.")
    print("Luego ejecuta: python scripts/vigilante_oauth.py")
    sys.exit(1)

# Procesar archivo
print()
print("=" * 60)
print("  Configurando credenciales...")
print("=" * 60)

for old in OLD_FILES:
    old_path = PROJECT_DIR / old
    if old_path.exists():
        try:
            old_path.unlink()
            print(f"  Eliminado: {old}")
        except Exception:
            pass

dest = PROJECT_DIR / "config" / "client_secret.json"
dest.parent.mkdir(exist_ok=True)
shutil.copy2(new_file, dest)
print(f"  Copiado a: {dest}")

creds_dest = PROJECT_DIR / "credentials.json"
shutil.copy2(new_file, creds_dest)
print(f"  Copiado a: {creds_dest}")

# Lanzar OAuth flow
print()
print("Iniciando autenticacion OAuth...")
venv_python = PROJECT_DIR / ".venv" / "bin" / "python"
py = str(venv_python) if venv_python.exists() else "python3"
result = subprocess.run(
    [py, "setup_gmail_oauth.py"],
    cwd=str(PROJECT_DIR),
    capture_output=True,
    text=True,
    timeout=120,
)
if result.stdout:
    print(result.stdout)
if result.returncode != 0 and result.stderr:
    print(result.stderr)

print()
print("=" * 60)
print("  CREDENCIALES ROTADAS CON EXITO")
print("=" * 60)
