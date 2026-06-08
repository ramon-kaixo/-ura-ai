# `scripts/pro/inspectores.py`

- **Language:** python
- **Chunks:** 24

## Symbols

### class: `CheckResult`
- Line: 59

class CheckResult:
Methods: __init__, to_dict

### class: `Inspector`
- Line: 85

class Inspector:
Base class para inspectores.
Methods: __init__, ejecutar

### class: `AgregadorInspecciones`
- Line: 467

class AgregadorInspecciones:
Consolida resultados de 10 inspectores y gestiona watermarks.
Methods: __init__, agregar, total_checks, total_fallos, total_passed, fallos_por_tipo, guardar_watermarks, decidir_accion, reporte

### function: `leer_codigo`
- Line: 44

def leer_codigo(ruta):

### function: `generar_id_watermark`
- Line: 51

def generar_id_watermark(tipo):

### function: `check_compile`
- Line: 107

def check_compile(codigo, lineas, arbol):
Check 1: El código compila sin errores.

### function: `check_triple_quotes`
- Line: 116

def check_triple_quotes(codigo, lineas, arbol):
Check 2: No hay triples comillas mal cerradas (solo si compile() falló).

### function: `check_git_artifacts`
- Line: 122

def check_git_artifacts(codigo, lineas, arbol):
Check 3: No hay residuos de git/LLM.

### function: `_buscar_ruff`
- Line: 138

def _buscar_ruff():
Busca el binario de ruff en ubicaciones conocidas.

### function: `check_f821`
- Line: 152

def check_f821(codigo, lineas, arbol):
Check 4: Fuga de referencias (F821).

### function: `check_dangling_blocks`
- Line: 204

def check_dangling_blocks(codigo, lineas, arbol):
Check 5: Bloques huérfanos (try/except/with/if sin cuerpo).

### function: `check_empty_body`
- Line: 214

def check_empty_body(codigo, lineas, arbol):
Check 6: Densidad lógica nula (solo pass/return None).

### function: `check_tipado`
- Line: 231

def check_tipado(codigo, lineas, arbol):
Check 7: Inconsistencias de tipado.

### function: `check_large_functions`
- Line: 248

def check_large_functions(codigo, lineas, arbol):
Check 8: Funciones demasiado grandes.

### function: `check_nesting_depth`
- Line: 258

def check_nesting_depth(codigo, lineas, arbol):
Check 9: Anidamiento excesivo.

### function: `_max_nesting`
- Line: 268

def _max_nesting(node, depth):

### function: `check_debug_code`
- Line: 276

def check_debug_code(codigo, lineas, arbol):
Check 10: Código de debug/residual.

### function: `check_security`
- Line: 287

def check_security(codigo, lineas, arbol):
Check 11: Prácticas inseguras.

### function: `check_circular_imports`
- Line: 304

def check_circular_imports(codigo, lineas, arbol):
Check 12: Potenciales imports circulares.

### function: `crear_inspectores`
- Line: 319

def crear_inspectores():

### function: `inspeccionar`
- Line: 573

def inspeccionar(ruta):
Ejecuta los 10 inspectores en paralelo sobre un archivo.

### function: `scan_project`
- Line: 601

def scan_project():
Escanear todo el proyecto.

### function: `main`
- Line: 617

def main():

## Imports

```
argparse
ast
collections.abc.Callable
concurrent.futures.ThreadPoolExecutor
concurrent.futures.as_completed
contextlib
json
os
pathlib.Path
re
shutil
subprocess
sys
time
```
