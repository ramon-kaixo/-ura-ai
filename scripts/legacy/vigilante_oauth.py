#!/usr/bin/env python3
"""
Vigilante de rotación OAuth — monitorea ~/Downloads/ y procesa
automáticamente cuando descargas el nuevo client_secret JSON.
"""

import shutil
import subprocess
import sys
import time
from pathlib import Path

PROJECT_DIR = Path(__file__).parent.parent
DOWNLOADS = Path.home() / "Downloads"
OLD_FILES = [
    "token.pickle",
    "credentials.json",
    "config/gmail_credentials.json",
    "config/gmail_token.json",
    "config/client_secret.json",
]

print("URA esta vigilando tus descargas...")

# Snapshot inicial — ignorar archivos viejos
before = {p.name for p in DOWNLOADS.glob("client_secret_*.json")}

print("[1] Elimina el cliente OAuth 'URA' viejo (papelera)")
print("[2] CREAR CREDENCIALES > ID de cliente de OAuth")
print("[3] Tipo: 'Aplicación de escritorio', Nombre: 'URA'")
print("[4] CREAR > DOWNLOAD JSON")
print()

timeout = 300
start = time.time()
new_file = None

while time.time() - start < timeout:
    after = {p.name for p in DOWNLOADS.glob("client_secret_*.json")}
    new = after - before
    if new:
        name = new.pop()
        new_file = DOWNLOADS / name
        print(f"\nArchivo detectado: {name}")
        break
    time.sleep(1)

if not new_file:
    print("ERROR: No se detecto nuevo client_secret en ~/Downloads/")
    print("Descargalo manualmente y ejecuta: python setup_gmail_oauth.py")
    sys.exit(1)

print("Procesando...")

# Limpiar archivos viejos
for old in OLD_FILES:
    old_path = PROJECT_DIR / old
    if old_path.exists():
        try:
            old_path.unlink()
            print(f"  Eliminado: {old}")
        except Exception:
            pass

# Copiar nuevo
dest = PROJECT_DIR / "config" / "client_secret.json"
dest.parent.mkdir(exist_ok=True)
shutil.copy2(new_file, dest)
print(f"  Copiado a: {dest}")

creds_dest = PROJECT_DIR / "credentials.json"
shutil.copy2(new_file, creds_dest)
print(f"  Copiado a: {creds_dest}")

# Limpiar el download original (opcional)
# new_file.unlink()

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
