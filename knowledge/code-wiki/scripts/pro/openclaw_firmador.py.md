# `scripts/pro/openclaw_firmador.py`

- **Language:** python
- **Chunks:** 21

## Symbols

### function: `sign`
- Line: 31

def sign(file_path):
Firma un archivo con BLAKE2b (8 bytes). Retorna hex digest.

### function: `sign_content`
- Line: 41

def sign_content(content):
Firma contenido en memoria (sin leer disco).

### function: `load_index`
- Line: 50

def load_index(force_reload):
Carga .nervioso/sistema_map.json en memoria (cacheado).
Single-Pass: primera llamada carga, siguientes devuelven cache.
Si el archivo cambio en disco → recarga automatica.

### function: `get_node`
- Line: 69

def get_node(rel_path):
Obtiene el nodo del grafo para una ruta relativa.

### function: `is_master`
- Line: 75

def is_master(rel_path):
Verifica si el archivo es el nodo maestro (no duplicado).

### function: `is_zombie`
- Line: 81

def is_zombie(rel_path):
Verifica si el archivo es un zombie (sin imports).

### function: `is_duplicate`
- Line: 89

def is_duplicate(rel_path):
Verifica si el archivo es un duplicado de otro.

### function: `validate_invariant`
- Line: 97

def validate_invariant(file_path, content):
Predicado: HASH(archivo) == HASH_INDEXADO.
Si content no es None → firma en memoria (Single-Pass, sin leer disco).
Si content es None → firma desde disco.

### function: `validate_and_abort`
- Line: 118

def validate_and_abort(file_path, worker_pid):
Valida invariante. Si falla → ABORTAJE DE EMERGENCIA.

### function: `update_index_node`
- Line: 128

def update_index_node(rel_path, new_hash, new_size):
Actualiza el hash y size de un nodo en el index (post-modificacion).

### function: `_abortaje_emergencia`
- Line: 149

def _abortaje_emergencia(motivo, worker_pid):
Protocolo de mitigacion atomico.

### function: `sign_and_verify_write`
- Line: 184

def sign_and_verify_write(file_path, new_content):
Single-Pass: firma el contenido nuevo, verifica contra index, escribe a disco.
Retorna (ok, firma).

### function: `sign_and_verify_write_bytes`
- Line: 206

def sign_and_verify_write_bytes(file_path, new_content):
Version simplificada: solo retorna True/False.

### function: `checkpoint_update`
- Line: 215

def checkpoint_update(rel_path, line, total_lines, worker_id):
Actualiza la marca de agua en .nervioso/sistema_map.json.
Registra la ultima linea procesada, total, timestamp, worker y estado.

### function: `checkpoint_get`
- Line: 239

def checkpoint_get(rel_path):
Obtiene los datos de checkpoint de un archivo.

### function: `reportar_estado_tierra`
- Line: 253

def reportar_estado_tierra():
Informe de Situacion: progreso del tunel, archivos pendientes, riesgos.

### function: `delta_snapshot`
- Line: 316

def delta_snapshot(label):
Guarda snapshot de hashes actuales para comparacion futura.

### function: `delta_check`
- Line: 342

def delta_check(label):
Compara sistema_map.json actual contra un snapshot anterior.
Retorna (modificados, nuevos, eliminados).
Solo archivos con hash diferente → necesitan re-procesarse.

### function: `aplicar_delta_check`
- Line: 384

def aplicar_delta_check():
Ejecuta delta check completo y retorna resumen.

## Module Overview

openclaw_firmador.py — Agente-Firmador BLAKE2b (Protocolo de Control de Inodos).

Principios:
  1. FIRMA: Toda modificacion de archivo genera firma BLAKE2b (digest_size=8)
  2. SINGLE-PASS: La verificacion se hace en el mismo flujo de lectura (cero latencia)
  3. NOTARIO: El Guardian valida HASH(archivo) == HASH_INDEXADO contra .nervioso/
  4. ABORTAJE: Si la invariante falla → SIGKILL + git checkout . + .refactor_blocked
  5. MAESTRO: Solo se opera sobre is_master:true. Duplicados y zombies ignorados.

Uso:
  from openclaw_firmador import sign, verify, load_index, validate_invariant

## Imports

```
contextlib
datetime.datetime
hashlib
json
os
pathlib.Path
subprocess
time
typing.Any
```
