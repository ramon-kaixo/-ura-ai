# `core/guardián_disco.py`

- **Language:** python
- **Chunks:** 10

## Symbols

### function: `cargar_config`
- Line: 39

def cargar_config():

### function: `calcular_hash`
- Line: 50

def calcular_hash(ruta, truncar):
SHA-256 completo. Si truncar < 64, devuelve versión acortada.

### function: `escanear`
- Line: 56

def escanear(config):
Escanea todos los archivos según patrones configurados.

### function: `comparar`
- Line: 72

def comparar(anterior, actual):
Compara snapshot anterior vs estado actual del disco.

### function: `verificar_escritura`
- Line: 86

def verificar_escritura(archivo, hash_esperado, config):
¿El archivo realmente se escribió en disco?
Compara el hash post-escritura con el hash que la IA dice haber generado.

Returns:
    True si el archivo existe y el hash coincide.
    False si: archivo no existe (FANTASMA) o hash no coincide (corrupto).

### function: `guardar_snapshot`
- Line: 103

def guardar_snapshot(data):
Escritura atómica: temp + rename.

### function: `guardar_historial`
- Line: 111

def guardar_historial(cambios, total):
Añade entrada al historial JSON Lines.

### function: `main`
- Line: 128

def main():

## Module Overview

Guardián de Disco — Detección de cambios vía SHA-256 con verificación post-escritura.

📖 MANUAL DE USO RÁPIDO:
  python3 core/guardián_disco.py --scan              # Escanear y comparar con snapshot
  python3 core/guardián_disco.py --verify <f> <hash>  # Verificar que un archivo se escribió
  python3 core/guardián_disco.py --init               # Crear snapshot inicial

🔒 GARANTÍAS:
  - Hash SHA-256 completo (64 chars, sin truncar)
  - Escritura atómica del snapshot (temp + rename)
  - Historial en .nervioso/hashes_history.jsonl
  - Verificación post-escritura: ¿el LLM realmente escribió?
  - Detecta código fantasma (archivo en snapshot pero no en disco)
  - Escanea *.py, *.json, *.sh, *.yaml, *.yml, *.md, *.env

## Imports

```
argparse
hashlib
json
pathlib.Path
sys
time
```
