# `scripts/pro/f821_watch.py`

- **Language:** python
- **Chunks:** 9

## Symbols

### function: `find_ruff`
- Line: 31

def find_ruff():

### function: `run_ruff`
- Line: 43

def run_ruff():

### function: `snapshot`
- Line: 60

def snapshot(label):

### function: `compare`
- Line: 84

def compare(target_label):

### function: `report`
- Line: 123

def report():

### function: `scan_project`
- Line: 138

def scan_project():

### function: `main`
- Line: 144

def main():

## Module Overview

Monitoriza progreso de errores F821 (undefined name) via ruff.

Uso:
  python3 f821_watch.py snapshot --label "antes-refactor"
  python3 f821_watch.py compare --target antes-refactor
  python3 f821_watch.py report

## Imports

```
argparse
datetime.UTC
datetime.datetime
json
os
pathlib.Path
shutil
subprocess
sys
```
