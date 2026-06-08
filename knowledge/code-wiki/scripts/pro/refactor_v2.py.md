# `scripts/pro/refactor_v2.py`

- **Language:** python
- **Chunks:** 8

## Symbols

### class: `FuncInfo`
- Line: 17

class FuncInfo:

### function: `find_large`
- Line: 25

def find_large(min_lines):

### function: `already_done`
- Line: 49

def already_done():

### function: `ollama_refactor`
- Line: 61

def ollama_refactor(fi, model):

### function: `apply_refactor`
- Line: 80

def apply_refactor(fi, nc):

### function: `worker`
- Line: 96

def worker(bid, funcs, model):

### function: `main`
- Line: 118

def main():

## Imports

```
ast
concurrent.futures.ThreadPoolExecutor
concurrent.futures.as_completed
dataclasses.dataclass
json
pathlib.Path
subprocess
time
```
