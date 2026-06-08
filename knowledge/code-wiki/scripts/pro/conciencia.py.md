# `scripts/pro/conciencia.py`

- **Language:** python
- **Chunks:** 13

## Symbols

### function: `cargar`
- Line: 49

def cargar():

### function: `_nuevo`
- Line: 62

def _nuevo():

### function: `guardar`
- Line: 80

def guardar(data):
Guarda con fcntl lock + escritura atomica. 0% race conditions.

### function: `escribir_proceso`
- Line: 94

def escribir_proceso(nombre, estado, detalles):
Registra el estado de un proceso.

### function: `registrar_error`
- Line: 105

def registrar_error(nivel, mensaje):
Registra un error y ajusta el nivel global.

### function: `registrar_arreglo`
- Line: 124

def registrar_arreglo(descripcion):
Registra un arreglo aplicado.

### function: `actualizar_progreso`
- Line: 140

def actualizar_progreso(archivo, ciclo, progreso):
Actualiza el contexto de progreso.

### function: `reset_ciclo`
- Line: 153

def reset_ciclo():
Reinicia para nuevo ciclo.

### function: `estado`
- Line: 159

def estado():
Devuelve el estado consolidado.

### function: `scan_project`
- Line: 189

def scan_project():

### function: `main`
- Line: 195

def main():

## Module Overview

Conciencia Unificada — Memoria global de todos los procesos del pipeline.

📖 MANUAL DE USO RÁPIDO:
  python3 conciencia.py --leer                          # Ver estado general
  python3 conciencia.py --escribir refactorer activo    # Actualizar proceso
  python3 conciencia.py --error 1 "F821 detectado"      # Registrar error (1=leve,2=crítico)
  python3 conciencia.py --progreso 67/107               # Actualizar progreso
  python3 conciencia.py --reset                         # Reiniciar para nuevo ciclo

🔒 GARANTÍAS:
  - 1 archivo JSON = 1 punto de verdad (.nervioso/conciencia.json)
  - Thread-safe: lock file para evitar corrupción por escrituras simultáneas
  - Memory-safe: arrays acotados a 50 entradas máx
  - Nivel de error global (0=OK, 1=LEVE, 2=CRÍTICO) visible de un vistazo
  - Si un proceso muere, otro puede retomar su estado desde el mismo archivo

Un solo archivo JSON (.nervioso/conciencia.json) que da "consciencia"
a cada proceso del pipeline: saben dónde están, qué hicieron y qué falta.

Principios:
  - 1 archivo = 1 punto de verdad
  - Todos los procesos leen/escriben el mismo archivo
  - Nivel de error global visible de un vistazo
  - Si un proceso muere, otro puede retomar su estado
  - Contexto nunca se pierde entre ciclos

## Imports

```
argparse
fcntl
json
os
pathlib.Path
time
```
