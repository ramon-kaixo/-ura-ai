# `scripts/pro/poda_mecanica.py`

- **Language:** python
- **Chunks:** 9

## Symbols

### function: `buscar_ruff`
- Line: 37

def buscar_ruff():
Busca ruff en ubicaciones conocidas.

### function: `eliminar_comentarios_no_docstring`
- Line: 50

def eliminar_comentarios_no_docstring(codigo):
Elimina comentarios de línea (#) que NO sean parte de docstrings.

Returns:
    (codigo_limpio, lineas_eliminadas)

### function: `_encontrar_comentario`
- Line: 108

def _encontrar_comentario(linea):
Encuentra la posición del primer # que NO esté dentro de una cadena.

### function: `poda_mecanica`
- Line: 128

def poda_mecanica(ruta):
Ejecuta la poda completa: ruff F841/F401/F811 + strip comentarios.

Returns:
    (codigo_podado, chars_original, chars_podado, lineas_comentarios)

### function: `anclaje_cromatico`
- Line: 166

def anclaje_cromatico(codigo):
Genera mapa cromático 🔴🟢 del código limpio.

🔴 Roja: end_line de cada instrucción lógica (función, clase, asignación)
🟢 Verde: gaps entre bloques (líneas en blanco, indentación)

Returns:
    Dict con el mapa cromático.

### function: `pipeline_poda`
- Line: 239

def pipeline_poda(ruta, output_dir):
Ejecuta Poda Mecánica + Anclaje Cromático y guarda resultados.

Returns:
    Dict con resultados completos.

### function: `scan_project`
- Line: 296

def scan_project():
Escanear todo el proyecto.

### function: `main`
- Line: 313

def main():

## Imports

```
argparse
ast
json
os
pathlib.Path
shutil
subprocess
sys
tempfile
```
