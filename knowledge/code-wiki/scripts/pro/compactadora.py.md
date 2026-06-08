# `scripts/pro/compactadora.py`

- **Language:** python
- **Chunks:** 12

## Symbols

### function: `parse_metadata`
- Line: 27

def parse_metadata(ruta):
Lee el metadata generado por el Fragmentador.

### function: `extraer_chincheta`
- Line: 32

def extraer_chincheta(codigo):
Extrae la chincheta única del código original vía AST.

Returns:
    (start_line, end_line, nombre_funcion)

### function: `validar_contabilidad`
- Line: 47

def validar_contabilidad(metadata, codigo_original, codigo_nuevo, tolerancia):
Verifica que la contabilidad de tokens cuadre.

tokens_esperados = tokens_in - tokens_removed + tokens_added

### function: `inyeccion_quirurgica`
- Line: 82

def inyeccion_quirurgica(original, start_line, end_line, nuevo_codigo):
Reemplazo quirúrgico: backward splicing desde la chincheta.

Args:
    original: Código fuente completo.
    start_line: Línea de inicio de la función (1-indexed).
    end_line: Línea de fin de la función (1-indexed) — la chincheta.
    nuevo_codigo: Código refactorizado.

Returns:
    Código completo con la función reemplazada.

### function: `verificar_compile`
- Line: 111

def verificar_compile(codigo, nombre):
Verifica que el código compile sin errores.

### function: `verificar_firma_ast`
- Line: 120

def verificar_firma_ast(codigo_original, codigo_final):
Verifica que las firmas de funciones se mantengan (AST Diff).

### function: `verificar_mapa_cromatico`
- Line: 148

def verificar_mapa_cromatico(mapa, codigo_original, codigo_final):
Verifica que el mapa cromático se mantenga tras el refactor.

🔴 Rojas: deben coincidir en número (mismas instrucciones lógicas)
🟢 Verdes: los gaps se reconstruyen después, no se verifican aquí

Returns:
    (ok, mensaje)

### function: `compactar`
- Line: 200

def compactar(ruta_original, ruta_nuevo_codigo, metadata, dry_run, mapa_cromatico):
Ejecuta el pipeline completo de compactación.

Args:
    ruta_original: Archivo original.
    ruta_nuevo_codigo: Código refactorizado (solo la función).
    metadata: Metadata del fragmentador.
    dry_run: Si True, no escribe el archivo.

Returns:
    Dict con resultado del proceso.

### function: `scan_project`
- Line: 286

def scan_project():

### function: `main`
- Line: 292

def main():

## Module Overview

Compactadora Determinista — Reintegra código refactorizado.

Principios:
  1. CONTABILIDAD: cada línea entrante = línea saliente.
     Si entran 300 líneas y salen 320, hay 20 líginas que justificar.
  2. VERIFICACIÓN: AST válido, tokens coherentes, mapa cromático.
  3. DRY-RUN: validación sin escritura.

## Imports

```
argparse
ast
json
pathlib.Path
shutil
subprocess
sys
```
