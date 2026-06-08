# `scripts/pro/refactor_large_functions.py`

- **Language:** python
- **Chunks:** 12

## Symbols

### function: `_ajustar_contexto`
- Line: 37

def _ajustar_contexto(tokens_funcion, max_modelo, factor):
Ajusta num_predict dinámicamente para acelerar inferencia.

### function: `_estimar_tokens`
- Line: 43

def _estimar_tokens(codigo):

### function: `log`
- Line: 45

def log(msg):

### function: `llm`
- Line: 49

def llm(prompt, model):

### function: `is_excluded`
- Line: 70

def is_excluded(path):

### function: `get_large_functions`
- Line: 75

def get_large_functions(threshold):

### function: `clean_llm_response`
- Line: 101

def clean_llm_response(text):

### function: `build_refactor_prompt`
- Line: 108

def build_refactor_prompt(func_name, func_source, n_lines):
Prompt de 6 capas (Identidad, Contexto, Objetivo, Restricciones, Formato, Verificacion).

### function: `apply_refactored`
- Line: 145

def apply_refactored(file_path, lineno, end_lineno, new_code):

### function: `main`
- Line: 212

def main():

## Module Overview

Refactoriza funciones grandes (>80 líneas) usando LLM vía Ollama.

Flujo:
  1. Detecta funciones grandes vía AST
  2. Por cada una, envía al LLM pidiendo dividir en funciones más pequeñas
  3. Aplica el cambio, verifica sintaxis, ejecuta ruff fix

## Imports

```
ast
json
os
pathlib.Path
re
shutil
subprocess
time
urllib.request
```
