# `cli/gatekeeper.py`

- **Language:** python
- **Chunks:** 11

## Symbols

### function: `ura`
- Line: 16

def ura():
URA Zero-Patch.

### function: `agency_status`
- Line: 19

def agency_status():

### function: `skill_review`
- Line: 24

def skill_review(nombre):

### function: `skill_approve`
- Line: 32

def skill_approve(nombre, skip_sandbox):

### function: `skill_reject`
- Line: 47

def skill_reject(nombre, razon):

### function: `debt_status`
- Line: 52

def debt_status():

### function: `debt_clean`
- Line: 57

def debt_clean(forzar):

### function: `_reg`
- Line: 61

def _reg(n, v, sp):

### function: `registrar_skill_propuesto`
- Line: 69

def registrar_skill_propuesto(nombre, codigo):

## Module Overview

gatekeeper.py — Capa 4: CLI de control humano.

## Imports

```
__future__.annotations
asyncio
click
core.cleaner.cold_refactor.ColdRefactor
core.guardians.ast_sentinel.ASTSentinel
core.sandbox.docker_orchestrator.DockerOrchestrator
datetime.datetime
json
mochila_engine.BASE_DIR
pathlib.Path
sys
```
