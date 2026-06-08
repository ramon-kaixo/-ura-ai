# `monitor/snc_remote.py`

- **Language:** python
- **Chunks:** 6

## Symbols

### function: `_escape_applescript`
- Line: 29

def _escape_applescript(s):
Escape string for safe use in osascript double-quoted strings.

### function: `mac_notify`
- Line: 35

def mac_notify(title, message):

### function: `sync_state`
- Line: 47

def sync_state():
Sincroniza el state file desde GX10 vía rsync.

### function: `main`
- Line: 61

def main():

## Module Overview

SNC Remote — Observador en Mac.
Sincroniza /tmp/ura_snc_state.json desde GX10 cada 10s.
Notifica si GX10 está OFFLINE o en estado CRITICAL.

## Imports

```
core.config_manager.CONFIG
datetime.datetime
json
pathlib.Path
subprocess
sys
time
```
