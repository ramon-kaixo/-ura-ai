# `scripts/pro/rpa_linksys.py`

- **Language:** python
- **Chunks:** 5

## Symbols

### function: `log`
- Line: 38

def log(msg):

### function: `wait_and_click`
- Line: 42

def wait_and_click(region, confidence, timeout):
Espera a que aparezca una imagen y hace click.

### function: `main`
- Line: 48

def main():

## Module Overview

RPA Linksys — Control robótico del navegador en Mac.

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

## Imports

```
pathlib.Path
pyautogui
subprocess
sys
time
```
