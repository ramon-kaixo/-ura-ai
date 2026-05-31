#!/usr/bin/env python3
"""Refactoriza funciones grandes (>80 líneas) usando LLM vía Ollama.

Flujo:
  1. Detecta funciones grandes vía AST
  2. Por cada una, envía al LLM pidiendo dividir en funciones más pequeñas
  3. Aplica el cambio, verifica sintaxis, ejecuta ruff fix
"""
import ast
import json
import os
import re
import shutil
import subprocess
import time
import urllib.request
from pathlib import Path

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://10.164.1.99:11434")
MODEL = os.environ.get("REFACTOR_MODEL", "qwen2.5:7b")
URA_ROOT = Path(os.environ.get("URA_ROOT", os.path.expanduser("~/URA/ura_ia_1972")))
DRY_RUN = os.environ.get("DRY_RUN", "0") == "1"
MAX_FUNCTIONS = int(os.environ.get("MAX_FUNCTIONS", "999"))
MIN_LINES = int(os.environ.get("MIN_LINES", "100"))

REFACTORED = 0
SKIPPED = 0
ERRORS = 0


def log(msg: str) -> None:
    print(msg)


def llm(prompt: str) -> str:
    payload = json.dumps({
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "keep_alive": -1,
        "options": {"temperature": 0.1, "num_predict": 3072},
    }).encode()
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=180) as r:
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
                            large.append({
                                "file": py_path,
                                "function": node.name,
                                "lines": n_lines,
                                "lineno": node.lineno,
                                "end_lineno": node.end_lineno,
                            })
        except (SyntaxError, UnicodeDecodeError, ValueError):
            pass
    return large


def clean_llm_response(text: str) -> str:
    text = text.strip()
    text = re.sub(r"(?s)^```(?:python)?\s*\n?", "", text)
    text = re.sub(r"(?s)\n?```\s*$", "", text)
    return text.strip()


def build_refactor_prompt(func_name: str, func_source: str, n_lines: int) -> str:
    return f"""Divide la función '{func_name}' ({n_lines} líneas) en funciones más pequeñas.

REGLAS:
1. NO cambies la lógica ni los nombres de variables/clases externas
2. NO añadas imports
3. NO cambies la firma de la función original
4. Las helpers deben ser funciones INDEPENDIENTES al mismo nivel que la original (NO anidadas dentro)
5. Cada helper debe tener MÁXIMO 30 líneas
6. Incluye TODAS las helpers + la función refactorizada
7. La función original refactorizada debe llamar a las helpers
8. Devuelve SOLO el código Python, sin explicaciones ni markdown

Código actual:
{func_source}

Escribe el código refactorizado (helpers + función original):"""


def apply_refactored(file_path: str, lineno: int, end_lineno: int, new_code: str) -> bool:
    path = Path(file_path)
    original = path.read_text(encoding="utf-8")
    lines = original.splitlines()

    new_code = clean_llm_response(new_code)
    if not new_code:
        log(f"  ❌ Respuesta LLM vacía tras limpiar")
        return False

    # Verify new_code compiles
    try:
        compile(new_code, file_path, "exec")
    except SyntaxError as e:
        log(f"  ❌ Error sintaxis en respuesta: {e}")
        return False

    new_lines = new_code.splitlines()

    # Simple replacement: swap old function lines with new code
    # The LLM should return code at the same indentation level as the original
    result = lines[:lineno - 1] + new_lines + lines[end_lineno:]
    new_content = "\n".join(result)

    try:
        compile(new_content, file_path, "exec")
    except SyntaxError as e:
        log(f"  ❌ Error sintaxis post-reemplazo: {e}")
        return False

    if DRY_RUN:
        return True

    backup = path.with_suffix(".py.bak")
    if not backup.exists():
        shutil.copy2(path, backup)

    path.write_text(new_content, encoding="utf-8")

    subprocess.run(["ruff", "check", "--fix", "--unsafe-fixes", file_path],
                   capture_output=True, timeout=30)
    subprocess.run(["ruff", "format", file_path],
                   capture_output=True, timeout=30)
    return True


def main() -> None:
    global REFACTORED, SKIPPED, ERRORS
    start_time = time.time()
    log(f"🚀 Refactorización de funciones grandes vía LLM")
    log(f"📁 Root: {URA_ROOT}")
    log(f"🤖 Modelo: {MODEL} @ {OLLAMA_URL}")
    log(f"🏷️  Dry run: {DRY_RUN}")
    log(f"📏 Mínimo líneas: {MIN_LINES}, Máximo funciones: {MAX_FUNCTIONS}")
    log("")

    large = [f for f in get_large_functions(MIN_LINES) if f["lines"] <= 300]
    large.sort(key=lambda x: -x["lines"])
    large = large[:MAX_FUNCTIONS]
    log(f"📊 {len(large)} funciones a refactorizar")
    log("")

    for i, func in enumerate(large):
        fname = func["file"]
        func_name = func["function"]
        n_lines = func["lines"]
        lineno = func["lineno"]
        end_lineno = func["end_lineno"]

        rel_path = os.path.relpath(fname, str(URA_ROOT))
        log(f"[{i + 1}/{len(large)}] {rel_path}:{lineno} {func_name} ({n_lines} líneas)")

        if "test_" in func_name or func_name.startswith("test"):
            log(f"  ⏭️  Test")
            SKIPPED += 1
            continue

        func_source = "\n".join(Path(fname).read_text(encoding="utf-8").splitlines()[lineno - 1:end_lineno])
        prompt = build_refactor_prompt(func_name, func_source, n_lines)

        log(f"  🤖 LLM...")
        try:
            t0 = time.time()
            response = llm(prompt)
            elapsed = time.time() - t0
            log(f"  ⏱️  {elapsed:.1f}s ({len(response)} chars)")
        except Exception as e:
            log(f"  ❌ Error LLM: {e}")
            ERRORS += 1
            continue

        if not response.strip():
            log(f"  ❌ Respuesta vacía")
            ERRORS += 1
            continue

        if apply_refactored(fname, lineno, end_lineno, response):
            REFACTORED += 1
            log(f"  ✅ OK")
        else:
            ERRORS += 1

        log("")

    elapsed = time.time() - start_time
    log("=" * 50)
    log(f"✅ Completado en {elapsed:.1f}s")
    log(f"   Refactorizadas: {REFACTORED}")
    log(f"   Saltadas:       {SKIPPED}")
    log(f"   Errores:        {ERRORS}")


if __name__ == "__main__":
    main()
