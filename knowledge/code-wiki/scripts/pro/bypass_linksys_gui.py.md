# `scripts/pro/bypass_linksys_gui.py`

- **Language:** python
- **Chunks:** 5

## Symbols

### function: `_load_config`
- Line: 25

def _load_config():

### function: `find_and_click`
- Line: 71

def find_and_click(page, selectors, timeout):
Busca el primer selector que existe y hace click.

### function: `bypass_linksys`
- Line: 84

def bypass_linksys():

## Module Overview

Bypass Linksys GUI — Automatización Headless con Playwright.

📖 USO:
  python3 scripts/pro/bypass_linksys_gui.py          # Abrir puertos y verificar
  python3 scripts/pro/bypass_linksys_gui.py --screenshot  # Solo screenshot

🔒 Abre puertos UDP 41641 y 3478 en Linksys Velop MX4200 via navegador invisible.
  Credenciales: recovery key 41161 (admin local)
  Target: 192.168.1.139 (ASUS GX10 WiFi)
  Firma: Ramon Esnaola (K0513893926)

## Imports

```
argparse
contextlib
json
os
pathlib.Path
playwright.sync_api.TimeoutError
playwright.sync_api.sync_playwright
subprocess
sys
time
```
