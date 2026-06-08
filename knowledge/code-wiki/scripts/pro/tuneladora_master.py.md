# `scripts/pro/tuneladora_master.py`

- **Language:** python
- **Chunks:** 11

## Symbols

### function: `log`
- Line: 32

def log(msg):
Escribe al log de la tuneladora.

### function: `modo_delta`
- Line: 44

def modo_delta():
Modo Delta diario: solo procesar archivos modificados.

### function: `helper1`
- Line: 133

def helper1():
Helper function to clean delta snapshots.

### function: `helper2`
- Line: 140

def helper2():
Helper function to rebuild the nervous system from scratch.

### function: `helper3`
- Line: 147

def helper3(label):
Helper function to create a snapshot of F821 errors.

### function: `helper4`
- Line: 156

def helper4(target):
Helper function to compare the F821 errors with a target.

### function: `helper5`
- Line: 167

def helper5():
Helper function to create a delta snapshot for the next cycle.

### function: `modo_profundo`
- Line: 175

def modo_profundo():
Modo Profundo mensual: audit, reset integrity.

### function: `main`
- Line: 234

def main():

## Module Overview

tuneladora_master.py — Orquestador de Excavacion Autonoma (AEA).

Modos:
  --use-delta-check    : Modo Delta diario (solo archivos modificados, ~100% ahorro)
  --force-all          : Modo Profundo mensual (auditoria total, reset integridad)
  --intensive-audit    : Auditoria intensiva (ruff + bandit + radon + F821 completo)

Log: /var/log/ura_tunel.log

Reglas de Oro:
  1. El Guardian es la unica fuente de verdad para limpieza
  2. Cero Ciga (analisis de redundancia innecesario)
  3. Reporte de auditoria obligatorio tras cada ciclo

## Imports

```
datetime.datetime
json
openclaw_firmador.delta_snapshot
os
pathlib.Path
subprocess
sys
time
```
