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

OLLAMA_URL = os.environ.get("OLLAMA_URL", os.environ.get("OLLAMA_URL", "http://10.164.1.99:11434"))
WORKER_ID = int(os.environ.get("REFACTOR_WORKER_ID", "0"))
WORKER_TOTAL = int(os.environ.get("REFACTOR_WORKER_TOTAL", "1"))

MODEL = os.environ.get("REFACTOR_MODEL", "deepseek-coder:6.7b")
MODEL_FALLBACK = os.environ.get("REFACTOR_MODEL_FALLBACK", "qwen2.5-coder:14b")
URA_ROOT = Path(os.environ.get("URA_ROOT", os.path.expanduser("~/URA/ura_ia_1972")))
DRY_RUN = os.environ.get("DRY_RUN", "0") == "1"
MAX_FUNCTIONS = int(os.environ.get("MAX_FUNCTIONS", "999"))
MIN_LINES = int(os.environ.get("MIN_LINES", "100"))

REFACTORED = 0
SKIPPED = 0
ERRORS = 0


def _ajustar_contexto(tokens_funcion: int, max_modelo: int = 100000, factor: float = 1.5) -> int:
    """Ajusta num_predict dinámicamente para acelerar inferencia."""
    optimo = int(max(tokens_funcion * factor, 2048))
    return min(optimo, max_modelo)


def _estimar_tokens(codigo: str) -> int:
    return max(len(codigo) // 4, 1)


def log(msg: str) -> None:
    pass


def llm(prompt: str, model: str | None = None) -> str:
    model = model or MODEL
    n_tokens = _estimar_tokens(prompt)
    n_predict = _ajustar_contexto(n_tokens)
    payload = json.dumps(
        {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "keep_alive": -1,
            "options": {"temperature": 0.1, "num_predict": n_predict},
        },
    ).encode()
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=600) as r:
        data = json.loads(r.read())
    return data.get("response", "")


def is_excluded(path: str) -> bool:
    excl = ["/venv/", "/.venv/", "/.git/", "/.mypy_cache/", "/__pycache__/", "/.tox/", "/node_modules/"]
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
                                },
                            )
        except (SyntaxError, UnicodeDecodeError, ValueError):
            pass
    return large


def clean_llm_response(text: str) -> str:
    text = text.strip()
    text = re.sub(r"(?s)^```(?:python)?\s*\n?", "", text)
    text = re.sub(r"(?s)\n?```\s*$", "", text)
    return text.strip()


def build_refactor_prompt(func_name: str, func_source: str, n_lines: int) -> str:
    """Prompt de 6 capas (Identidad, Contexto, Objetivo, Restricciones, Formato, Verificacion)."""
    return f"""Eres un ingeniero senior de Python con 20 anos de experiencia en refactorizacion.
Tu especialidad es dividir funciones monoliticas en componentes atomicos sin cambiar el comportamiento.

CONTEXTO:
  Funcion: \"{func_name}\" ({n_lines} lineas)
  Los imports disponibles son los que ya estan en el codigo

OBJETIVO:
  Divide esta funcion en helpers mas pequenas (MAXIMO 30 lineas cada una)
  La funcion original refactorizada debe llamar a las helpers que crees
  Las helpers van al MISMO nivel de indentacion, nunca anidadas

RESTRICCIONES (no negociables):
  1. NO cambies la logica ni el comportamiento observable
  2. NO cambies nombres de variables, argumentos, ni imports
  3. NO anadas ni elimines imports
  4. NO cambies la firma de la funcion original ni sus argumentos
  5. Cada helper: nombre descriptivo, sin efectos secundarios
  6. Incluye TODAS las helpers + la funcion refactorizada

FORMATO DE RESPUESTA:
  Devuelve SOLO codigo Python. Sin explicaciones. Sin markdown. Sin bloques ```.

VERIFICACION (antes de responder, marca cada punto):
  [ ] Parentesis, corchetes y llaves balanceados
  [ ] Indentacion consistente (4 espacios)
  [ ] Sin bloques vacios (if/for/while/try sin cuerpo)
  [ ] Sin codigo muerto tras return/raise/break/continue
  [ ] Todos los nombres de funcion/argumento existen
  [ ] Las helpers no duplican nombres existentes

[CODIGO]
{func_source}"""


def apply_refactored(file_path: str, lineno: int, end_lineno: int, new_code: str) -> bool:
    path = Path(file_path)
    original = path.read_text(encoding="utf-8")
    lines = original.splitlines()

    new_code = clean_llm_response(new_code)
    if not new_code:
        log("  ❌ Respuesta LLM vacía tras limpiar")
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
    result = lines[: lineno - 1] + new_lines + lines[end_lineno:]
    new_content = "\n".join(result)

    try:
        compile(new_content, file_path, "exec")
    except SyntaxError as e:
        log(f"  ❌ Error sintaxis post-reemplazo: {e}")
        log("  🔄 Reintentando con reparación...")
        fix_prompt = f"El código tiene un error de sintaxis: {e}. Corrígelo SIN cambiar la lógica. Código:\n```python\n{new_code}\n```\nDevuelve SOLO el código corregido."
        fix_resp = llm(fix_prompt)
        fix_code = clean_llm_response(fix_resp)
        if fix_code:
            fix_lines = fix_code.splitlines()
            fix_result = lines[: lineno - 1] + fix_lines + lines[end_lineno:]
            fix_content = "\n".join(fix_result)
            try:
                compile(fix_content, file_path, "exec")
                if not DRY_RUN:
                    backup = path.with_suffix(".py.bak3")
                    if not backup.exists():
                        shutil.copy2(path, backup)
                    path.write_text(fix_content, encoding="utf-8")
                    subprocess.run(
                        ["ruff", "check", "--fix", "--unsafe-fixes", file_path],
                        capture_output=True,
                        timeout=30,
                        check=False,
                    )
                    subprocess.run(["ruff", "format", file_path], capture_output=True, timeout=30, check=False)
                log("  ✅ Reparado tras reintento")
                return True
            except SyntaxError:
                log("  ❌ Error persiste tras reparación")
        return False

    if DRY_RUN:
        return True

    backup = path.with_suffix(".py.bak")
    if not backup.exists():
        shutil.copy2(path, backup)

    path.write_text(new_content, encoding="utf-8")

    subprocess.run(
        ["ruff", "check", "--fix", "--unsafe-fixes", file_path],
        capture_output=True,
        timeout=30,
        check=False,
    )
    subprocess.run(["ruff", "format", file_path], capture_output=True, timeout=30, check=False)
    return True


def main() -> None:
    global REFACTORED, SKIPPED, ERRORS
    start_time = time.time()
    log("🚀 Refactorización de funciones grandes vía LLM")
    log(f"📁 Root: {URA_ROOT}")
    log(f"🤖 Modelos: {MODEL} (principal) + {MODEL_FALLBACK} (fallback)")
    log(f"🏷️  Dry run: {DRY_RUN}")
    log(f"📏 Mínimo líneas: {MIN_LINES}, Máximo funciones: {MAX_FUNCTIONS}")
    log("")

    large = [f for f in get_large_functions(MIN_LINES) if f["lines"] <= 300]
    large.sort(key=lambda x: -x["lines"])
    large = large[:MAX_FUNCTIONS]
    # Distribuir entre workers
    if WORKER_TOTAL > 1:
        large = [f for i, f in enumerate(large) if i % WORKER_TOTAL == WORKER_ID]
        log(f"  Worker {WORKER_ID + 1}/{WORKER_TOTAL}: {len(large)} funciones")
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
            log("  ⏭️  Test")
            SKIPPED += 1
            continue

        func_source = "\n".join(Path(fname).read_text(encoding="utf-8").splitlines()[lineno - 1 : end_lineno])
        prompt = build_refactor_prompt(func_name, func_source, n_lines)

        log("  🤖 LLM...")
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
            log("  ❌ Respuesta vacía")
            ERRORS += 1
            continue

        if apply_refactored(fname, lineno, end_lineno, response):
            REFACTORED += 1
            log("  ✅ OK")
        else:
            log(f"  🔄 Reintentando con fallback: {MODEL_FALLBACK}")
            try:
                t0_fb = time.time()
                response_fb = llm(prompt, MODEL_FALLBACK)
                elapsed_fb = time.time() - t0_fb
                log(f"  ⏱️  Fallback: {elapsed_fb:.1f}s ({len(response_fb)} chars)")
                if apply_refactored(fname, lineno, end_lineno, response_fb):
                    REFACTORED += 1
                    log("  ✅ OK (fallback)")
                else:
                    ERRORS += 1
                    log("  ❌ Error también con fallback")
            except Exception as e:
                ERRORS += 1
                log(f"  ❌ Error fallback: {e}")

        log("")

    elapsed = time.time() - start_time
    log("=" * 50)
    log(f"✅ Completado en {elapsed:.1f}s")
    log(f"   Refactorizadas: {REFACTORED}")
    log(f"   Saltadas:       {SKIPPED}")
    log(f"   Errores:        {ERRORS}")


if __name__ == "__main__":
    main()
