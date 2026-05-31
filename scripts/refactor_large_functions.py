#!/usr/bin/env python3
"""Refactoriza funciones grandes usando LLM vía Ollama.

Modos:
  - Normal (MIN_LINES=100, MAX_FUNCTIONS=N): parte funciones una a una (100-300l)
  - Chunk (CHUNK_LINES=60): divide archivos en fragmentos lógicos de ~N líneas,
    cortando siempre por límites de función/clase. Rápido y no rompe contexto.
  - Monstruo (MONSTER_MODE=1): envía archivo entero (>300l por función)
"""

import ast
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://10.164.1.99:11434")
MODEL = os.environ.get("REFACTOR_MODEL", "qwen2.5:7b")
URA_ROOT = Path(os.environ.get("URA_ROOT", os.path.expanduser("~/URA/ura_ia_1972")))
DRY_RUN = os.environ.get("DRY_RUN", "0") == "1"
MAX_CHUNKS = int(os.environ.get("MAX_CHUNKS", "999"))
MONSTER_THRESHOLD = int(os.environ.get("MONSTER_THRESHOLD", "300"))

# Chunk mode: divide archivos en fragmentos de este tamaño
CHUNK_LINES = int(os.environ.get("CHUNK_LINES", "0"))
if CHUNK_LINES == 0:
    CHUNK_LINES = 80  # default
MODE = os.environ.get("REFACTOR_MODE", "chunk").lower()

REFACTORED = 0
SKIPPED = 0
ERRORS = 0


def log(msg: str) -> None:
    print(msg)


def llm(prompt: str, num_predict: int = 4096) -> str:
    payload = json.dumps(
        {
            "model": MODEL,
            "prompt": prompt,
            "stream": False,
            "keep_alive": -1,
            "options": {"temperature": 0.1, "num_predict": num_predict},
        }
    ).encode()
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=300) as r:
        data = json.loads(r.read())
    return data.get("response", "")


def is_excluded(path: str) -> bool:
    excl = ["/venv/", "/.git/", "/.mypy_cache/", "/__pycache__/", "/.tox/", "/node_modules/"]
    return any(e in path for e in excl)


def get_large_functions(threshold: int = 80) -> list[dict]:
    large = []
    for py_file in sorted(URA_ROOT.rglob("*.py")):
        py_path = str(py_file)
        if is_excluded(py_path):
            continue
        try:
            source = py_file.read_text(encoding="utf-8")
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if hasattr(node, "end_lineno") and node.end_lineno and node.lineno:
                        n_lines = node.end_lineno - node.lineno
                        if n_lines > threshold:
                            large.append(
                                {
                                    "file": py_path,
                                    "function": node.name,
                                    "lines": n_lines,
                                    "lineno": node.lineno,
                                    "end_lineno": node.end_lineno,
                                }
                            )
        except (SyntaxError, UnicodeDecodeError, ValueError):
            pass
    return large


def get_monster_files() -> list[dict]:
    """Encuentra archivos con funciones >MONSTER_THRESHOLD."""
    funcs = get_large_functions(MONSTER_THRESHOLD)
    seen = set()
    files = []
    for f in funcs:
        if f["file"] not in seen:
            seen.add(f["file"])
            source = Path(f["file"]).read_text(encoding="utf-8")
            n_lines = len(source.splitlines())
            files.append(
                {
                    "file": f["file"],
                    "total_lines": n_lines,
                    "functions": [g for g in funcs if g["file"] == f["file"]],
                }
            )
    return files


def get_natural_breaks(file_path: str) -> list[int]:
    """Encuentra puntos de corte naturales: funciones, clases, líneas en blanco."""
    source = Path(file_path).read_text(encoding="utf-8")
    lines = source.splitlines()
    total = len(lines)
    tree = ast.parse(source)

    breaks = set()
    breaks.add(1)
    breaks.add(total + 1)

    # Límites de funciones y clases top-level
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            breaks.add(node.lineno)
            breaks.add(node.end_lineno + 1)  # blank line after function

    # Líneas en blanco (natural paragraph breaks)
    for ln in range(1, total + 1):
        idx = ln - 1
        if idx < len(lines) and lines[idx].strip() == "":
            # Solo cortar si hay código antes y después (no dobles blanks seguidos)
            if idx > 0 and idx < total - 1 and lines[idx - 1].strip() and lines[idx + 1].strip():
                breaks.add(ln + 1)  # cut after blank line

    return sorted(breaks)


def chunk_file(file_path: str) -> list[dict]:
    """Divide archivo en fragmentos lógicos de ~CHUNK_LINES, con índice."""
    source = Path(file_path).read_text(encoding="utf-8")
    lines = source.splitlines()
    total = len(lines)
    breaks = get_natural_breaks(file_path)

    # Construir segmentos entre puntos de corte
    segments = []
    for i in range(len(breaks) - 1):
        start = breaks[i]
        end = breaks[i + 1] - 1
        if end >= start:
            src = "\n".join(lines[start - 1 : end])
            segments.append({"start": start, "end": end, "source": src, "lines": end - start + 1})

    # Agrupar segmentos en chunks de ~CHUNK_LINES
    chunks = []
    buf = []
    buf_lines = 0

    def flush():
        nonlocal buf, buf_lines
        if not buf:
            return
        start = buf[0]["start"]
        end = buf[-1]["end"]
        src = "\n".join(lines[start - 1 : end])
        chunks.append(
            {
                "start": start,
                "end": end,
                "source": src,
                "lines": end - start + 1,
                "idx": len(chunks),
            }
        )
        buf = []
        buf_lines = 0

    for seg in segments:
        if buf_lines + seg["lines"] > CHUNK_LINES and buf_lines > 0:
            flush()
        buf.append(seg)
        buf_lines += seg["lines"]

    flush()
    return chunks


def clean_llm_response(text: str) -> str:
    text = text.strip()
    text = re.sub(r"(?s)^```(?:python)?\s*\n?", "", text)
    text = re.sub(r"(?s)\n?```\s*$", "", text)
    return text.strip()


ENGLISH_THINK = os.environ.get("ENGLISH_THINK", "1") == "1"
ENGLISH_ONLY = os.environ.get("ENGLISH_ONLY", "0") == "1"


def build_refactor_prompt(func_name: str, func_source: str, n_lines: int) -> str:
    if ENGLISH_ONLY:
        return f"""[INDUSTRIAL DIRECTIVE: 100% ENGLISH REFACTORING]
You are a Principal Software Engineer. Provided is the function '{func_name}' ({n_lines} lines).
Your mission: reinterpret the logic from scratch in professional programming English.

RULES:
1. 100% ENGLISH output — no Spanish words, no Spanglish. All identifiers in English.
2. Atomic helpers: extract each independent action into a sub-function (15-30 lines max).
   Helper names start with underscore (e.g. _validate_token, _compute_totals).
3. Conductor pattern: the original function becomes a minimal orchestrator.
4. PRESERVE the original function SIGNATURE (name + arguments) exactly — it's called externally.
5. 4-space indent. NO markdown, NO explanations. Pure Python code only.

[CODE TO REFACTOR]
{func_source}"""
    elif ENGLISH_THINK:
        return f"""[INSTRUCCIÓN INDUSTRIAL DE REINTERPRETACIÓN Y REESCRITURA]
Actúas como un Diseñador de Software Principal experto en Python y sistemas de IA locales.
Se te proporciona la función '{func_name}' ({n_lines} líneas). Tu objetivo no es limpiar ni resumir,
sino REINTERPRETAR la lógica desde cero y modularizarla por "frases lógicas" independientes
usando el puente del inglés como motor de pensamiento.

PROCESO MENTAL INTERNO OBLIGATORIO:
1. TRADUCCIÓN CONCEPTUAL: Traduce mentalmente la lógica, variables e intención al inglés.
2. REINTERPRETACIÓN POR FRASES: Identifica cada acción única e independiente. Divide en "frases lógicas".
3. CONSTRUCCIÓN ATÓMICA: Diseña sub-funciones (helpers) para cada frase. Cada helper hace UNA SOLA COSA,
   nombre descriptivo, MÁXIMO 30 líneas. La función principal queda reducida a un director de orquesta.
4. RETORNO AL CASTELLANO: Genera el código Python con nombres de funciones y variables en castellano.

REGLAS DE SALIDA:
- Las helpers empiezan con guion bajo (ej. _validar_entrada)
- Indentación perfecta 4 espacios
- La función principal solo llama a las helpers en orden
- NO cambies la firma de la función original ni los imports
- Devuelve SOLO el código Python, sin markdown ni explicaciones

[CÓDIGO ORIGINAL]
{func_source}

Escribe el código refactorizado completo:"""
    else:
        return f"""Divide la función '{func_name}' ({n_lines} líneas) en funciones más pequeñas.

REGLAS:
1. NO cambies la lógica ni los nombres de variables/clases externas
2. NO añadas imports
3. NO cambies la firma de la función original
4. Las helpers deben ser funciones INDEPENDIENTES al mismo nivel que la original
5. Cada helper debe tener MÁXIMO 30 líneas
6. Incluye TODAS las helpers + la función refactorizada
7. La función original refactorizada debe llamar a las helpers
8. Devuelve SOLO el código Python, sin explicaciones ni markdown

Código actual:
{func_source}

Escribe el código refactorizado:"""


def build_chunk_prompt(rel_path: str, chunk_source: str, chunk_n: int, total_chunks: int) -> str:
    n = len(chunk_source.splitlines())
    if ENGLISH_ONLY:
        return f"""[INDUSTRIAL DIRECTIVE: ENGLISH REFACTORING]
Fragment {chunk_n}/{total_chunks} of "{rel_path}" ({n} lines).

RULES:
1. 100% ENGLISH — all identifiers, comments, docstrings in English.
2. PRESERVE original function signatures (names called from other files).
3. Atomic helpers 15-30 lines, underscore-prefixed names.
4. 4-space indent. Pure Python, no markdown.

[CODE]
{chunk_source}"""
    elif ENGLISH_THINK:
        return f"""[INSTRUCCIÓN INDUSTRIAL DE REINTERPRETACIÓN Y REESCRITURA]
Actúas como Diseñador de Software Principal. Fragmento {chunk_n}/{total_chunks} de "{rel_path}" ({n} líneas).

PROCESO MENTAL:
1. TRADUCCIÓN: piensa la lógica en inglés para máxima abstracción
2. FRASES LÓGICAS: identifica cada acción independiente
3. CONSTRUCCIÓN ATÓMICA: crea helpers de 15-30 líneas, cada una hace UNA COSA
4. RETORNO: código Python en castellano (variables, funciones)

REGLAS:
- Las helpers con guion bajo (ej. _calcular_totales)
- Indentación 4 espacios perfecta
- NO cambies imports, firmas públicas, ni lógica
- Devuelve SOLO código Python, sin markdown ni explicaciones

[CÓDIGO]
{chunk_source}"""
    else:
        return f"""Actúa como un Ingeniero de Software experto en refactorización limpia de Python.

Este es el fragmento {chunk_n}/{total_chunks} del archivo "{rel_path}" ({n} líneas).
Divide este fragmento en funciones puras de entre 15 y 30 líneas cada una.
Las funciones relacionadas deben agruparse. NO superes las 100 líneas por bloque lógico.

REGLAS:
1. NO cambies la lógica ni los nombres de variables/clases externas
2. NO añadas imports
3. Mantén la misma interfaz (nombres de función y argumentos)
4. Devuelve SOLO el código Python, SIN explicaciones ni markdown

Código:
{chunk_source}"""


def build_monster_prompt(file_path: str, source: str) -> str:
    rel = os.path.relpath(file_path, str(URA_ROOT))
    n_lines = len(source.splitlines())
    return f"""Actúa como un Ingeniero de Software experto en refactorización limpia de Python.

Tengo un archivo "{rel}" ({n_lines} líneas) con código acumulado, históricos y funciones gigantes. Tu objetivo es desestructurar este archivo de forma recursiva aplicando la regla de múltiplos de 100 líneas.

INSTRUCCIONES DE DISEÑO:
1. Identifica "Paja" e Históricos: Si detectas listas gigantes, diccionarios estáticos o comentarios obsoletos, extráelos mentalmente y colócalos en un bloque separado llamado "# CONSTANTES Y CONFIGURACIÓN".
2. Filtro de los múltiplos de 100: Divide el código en bloques lógicos compactos. Ningún bloque o grupo de funciones relacionadas debe superar las 100 líneas.
3. Funciones Atómicas: Dentro de cada bloque de 100 líneas, el código debe subdividirse en funciones puras de entre 15 y 30 líneas cada una.
4. Repetición: Aplica este reparto de forma iterativa hasta que dejen de aparecer funciones masivas. Toda la lógica original debe seguir funcionando exactamente igual.

REGLAS ESTRICTAS:
- Devuelve SOLO el código Python completo, sin explicaciones ni markdown
- Mantén los mismos imports y la misma interfaz pública
- NO uses ```python ni ``` en la respuesta

Código:
{source}"""


def verify_compile(code: str, file_path: str) -> bool:
    try:
        compile(code, file_path, "exec")
        return True
    except SyntaxError as e:
        log(f"  ❌ Error sintaxis: {e}")
        return False


def apply_refactored(file_path: str, lineno: int, end_lineno: int, new_code: str) -> bool:
    path = Path(file_path)
    original = path.read_text(encoding="utf-8")
    lines = original.splitlines()

    new_code = clean_llm_response(new_code)
    if not new_code:
        log("  ❌ Respuesta LLM vacía tras limpiar")
        return False

    if not verify_compile(new_code, file_path):
        return False

    new_lines = new_code.splitlines()
    result = lines[: lineno - 1] + new_lines + lines[end_lineno:]
    new_content = "\n".join(result)

    if not verify_compile(new_content, file_path):
        return False

    if DRY_RUN:
        return True

    backup = path.with_suffix(".py.bak")
    if not backup.exists():
        shutil.copy2(path, backup)

    path.write_text(new_content, encoding="utf-8")
    subprocess.run(
        ["ruff", "check", "--fix", "--unsafe-fixes", file_path], capture_output=True, timeout=30
    )
    subprocess.run(["ruff", "format", file_path], capture_output=True, timeout=30)
    return True


def apply_refactored_file(file_path: str, new_code: str) -> bool:
    path = Path(file_path)
    new_code = clean_llm_response(new_code)
    if not new_code:
        log("  ❌ Respuesta LLM vacía tras limpiar")
        return False
    if not verify_compile(new_code, file_path):
        return False
    if DRY_RUN:
        return True
    backup = path.with_suffix(".py.bak")
    if not backup.exists():
        shutil.copy2(path, backup)
    path.write_text(new_code, encoding="utf-8")
    subprocess.run(
        ["ruff", "check", "--fix", "--unsafe-fixes", file_path], capture_output=True, timeout=30
    )
    subprocess.run(["ruff", "format", file_path], capture_output=True, timeout=30)
    return True


def run_normal_mode() -> None:
    global REFACTORED, SKIPPED, ERRORS
    large = list(get_large_functions(100))
    large.sort(key=lambda x: -x["lines"])
    large = large[:MAX_CHUNKS]

    for i, func in enumerate(large):
        fname = func["file"]
        func_name = func["function"]
        n_lines = func["lines"]
        lineno = func["lineno"]
        end_lineno = func["end_lineno"]
        rel = os.path.relpath(fname, str(URA_ROOT))

        log(f"[{i + 1}/{len(large)}] {rel}:{lineno} {func_name} ({n_lines}l)")

        if "test_" in func_name or func_name.startswith("test"):
            SKIPPED += 1
            continue
        if DRY_RUN:
            REFACTORED += 1
            continue

        src = "\n".join(Path(fname).read_text().splitlines()[lineno - 1 : end_lineno])
        prompt = build_refactor_prompt(func_name, src, n_lines)

        log("  🤖 LLM...")
        try:
            t0 = time.time()
            response = llm(prompt)
            log(f"  ⏱️  {time.time() - t0:.1f}s ({len(response)} chars)")
        except Exception as e:
            log(f"  ❌ Error LLM: {e}")
            ERRORS += 1
            continue

        if not response.strip():
            ERRORS += 1
            continue

        if apply_refactored(fname, lineno, end_lineno, response):
            REFACTORED += 1
        else:
            ERRORS += 1


def run_chunk_mode(target_files: list[str] | None = None) -> None:
    """Modo chunk: divide archivos con funciones grandes en fragmentos lógicos de ~CHUNK_LINES cada uno."""
    global REFACTORED, SKIPPED, ERRORS
    if target_files:
        # Process specific files passed via CLI
        monsters = []
        for f in target_files:
            fpath = str(URA_ROOT / f) if not f.startswith("/") else f
            if not Path(fpath).exists():
                log(f"⚠️  Archivo no encontrado: {fpath}")
                continue
            source = Path(fpath).read_text(encoding="utf-8")
            n_lines = len(source.splitlines())
            funcs = get_large_functions(MONSTER_THRESHOLD)
            monsters.append(
                {
                    "file": fpath,
                    "total_lines": n_lines,
                    "functions": [g for g in funcs if g["file"] == fpath],
                }
            )
    else:
        monsters = get_monster_files()
    monsters = monsters[:MAX_CHUNKS]
    total_lines = sum(m["total_lines"] for m in monsters)
    log(f"📊 {len(monsters)} archivos → divididos en fragmentos de ~{CHUNK_LINES} líneas")
    log(f"📏 Total: {total_lines} líneas (~{total_lines // max(CHUNK_LINES, 1) + 1} fragmentos)")

    for m in monsters:
        fname = m["file"]
        rel = os.path.relpath(fname, str(URA_ROOT))
        chunks = chunk_file(fname)
        funcs_str = ", ".join(f"{f['function']}({f['lines']}l)" for f in m["functions"])
        log(f"\n📁 {rel} ({m['total_lines']}l) → {len(chunks)} fragmentos — {funcs_str}")

        # Process bottom-to-top so line numbers stay valid
        for c in reversed(chunks):
            log(f"  └─ Fragmento L{c['start']}-{c['end']} ({c['lines']}l)")

            if DRY_RUN:
                REFACTORED += 1
                continue

            chunk_n = len(chunks) - chunks[::-1].index(c)  # index in original order
            prompt = build_chunk_prompt(rel, c["source"], chunk_n, len(chunks))

            log("     🤖 LLM...")
            try:
                t0 = time.time()
                response = llm(prompt, num_predict=min(c["lines"] * 15, 8192))
                log(f"     ⏱️  {time.time() - t0:.1f}s ({len(response)} chars)")
            except Exception as e:
                log(f"     ❌ Error LLM: {e}")
                ERRORS += 1
                continue

            if not response.strip():
                ERRORS += 1
                continue

            if apply_refactored(fname, c["start"], c["end"], response):
                REFACTORED += 1
                log("     ✅ OK")
            else:
                ERRORS += 1

    log("")


def run_monster_mode() -> None:
    global REFACTORED, SKIPPED, ERRORS
    monsters = get_monster_files()
    monsters = monsters[:MAX_CHUNKS]

    for i, m in enumerate(monsters):
        fname = m["file"]
        rel = os.path.relpath(fname, str(URA_ROOT))
        source = Path(fname).read_text()
        funcs_str = ", ".join(f"{f['function']}({f['lines']}l)" for f in m["functions"])
        log(f"[{i + 1}/{len(monsters)}] {rel} ({m['total_lines']}l) — {funcs_str}")

        if DRY_RUN:
            REFACTORED += 1
            continue

        prompt = build_monster_prompt(fname, source)
        log("  🤖 LLM (archivo completo)...")
        try:
            t0 = time.time()
            response = llm(prompt, num_predict=16384)
            log(f"  ⏱️  {time.time() - t0:.1f}s ({len(response)} chars)")
        except Exception as e:
            log(f"  ❌ Error LLM: {e}")
            ERRORS += 1
            continue

        if not response.strip():
            ERRORS += 1
            continue

        if apply_refactored_file(fname, response):
            REFACTORED += 1
        else:
            ERRORS += 1


def main() -> None:
    global REFACTORED, SKIPPED, ERRORS
    start = time.time()
    log("🚀 Refactorización de funciones grandes vía LLM")
    log(f"🤖 Modelo: {MODEL} @ {OLLAMA_URL}")
    log(f"🏷️  Dry run: {DRY_RUN}")
    log(f"📏 Chunk: ~{CHUNK_LINES}l/fragmento | Monstruo: >={MONSTER_THRESHOLD}l")
    log("")

    # CLI args: file paths to process (skips repo scan)
    cli_files = sys.argv[1:] if len(sys.argv) > 1 else None

    MONSTER_MODE = os.environ.get("MONSTER_MODE", "0") == "1"
    if MONSTER_MODE:
        run_monster_mode()
    elif MODE == "normal":
        run_normal_mode()
    else:
        run_chunk_mode(cli_files)

    elapsed = time.time() - start
    log("=" * 50)
    log(f"✅ Completado en {elapsed:.1f}s")
    log(f"   Refactorizadas: {REFACTORED}")
    log(f"   Saltadas:       {SKIPPED}")
    log(f"   Errores:        {ERRORS}")


if __name__ == "__main__":
    main()
