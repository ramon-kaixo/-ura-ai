# `scripts/pro/rpa_zte_f6640.py`

- **Language:** python
- **Chunks:** 6

## Symbols

### function: `click`
- Line: 25

def click(x_pct, y_pct, wait_s):
Click en coordenadas relativas a la pantalla.

### function: `write`
- Line: 32

def write(text):

### function: `press`
- Line: 36

def press(key, t, d):

### function: `wait`
- Line: 42

def wait(n):

## Module Overview

RPA ZTE F6640 v3 — Router real identificado por capturas.

ZTE F6640 (ZTEGF6640P2N10C)

Layout confirmado por las 4 capturas:
  Barra superior: Internet | Local Network | VoIP | Management
  Menú lateral izquierdo dentro de Local Network:
    Port Forwarding (o Port Mapping / Application)

EJECUTAR EN MAC:
  python3 ~/URA/ura_ia_1972/scripts/pro/rpa_zte_f6640.py

## Imports

```
pyautogui
subprocess
sys
time
```
