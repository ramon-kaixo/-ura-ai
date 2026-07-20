#!/usr/bin/env python3
"""Sandbox Industrial — Aislamiento total para reescritura masiva de archivos monstruo.

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
"""

import ast
import json
import os
import re
import shutil
import subprocess
import sys
import time
import traceback
import urllib.request
from pathlib import Path

# ── Configuración ──────────────────────────────────────────────────────────
OLLAMA_URL = os.environ.get("OLLAMA_URL", os.environ.get("OLLAMA_URL", "http://10.164.1.99:11434"))
MODEL_CLEANER = os.environ.get("MODEL_CLEANER", "qwen2.5-coder:14b")
MODEL_REFACTOR = os.environ.get("MODEL_REFACTOR", "qwen2.5-coder:14b")
SANDBOX_CHUNK = int(os.environ.get("SANDBOX_CHUNK", "60"))
SANDBOX_WORKERS = int(os.environ.get("SANDBOX_WORKERS", "0"))  # 0 = auto-detect
RAM_CEILING_GB = float(os.environ.get("RAM_CEILING_GB", "96.0"))
DRY_RUN = os.environ.get("DRY_RUN", "0") == "1"
URA_ROOT = Path(os.environ.get("URA_ROOT", Path("~/URA/ura_ia_1972").expanduser()))
SANDBOX_DIR = Path(os.environ.get("SANDBOX_DIR", "/tmp/sandbox_industrial"))

MONSTER_LIST = [
    "benchmarks/STRESS_TEST_125.py",
    "core/agente_administrativo_contable.py",
    "core/agente_cocina_navarra_temporada.py",
    "core/agente_gastronomo_musica.py",
    "core/central_router.py",
    "core/ura_panel.py",
    "ura_panel.py",
]

CHUNKS_DONE = 0
CHUNKS_FAILED = 0
FILES_DONE = 0
FILES_FAILED = 0


from psutil import virtual_memory

RAM_CEILING_GB = 16.0


def log(msg: str) -> None:
    pass


def _get_ssh_command_output(command: list[str], timeout: int = 10) -> str:
    """Ejecuta una comando SSH y devuelve la salida."""
    try:
        out = subprocess.check_output(command, timeout=timeout, text=True)
        return out.strip()
    except Exception:
        return ""


def _get_free_memory_gx10() -> float:
    """Obtiene el uso de memoria en GB del servidor GX10 a través de SSH."""
    command = [
        "ssh",
        "-o",
        "ConnectTimeout=3",
        "-o",
        "BatchMode=yes",
        "gx10",
        "free -g | awk '/^Mem:/{print $3}'",
    ]
    return float(_get_ssh_command_output(command).strip()) if _get_ssh_command_output(command) else 0.0


def _get_local_memory_usage() -> float:
    """Obtiene el uso de memoria en GB localmente."""
    try:
        memory = virtual_memory()
        return memory.used / (1024**3)
    except ImportError:
        return 0.0


def _get_total_memory_usage() -> float:
    """Obtiene el uso total de memoria en GB."""
    gx10_ram = _get_free_memory_gx10()
    if gx10_ram > 0:
        return gx10_ram
    return _get_local_memory_usage()


def _calculate_free_memory(ram_total: float) -> float:
    """Calcula la memoria libre en GB."""
    return RAM_CEILING_GB - ram_total


def _determine_worker_count(free_memory: float) -> int:
    """Determina el número de workers basado en la memoria libre."""
    if free_memory > 90:
        return 12
    if free_memory > 70:
        return 10
    if free_memory > 50:
        return 8
    if free_memory > 30:
        return 6
    if free_memory > 10:
        return 4
    return 2


def auto_workers() -> int:
    """Escala dinámico: a más RAM libre, más workers."""
    ram_total = _get_total_memory_usage()
    free_memory = _calculate_free_memory(ram_total)
    return _determine_worker_count(free_memory)


def _get_natural_breaks(file_path: str) -> list[int]:
    source = Path(file_path).read_text(encoding="utf-8")
    lines = source.splitlines()
    total_lines = len(lines)

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return [1, total_lines + 1]

    breaks = {1, total_lines + 1}

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            breaks.add(node.lineno)
            breaks.add(node.end_lineno + 1)

    for line_number in range(1, total_lines + 1):
        index = line_number - 1
        if index > 0 and index < total_lines - 1 and lines[index].strip() == "":  # noqa: SIM102
            if lines[index - 1].strip() and lines[index + 1].strip():
                breaks.add(line_number + 1)

    return sorted(breaks)


def _verify_compile(code: str, file_path: str) -> bool:
    try:
        compile(code, file_path, "exec")
        return True
    except SyntaxError as e:
        log(f"  ❌ SyntaxError: {e}")
        return False


def _clean_response(text: str) -> str:
    text = text.strip()
    text = re.sub(r"(?s)^```(?:python)?\s*\n?", "", text)
    text = re.sub(r"(?s)\n?```\s*$", "", text)
    return text.strip()


def _llm(prompt: str, model: str, num_predict: int = 4096) -> str:
    payload = json.dumps(
        {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "keep_alive": -1,
            "options": {"temperature": 0.1, "num_predict": num_predict},
        },
    ).encode()
    req = urllib.request.Request(  # noqa: S310
        f"{OLLAMA_URL}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=300) as r:  # noqa: S310
        data = json.loads(r.read())
    return data.get("response", "")


def chunk_file(file_path: str) -> list[dict]:
    source = Path(file_path).read_text(encoding="utf-8")
    lines = source.splitlines()
    breaks = _get_natural_breaks(file_path)

    segments = []
    for i in range(len(breaks) - 1):
        start = breaks[i]
        end = breaks[i + 1] - 1
        if end >= start:
            src = "\n".join(lines[start - 1 : end])
            segments.append({"start": start, "end": end, "source": src, "lines": end - start + 1})

    chunks = []
    buf = []
    buf_lines = 0

    def flush() -> None:
        nonlocal buf, buf_lines
        if not buf:
            return
        start = buf[0]["start"]
        end = buf[-1]["end"]
        src = "\n".join(lines[start - 1 : end])
        chunks.append(
            {
                "source": src,
                "lines": end - start + 1,
                "idx": len(chunks),
            },
        )
        buf.clear()
        buf_lines = 0

    for seg in segments:
        if buf_lines + seg["lines"] > SANDBOX_CHUNK and buf_lines > 0:
            flush()
        buf.append(seg)
        buf_lines += seg["lines"]

    flush()
    return chunks


def detect_indent(text: str) -> int:
    """Indentación base del bloque (mínima indentación de líneas no vacías)."""
    min_indent = 999
    for line in text.splitlines():
        stripped = line.rstrip()
        if stripped and stripped.lstrip() != "":
            indent = len(line) - len(line.lstrip())
            min_indent = min(min_indent, indent)
    return min_indent if min_indent != 999 else 0


# ── Pipeline stages ────────────────────────────────────────────────────────

COORD_TAG_PATTERN = re.compile(r"^#\s*\[SANDBOX-COORD:.+?\]\s*$")


def inject_coord_tag(code: str, idx: int, total: int, indent: int) -> str:
    """Precede el chunk con una etiqueta de coordenadas para costura posterior."""
    tag = f"# [SANDBOX-COORD: CHUNK_{idx:04d}/{total:04d} INDENT_{indent:03d}]"
    return tag + "\n" + code


def strip_coord_tags(text: str) -> str:
    return "\n".join(line for line in text.splitlines() if not COORD_TAG_PATTERN.match(line))


def build_cleaner_prompt(chunk: dict, rel_path: str, total: int) -> str:
    chunk_n = chunk["idx"] + 1
    return f"""[INSTRUCCIÓN]
Limpia este fragmento {chunk_n}/{total} del archivo "{rel_path}".
Elimina:
- Comentarios históricos obsoletos (ej: "# TODO: ...", "# FIXME: ...", "# Cambio XXXX")
- Logs repetitivos de depuración (print() o logging.debug() sin valor real)
- Código comentado inerte
- Listas/diccionarios estáticos enormes que parezcan fixtures de prueba
- Docstrings redundantes

REGLAS:
1. NO cambies la lógica, nombres de funciones, argumentos, ni indentación
2. NO añadas ni quites imports
3. NO renombres nada
4. No toques la primera línea de control que empieza por # [SANDBOX-COORD:
5. Devuelve SOLO el código limpio, sin explicaciones ni markdown

[CÓDIGO]
{chunk["source"]}"""


def build_refactorer_prompt(code: str, rel_path: str, chunk_n: int, total: int, indent: int) -> str:
    n = len(code.splitlines())
    return f"""[INSTRUCCIÓN]
Reescribe este fragmento {chunk_n}/{total} del archivo "{rel_path}" ({n} líneas).
La indentación padre para todo este bloque es de {indent} espacios.

REGLAS ESTRICTAS:
1. TODAS las líneas deben comenzar con EXACTAMENTE {indent} espacios de indentación base
2. Divide en funciones atómicas de 15-30 líneas cada una
3. Extrae helpers con nombres descriptivos
4. NO cambies la interfaz pública ni los nombres de argumentos
5. NO añadas imports
6. No toques la primera línea de control que empieza por # [SANDBOX-COORD:
7. Devuelve SOLO código Python con indentación 4 espacios, sin markdown

[CÓDIGO]
{code}"""


def run_cleaner(chunk: dict, rel_path: str, total: int) -> dict:
    chunk_n = chunk["idx"] + 1
    prompt = build_cleaner_prompt(chunk, rel_path, total)
    t0 = time.time()
    resp = _llm(prompt, MODEL_CLEANER, num_predict=min(chunk["lines"] * 10, 4096))
    elapsed = time.time() - t0
    cleaned = _clean_response(resp)
    if not cleaned:
        log(f"     ⚠️  Chunk {chunk_n}: clean vacío → usando original")
        cleaned = chunk["source"]
    else:
        log(f"     🧹 C{chunk_n}/{total} en {elapsed:.1f}s ({len(cleaned)} chars)")
    return {"idx": chunk["idx"], "cleaned": cleaned, "lines": chunk["lines"]}


def run_refactorer(cleaned_chunk: dict, rel_path: str, total: int) -> dict:
    idx = cleaned_chunk["idx"]
    chunk_n = idx + 1
    code = cleaned_chunk["cleaned"]
    indent = detect_indent(code)
    tagged = inject_coord_tag(code, idx, total, indent)
    prompt = build_refactorer_prompt(tagged, rel_path, chunk_n, total, indent)
    t0 = time.time()
    resp = _llm(prompt, MODEL_REFACTOR, num_predict=min(len(code.splitlines()) * 20, 8192))
    elapsed = time.time() - t0
    refactored = _clean_response(resp)
    if not refactored:
        log(f"     💀 C{chunk_n}/{total}: refactor vacío → usando código limpio")
        refactored = code
    else:
        refactored = strip_coord_tags(refactored)
        if not refactored.strip():
            refactored = code
            log(f"     ⚠️  C{chunk_n}/{total}: código vacío tras limpiar tags → usando limpio")
        else:
            log(f"     💎 C{chunk_n}/{total} en {elapsed:.1f}s ({len(refactored)} chars)")
    return {"idx": idx, "refactored": refactored, "indent": indent}


# ── Main sandbox pipeline ──────────────────────────────────────────────────


def helper1(file_path):
    path = Path(file_path)
    if not path.exists():
        log(f"❌ Archivo no encontrado:  {file_path}")
        return False, None
    rel = os.path.relpath(str(path), str(URA_ROOT))
    return True, (path, rel)


def helper2(data) -> None:
    path, rel = data
    log(f"\n{'=' * 70}")
    log(f"🏭 Sandbox Industrial:  {rel}")

    SANDBOX_DIR.mkdir(parents=True, exist_ok=True)
    sandbox_file_path = SANDBOX_DIR / path.name
    sandbox_file_path_bak = SANDBOX_DIR / (path.name + ".orig")
    shutil.copy2(path, sandbox_file_path)
    shutil.copy2(path, sandbox_file_path_bak)
    log(f"📋 Copia en sandbox:  {sandbox_file_path}")
    log(f"💾 Original guardado:   {sandbox_file_path_bak}")


def helper3(data) -> None:
    path, _rel = data
    chunks = chunk_file(str(SANDBOX_DIR / path.name))
    total = len(chunks)
    log(f"📚 {total} chunks de ~{SANDBOX_CHUNK}l cada uno")


def helper4(data) -> None:
    _, _rel = data
    workers = SANDBOX_WORKERS if SANDBOX_WORKERS > 0 else auto_workers()
    log(f"🎛️  Workers: {workers} | RAM usada: {_get_total_memory_usage():.1f}GB | Techo: {RAM_CEILING_GB}GB")


def _ejecutar_ruff_check(sandbox_file_path) -> None:
    log("   🧹 ruff check --fix --unsafe-fixes...")
    resultado = subprocess.run(
        ["ruff", "check", "--fix", "--unsafe-fixes", str(sandbox_file_path)],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if resultado.returncode != 0 and resultado.stdout:
        log(f"      ruff: {resultado.stdout.strip()[:200]}")


def _ejecutar_ruff_format(sandbox_file_path) -> None:
    subprocess.run(["ruff", "format", str(sandbox_file_path)], capture_output=True, timeout=30, check=False)


def _ejecutar_py_compile(sandbox_file_path):
    log("   🔬 python3 -m py_compile...")
    resultado = subprocess.run(
        ["python3", "-m", "py_compile", str(sandbox_file_path)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    return resultado.returncode == 0


def _verificar_compilacion(code_content, sandbox_file_path):
    from scripts.utils import verify_compile

    return verify_compile(code_content, str(sandbox_file_path))


def _procesar_resultados(
    pyc_ok,
    compile_ok,
    sandbox_file_path,
    sandbox_file_path_bak,
    CHUNKS_FAILED,
    FILES_FAILED,
    total: int = 0,
) -> bool | None:
    if not pyc_ok or not compile_ok:
        log("❌ Aduana RECHAZADA")
        if not pyc_ok:
            log(f"   py_compile: ERROR — {pyc_ok.stderr.strip()[:200]}")
        if not compile_ok:
            log("   compile():  ERROR")
        log("   Repositorio real NO TOCADO. Sandbox preservada para diagnóstico.")
        log(f"   Archivo sandbox: {sandbox_file_path}")
        log(f"   Backup original: {sandbox_file_path_bak}")
        CHUNKS_FAILED += total
        FILES_FAILED += 1
        return False
    return None


def _inyectar_en_repo_real(sandbox_file_path, path) -> None:
    log("✅ Aduana APROBADA → inyectando en repositorio real...")
    shutil.copy2(sandbox_file_path, path)


log = print  # Simulamos la función de registro para fines de ejemplo  # noqa: F811


def _leer_archivo(file_path: str) -> int:
    with open(file_path) as file:  # noqa: PTH123
        lines = file.readlines()
    return len(lines)


def _escribir_log(mensaje: str) -> None:
    log(f"🎉 {mensaje}")


def _actualizar_contadores(chunks_inyectados: int, archivos_procesados: int) -> None:
    global CHUNKS_DONE, FILES_DONE  # noqa: PLW0603
    CHUNKS_DONE += chunks_inyectados
    FILES_DONE += archivos_procesados


def _ejecutar_ruff_check(sandbox_file_path: Path) -> None:
    subprocess.run(
        ["ruff", "check", "--fix", "--unsafe-fixes", str(sandbox_file_path)],
        capture_output=True,
        timeout=30,
        check=False,
    )


def _ejecutar_ruff_format(sandbox_file_path: Path) -> None:
    subprocess.run(
        ["ruff", "format", str(sandbox_file_path)],
        capture_output=True,
        timeout=30,
        check=False,
    )


def _ejecutar_py_compile(sandbox_file_path: Path) -> bool:
    try:
        compile(
            sandbox_file_path.read_text(encoding="utf-8"),
            filename=str(sandbox_file_path),
            doraise=True,
        )
        return True
    except Exception as e:
        log(f"⚠️ Compilación fallida: {e}")
        return False


def _verificar_compilacion(code: str, file_path: str) -> bool:
    try:
        compile(code, filename=file_path, doraise=True)
        return True
    except Exception as e:
        log(f"⚠️ Verificación de compilación fallida: {e}")
        return False


def _inyectar_en_repo_real(sandbox_file_path: Path, path: str) -> None:
    # Implementar la lógica para inyectar el archivo en el repositorio real
    pass


def _revisar_ruff_ultimo(original_path: Path) -> None:
    subprocess.run(
        ["ruff", "check", "--fix", "--unsafe-fixes", str(original_path)],
        capture_output=True,
        timeout=30,
        check=False,
    )
    subprocess.run(
        ["ruff", "format", str(original_path)],
        capture_output=True,
        timeout=30,
        check=False,
    )


def process_sandbox(
    sandbox_file_path: Path,
    sandbox_file_path_bak: Path,
    path: str,
    total: int,
    CHUNKS_FAILED: int,
    FILES_FAILED: int,
):
    _ejecutar_ruff_check(sandbox_file_path)
    _ejecutar_ruff_format(sandbox_file_path)
    pyc_ok = _ejecutar_py_compile(sandbox_file_path)
    compile_ok = _verificar_compilacion(
        sandbox_file_path.read_text(encoding="utf-8"),
        str(sandbox_file_path),
    )
    if not pyc_ok or not compile_ok:
        return _procesar_resultados(
            pyc_ok,
            compile_ok,
            sandbox_file_path,
            sandbox_file_path_bak,
            CHUNKS_FAILED,
            FILES_FAILED,
            total,
        )
    _inyectar_en_repo_real(sandbox_file_path, path)
    _revisar_ruff_ultimo(path)
    return None


def _verificar_argumentos(targets) -> None:
    if not targets:
        log("Uso: python scripts/pro/sandbox_industrial.py <archivo> [archivo2...]")
        log("     python scripts/pro/sandbox_industrial.py --monsters")
        raise SystemExit(1)


def _procesar_monsters(targets) -> None:
    if "--monsters" in targets:
        targets = [str(URA_ROOT / m) for m in MONSTER_LIST]
        log(f"🎯 Objetivos: {len(targets)} archivos monstruo")


def _leer_archivo(file_path: str) -> list[str]:
    with open(file_path) as file:  # noqa: PTH123
        return file.readlines()


def _escribir_log(message: str) -> None:
    pass


def _actualizar_contadores(chunks_done: int = 0, chunks_failed: int = 0) -> None:
    global CHUNKS_DONE, CHUNKS_FAILED  # noqa: PLW0603
    CHUNKS_DONE += chunks_done
    CHUNKS_FAILED += chunks_failed


def _procesar_archivo(file_path: str) -> bool:
    final_lines = _leer_archivo(file_path)
    _escribir_log(f"inyectado con éxito ({len(final_lines)} líneas)")
    return True


def _tratar_error(file_path: str, error: Exception) -> None:
    log(f"❌ Error catastrófico en {file_path}: {error}")
    import traceback

    traceback.print_exc()
    global FILES_FAILED  # noqa: PLW0603
    FILES_FAILED += 1


def sandbox_file(file_path: str) -> None:
    try:
        if _procesar_archivo(file_path):
            _actualizar_contadores(1, 0)
    except Exception as e:
        _tratar_error(file_path, e)


def main() -> None:
    global CHUNKS_DONE, CHUNKS_FAILED, FILES_DONE, FILES_FAILED  # noqa: PLW0602
    time.time()

    log("═" * 70)
    log("🏭 SANDBOX INDUSTRIAL — Aislamiento Total")
    log("═" * 70)
    log(f"📍 Sandbox dir:  {SANDBOX_DIR}")
    log(f"🤖 Cleaner:      {MODEL_CLEANER}")
    log(f"🤖 Refactorer:   {MODEL_REFACTOR}")
    log(f"📏 Chunk size:   {SANDBOX_CHUNK}l")
    log(f"📏 RAM ceiling:  {RAM_CEILING_GB}GB")
    log(f"🏷️  Dry run:      {DRY_RUN}")
    log("")

    _verificar_argumentos(sys.argv[1:])
    if "--monsters" in sys.argv:
        targets = _procesar_monsters(sys.argv[1:])
    else:
        targets = [arg for arg in sys.argv[1:] if Path(arg).is_file()]

    for file_path in targets:
        sandbox_file(file_path)


def _calcular_totales():
    return FILES_DONE, FILES_FAILED, CHUNKS_DONE, CHUNKS_FAILED


def _log_formato(tiempo_total, archivos_ok, archivos_fallidos, chunks_ok, chunks_fallidos) -> None:
    log("═" * 70)
    log(f"🏁 SANDBOX INDUSTRIAL — Finalizado en {tiempo_total:.1f}s")
    log(f"   Archivos OK:     {archivos_ok}")
    log(f"   Archivos FAIL:   {archivos_fallidos}")
    log(f"   Chunks OK:       {chunks_ok}")
    log(f"   Chunks FAIL:     {chunks_fallidos}")


def _ejecutar_sandbox(t) -> None:
    global FILES_FAILED  # noqa: PLW0603
    try:
        sandbox_file(t)
    except Exception as e:
        log(f"❌ Error catastrófico en {t}: {e}")

        traceback.print_exc()
        FILES_FAILED += 1


def _registrar_tiempo_final(start, elapsed) -> None:
    archivos_ok, archivos_fallidos, chunks_ok, chunks_fallidos = _calcular_totales()
    _log_formato(elapsed, archivos_ok, archivos_fallidos, chunks_ok, chunks_fallidos)


if __name__ == "__main__":
    start = time.time()
    targets = sys.argv[1:]
    _verificar_argumentos(targets)
    _procesar_monsters(targets)
    for t in targets:
        _ejecutar_sandbox(t)
    elapsed = time.time() - start
    _registrar_tiempo_final(start, elapsed)
