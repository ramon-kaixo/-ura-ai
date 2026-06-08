# `scripts/pro/sandbox_industrial.py`

- **Language:** python
- **Chunks:** 55

## Symbols

### function: `log`
- Line: 63

def log(msg):

### function: `_get_ssh_command_output`
- Line: 67

def _get_ssh_command_output(command, timeout):
Ejecuta una comando SSH y devuelve la salida.

### function: `_get_free_memory_gx10`
- Line: 76

def _get_free_memory_gx10():
Obtiene el uso de memoria en GB del servidor GX10 a través de SSH.

### function: `_get_local_memory_usage`
- Line: 92

def _get_local_memory_usage():
Obtiene el uso de memoria en GB localmente.

### function: `_get_total_memory_usage`
- Line: 101

def _get_total_memory_usage():
Obtiene el uso total de memoria en GB.

### function: `_calculate_free_memory`
- Line: 109

def _calculate_free_memory(ram_total):
Calcula la memoria libre en GB.

### function: `_determine_worker_count`
- Line: 114

def _determine_worker_count(free_memory):
Determina el número de workers basado en la memoria libre.

### function: `auto_workers`
- Line: 129

def auto_workers():
Escala dinámico: a más RAM libre, más workers.

### function: `_get_natural_breaks`
- Line: 136

def _get_natural_breaks(file_path):

### function: `_verify_compile`
- Line: 162

def _verify_compile(code, file_path):

### function: `_clean_response`
- Line: 171

def _clean_response(text):

### function: `_llm`
- Line: 178

def _llm(prompt, model, num_predict):

### function: `chunk_file`
- Line: 212

def chunk_file(file_path):

### function: `detect_indent`
- Line: 256

def detect_indent(text):
Indentación base del bloque (mínima indentación de líneas no vacías).

### function: `inject_coord_tag`
- Line: 272

def inject_coord_tag(code, idx, total, indent):
Precede el chunk con una etiqueta de coordenadas para costura posterior.

### function: `strip_coord_tags`
- Line: 278

def strip_coord_tags(text):

### function: `build_cleaner_prompt`
- Line: 282

def build_cleaner_prompt(chunk, rel_path, total):

### function: `build_refactorer_prompt`
- Line: 304

def build_refactorer_prompt(code, rel_path, chunk_n, total, indent):

### function: `run_cleaner`
- Line: 323

def run_cleaner(chunk, rel_path, total):

### function: `run_refactorer`
- Line: 338

def run_refactorer(cleaned_chunk, rel_path, total):

### function: `helper1`
- Line: 365

def helper1(file_path):

### function: `helper2`
- Line: 374

def helper2(data):

### function: `helper3`
- Line: 388

def helper3(data):

### function: `helper4`
- Line: 395

def helper4(data):

### function: `_ejecutar_ruff_check`
- Line: 401

def _ejecutar_ruff_check(sandbox_file_path):

### function: `_ejecutar_ruff_format`
- Line: 413

def _ejecutar_ruff_format(sandbox_file_path):

### function: `_ejecutar_py_compile`
- Line: 417

def _ejecutar_py_compile(sandbox_file_path):

### function: `_verificar_compilacion`
- Line: 428

def _verificar_compilacion(code_content, sandbox_file_path):

### function: `_procesar_resultados`
- Line: 434

def _procesar_resultados(pyc_ok, compile_ok, sandbox_file_path, sandbox_file_path_bak, CHUNKS_FAILED, FILES_FAILED):

### function: `_inyectar_en_repo_real`
- Line: 452

def _inyectar_en_repo_real(sandbox_file_path, path):

### function: `_leer_archivo`
- Line: 460

def _leer_archivo(file_path):

### function: `_escribir_log`
- Line: 466

def _escribir_log(mensaje):

### function: `_actualizar_contadores`
- Line: 470

def _actualizar_contadores(chunks_inyectados, archivos_procesados):

### function: `_ejecutar_ruff_check`
- Line: 476

def _ejecutar_ruff_check(sandbox_file_path):

### function: `_ejecutar_ruff_format`
- Line: 484

def _ejecutar_ruff_format(sandbox_file_path):

### function: `_ejecutar_py_compile`
- Line: 492

def _ejecutar_py_compile(sandbox_file_path):

### function: `_verificar_compilacion`
- Line: 505

def _verificar_compilacion(code, file_path):

### function: `_inyectar_en_repo_real`
- Line: 514

def _inyectar_en_repo_real(sandbox_file_path, path):

### function: `_revisar_ruff_ultimo`
- Line: 519

def _revisar_ruff_ultimo(original_path):

### function: `process_sandbox`
- Line: 532

def process_sandbox(sandbox_file_path, sandbox_file_path_bak, path, total, CHUNKS_FAILED, FILES_FAILED):

### function: `_verificar_argumentos`
- Line: 560

def _verificar_argumentos(targets):

### function: `_procesar_monsters`
- Line: 567

def _procesar_monsters(targets):

### function: `_leer_archivo`
- Line: 573

def _leer_archivo(file_path):

### function: `_escribir_log`
- Line: 578

def _escribir_log(message):

### function: `_actualizar_contadores`
- Line: 582

def _actualizar_contadores(chunks_done, chunks_failed):

### function: `_procesar_archivo`
- Line: 588

def _procesar_archivo(file_path):

### function: `_tratar_error`
- Line: 594

def _tratar_error(file_path, error):

### function: `sandbox_file`
- Line: 603

def sandbox_file(file_path):

### function: `main`
- Line: 611

def main():

### function: `_calcular_totales`
- Line: 636

def _calcular_totales():

### function: `_log_formato`
- Line: 640

def _log_formato(tiempo_total, archivos_ok, archivos_fallidos, chunks_ok, chunks_fallidos):

### function: `_ejecutar_sandbox`
- Line: 649

def _ejecutar_sandbox(t):

### function: `_registrar_tiempo_final`
- Line: 660

def _registrar_tiempo_final(start, elapsed):

## Module Overview

Sandbox Industrial — Aislamiento total para reescritura masiva de archivos monstruo.

Arquitectura:
  1. Copia del archivo a /tmp/sandbox_industrial/ (RAM, sin tocar repo real)
  2. Chunking en ~60l con límites naturales (funciones/clases/líneas en blanco)
  3. Marcado de coordenadas: cada chunk lleva índice + indentación padre
  4. Limpieza en paralelo (qwen2.5:7b) — elimina paja, comentarios, logs
  5. Reescritura en paralelo (qwen2.5:7b) — funciones 15-30l, indentación forzada
  6. Costura láser por coordenadas: ordena, alinea indentación, borra tags
  7. Aduana de calidad: ruff --fix + py_compile + compile() en la sandbox
  8. Inyección al repo real SOLO si 100% de checks pasan

Uso:
  python scripts/pro/sandbox_industrial.py core/central_router.py
  python scripts/pro/sandbox_industrial.py --monsters
  DRY_RUN=1 SANDBOX_CHUNK=40 SANDBOX_WORKERS=8 python scripts/pro/sandbox_industrial.py --monsters

## Imports

```
ast
json
os
pathlib.Path
psutil.virtual_memory
re
scripts.utils.verify_compile
shutil
subprocess
sys
time
traceback
urllib.request
```
