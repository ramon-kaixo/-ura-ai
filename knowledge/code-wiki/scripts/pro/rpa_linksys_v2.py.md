# `scripts/pro/rpa_linksys_v2.py`

- **Language:** python
- **Chunks:** 5

## Symbols

### function: `press`
- Line: 19

def press(key, times, delay):

### function: `write`
- Line: 24

def write(text, delay):

### function: `wait`
- Line: 27

def wait(n):

## Module Overview

RPA Linksys v2 — Navegación por TECLADO (sin depender de screenshots).

EJECUTAR EN MAC:
  python3 ~/URA/ura_ia_1972/scripts/pro/rpa_linksys_v2.py

Usa solo teclado (Tab, Enter, flechas) para navegar.
Más fiable que clicks ciegos con coordenadas estimadas.

## Imports

```
pyautogui
subprocess
time
```
