# `scripts/pro/tuneladora_mantenimiento.py`

- **Language:** python
- **Chunks:** 29

## Symbols

### function: `_load_devices`
- Line: 34

def _load_devices(root):

### function: `log`
- Line: 60

def log(msg):

### function: `run`
- Line: 64

def run(cmd, timeout):

### function: `detectar_nivel`
- Line: 72

def detectar_nivel():

### function: `health_check`
- Line: 82

def health_check():

### function: `check_ollama`
- Line: 106

def check_ollama():

### function: `check_model_router`
- Line: 116

def check_model_router():

### function: `check_dispositivos`
- Line: 124

def check_dispositivos():

### function: `step_token_screen`
- Line: 140

def step_token_screen():

### function: `step_scanner_entrada`
- Line: 148

def step_scanner_entrada():

### function: `step_scanner_salida`
- Line: 153

def step_scanner_salida():

### function: `step_poda`
- Line: 158

def step_poda():

### function: `step_refactor`
- Line: 163

def step_refactor(workers, model, fallback):

### function: `step_compactadora`
- Line: 201

def step_compactadora():

### function: `step_inspectores`
- Line: 207

def step_inspectores():

### function: `snapshot_f821`
- Line: 216

def snapshot_f821(label):

### function: `audit_delta`
- Line: 221

def audit_delta(target):

### function: `git_commit_if_stable`
- Line: 227

def git_commit_if_stable():

### function: `git_rollback`
- Line: 233

def git_rollback():

### function: `step_diagnostico_conciencia`
- Line: 241

def step_diagnostico_conciencia():

### function: `step_testing_acciones`
- Line: 250

def step_testing_acciones():

### function: `step_gestion_datos`
- Line: 259

def step_gestion_datos():

### function: `step_auto_mejora_prompt`
- Line: 268

def step_auto_mejora_prompt():

### function: `revision_ligera`
- Line: 277

def revision_ligera():

### function: `revision_media`
- Line: 290

def revision_media():

### function: `revision_profunda`
- Line: 315

def revision_profunda():

### function: `main`
- Line: 381

def main():

## Module Overview

TUNELADORA DE MANTENIMIENTO — Flujo unificado con commit/rollback.

FLUJO CORRECTO:
  Ligero (6h):   token_screen + scanner + ruff + auto_reglas
  Medio (24h):   + poda + refactor_v2 + compactadora + scanner_salida + inspectores
  Profundo (7d): + refactor 4 workers + watermarks + backup + commit/rollback

FUSIONADO CON:
  - ciclo_autonomo_gx10.py (commit/rollback basado en F821)
  - analizar_fallo_conciencia.py (diagnóstico de conciencia)
  - master_conciencia.py (testing de acciones)
  - pareto_router.py (gestión de datos)
  - ura_self_modify.py (auto-mejora del prompt)

## Imports

```
datetime.datetime
json
os
pathlib.Path
socket
subprocess
sys
```
