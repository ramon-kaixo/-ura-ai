# `scripts/pro/refactor_4_motores.py`

- **Language:** python
- **Chunks:** 5

## Symbols

### function: `log`
- Line: 31

def log(msg):

### function: `worker_task`
- Line: 35

def worker_task(worker_id):

### function: `main`
- Line: 56

def main():

## Module Overview

refactor_4_motores.py — Orquestador de 4 workers de refactorización en paralelo.

Lanza 4 workers (deepseek-coder:6.7b con compactación) en paralelo,
cada uno procesando ~10 funciones >80 líneas vía round-robin.

## Imports

```
concurrent.futures.ThreadPoolExecutor
concurrent.futures.as_completed
os
pathlib.Path
subprocess
sys
time
```
