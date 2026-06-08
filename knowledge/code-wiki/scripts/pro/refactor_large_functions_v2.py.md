# `scripts/pro/refactor_large_functions_v2.py`

- **Language:** python
- **Chunks:** 15

## Symbols

### function: `_ajustar_contexto`
- Line: 49

def _ajustar_contexto(tokens_funcion, max_modelo, factor):

### function: `_estimar_tokens`
- Line: 63

def _estimar_tokens(codigo):

### function: `log`
- Line: 67

def log(msg):

### function: `_ollama_request`
- Line: 71

def _ollama_request(url, payload):
Envía request a Ollama/router. Retorna respuesta JSON o dict vacío.

### function: `llm`
- Line: 82

def llm(prompt, model):
Llama al LLM vía model_router para temperatura optimizada por modelo.

El router (puerto 11435) inyecta temperatura específica por arquitectura:
- Qwen 14B (LLaMA/RoPE): temperatura 0.0 para refactor preciso
- DeepSeek 6.7B (GPT): temperatura 0.2 para equilibrio creatividad/precisión
- Qwen 32B: temperatura 0.1 para código complejo

Si el router no está disponible, cae directo a Ollama con temperatura 0.1.

### function: `is_excluded`
- Line: 122

def is_excluded(path):

### function: `get_large_functions`
- Line: 135

def get_large_functions(threshold):

### function: `clean_llm_response`
- Line: 163

def clean_llm_response(text):

### function: `build_refactor_prompt`
- Line: 170

def build_refactor_prompt(func_name, func_source, n_lines):

### function: `apply_refactored`
- Line: 206

def apply_refactored(file_path, lineno, end_lineno, new_code):

### function: `refactor_one`
- Line: 271

def refactor_one(func):
Refactoriza una funcion con compactacion.

### function: `scan_project`
- Line: 328

def scan_project():

### function: `main`
- Line: 334

def main():

## Module Overview

Refactoriza funciones grandes (>80 lineas) usando LLM con COMPACTACION.

Flujo:
  1. Detecta funciones grandes via AST
  2. COMPACTA: quita comentarios, docstrings, lineas en blanco (-25-30% tokens)
  3. Envia al LLM pidiendo dividir en funciones mas pequenas
  4. DESCOMPACTA: restaura huecos usando mapa de anchors
  5. Aplica el cambio, verifica sintaxis, ejecuta ruff fix

## Imports

```
argparse
ast
compactador_espacios.compactar
compactador_espacios.descompactar
json
os
pathlib.Path
re
shutil
subprocess
sys
time
urllib.request
```
