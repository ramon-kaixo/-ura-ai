#!/usr/bin/env python3
"""Refactoriza funciones grandes (>80 lineas) usando LLM con COMPACTACION.

Flujo:
  1. Detecta funciones grandes via AST
  2. COMPACTA: quita comentarios, docstrings, lineas en blanco (-25-30% tokens)
  3. Envia al LLM pidiendo dividir en funciones mas pequenas
  4. DESCOMPACTA: restaura huecos usando mapa de anchors
  5. Aplica el cambio, verifica sintaxis, ejecuta ruff fix
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

# Agregar directorio de scripts al path
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

from compactador_espacios import compactar, descompactar

# Usar model_router (puerto 11435) para enrutamiento inteligente con temperatura por modelo
# Si no está disponible, cae directo a Ollama (11434)
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://10.164.1.99:11435")
OLLAMA_FALLBACK_URL = "http://10.164.1.99:11434"
WORKER_ID = int(os.environ.get("REFACTOR_WORKER_ID", "0"))
WORKER_TOTAL = int(os.environ.get("REFACTOR_WORKER_TOTAL", "1"))

# Valores por defecto — enviar "auto" para que el router seleccione el mejor modelo
# con temperatura optimizada por arquitectura (Qwen=0.0, DeepSeek=0.2, etc.)
MODEL = os.environ.get("REFACTOR_MODEL", "auto")
MODEL_FALLBACK = os.environ.get("REFACTOR_MODEL_FALLBACK", "qwen2.5-coder:14b")
URA_ROOT = Path(os.environ.get("URA_ROOT", os.path.expanduser("~/URA/ura_ia_1972")))
DRY_RUN = os.environ.get("DRY_RUN", "0") == "1"
MAX_FUNCTIONS = int(os.environ.get("MAX_FUNCTIONS", "999"))
MIN_LINES = int(os.environ.get("MIN_LINES", "100"))

REFACTORED = 0
SKIPPED = 0
ERRORS = 0


def _ajustar_contexto(tokens_funcion: int, max_modelo: int = 100000, factor: float = 1.5) -> int:
    optimo = int(max(tokens_funcion * factor, 2048))
    # Leer chunk_config.json si existe (bucle cerrado chunk_optimizer)
    chunk_cfg = URA_ROOT / ".nervioso" / "chunk_config.json"
    if chunk_cfg.exists():
        try:
            cfg = json.loads(chunk_cfg.read_text())
            chunk_actual = cfg.get("chunk_actual", optimo)
            optimo = min(optimo, chunk_actual)
        except Exception:
            pass
    return min(optimo, max_modelo)


def _estimar_tokens(codigo: str) -> int:
    return max(len(codigo) // 4, 1)


def log(msg: str) -> None:
    pass


def _ollama_request(url: str, payload: dict) -> dict:
    """Envía request a Ollama/router. Retorna respuesta JSON o dict vacío."""
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.loads(r.read())


def llm(prompt: str, model: str | None = None) -> str:
    """Llama al LLM vía model_router para temperatura optimizada por modelo.

    El router (puerto 11435) inyecta temperatura específica por arquitectura:
    - Qwen 14B (LLaMA/RoPE): temperatura 0.0 para refactor preciso
    - DeepSeek 6.7B (GPT): temperatura 0.2 para equilibrio creatividad/precisión
    - Qwen 32B: temperatura 0.1 para código complejo

    Si el router no está disponible, cae directo a Ollama con temperatura 0.1.
    """
    model = model or MODEL
    n_tokens = _estimar_tokens(prompt)
    n_predict = _ajustar_contexto(n_tokens)

    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "keep_alive": -1,
        "options": {"num_predict": n_predict},
    }

    # Intentar vía router primero (temperatura por modelo)
    try:
        data = _ollama_request(f"{OLLAMA_URL}/api/generate", payload)
        if data.get("response") is not None:
            return data["response"]
    except Exception:
        log("  ⚠️ Router no disponible, fallback a Ollama directo")

    # Fallback directo a Ollama con temperatura conservadora
    payload["options"]["temperature"] = 0.1
    try:
        data = _ollama_request(f"{OLLAMA_FALLBACK_URL}/api/generate", payload)
        return data.get("response", "")
    except Exception as e:
        log(f"  ❌ Error LLM: {e}")
        return ""


def is_excluded(path: str) -> bool:
    excl = [
        "/venv/",
        "/.venv/",
        "/.git/",
        "/.mypy_cache/",
        "/__pycache__/",
        "/.tox/",
        "/node_modules/",
    ]
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
        log("  Respuesta LLM vacia tras limpiar")
        return False

    try:
        compile(new_code, file_path, "exec")
    except SyntaxError as e:
        log(f"  Error sintaxis en respuesta: {e}")
        return False

    new_lines = new_code.splitlines()
    result = lines[: lineno - 1] + new_lines + lines[end_lineno:]
    new_content = "\n".join(result)

    try:
        compile(new_content, file_path, "exec")
    except SyntaxError as e:
        log(f"  Error sintaxis post-reemplazo: {e}")
        fix_prompt = f"El codigo tiene un error de sintaxis: {e}. Corrigelo SIN cambiar la logica. Codigo:\n```python\n{new_code}\n```\nDevuelve SOLO el codigo corregido."
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
                    )
                    subprocess.run(["ruff", "format", file_path], capture_output=True, timeout=30)
                log("  Reparado tras reintento")
                return True
            except SyntaxError:
                log("  Error persiste tras reparacion")
        return False

    if DRY_RUN:
        return True

    backup = path.with_suffix(".py.bak")
    if not backup.exists():
        shutil.copy2(path, backup)

    path.write_text(new_content, encoding="utf-8")
    subprocess.run(
        ["ruff", "check", "--fix", "--unsafe-fixes", file_path], capture_output=True, timeout=30,
    )
    subprocess.run(["ruff", "format", file_path], capture_output=True, timeout=30)
    return True


def refactor_one(func: dict) -> bool:
    """Refactoriza una funcion con compactacion."""
    global REFACTORED, SKIPPED, ERRORS

    file_path = func["file"]
    func_name = func["function"]
    lineno = func["lineno"]
    end_lineno = func["end_lineno"]
    n_lines = func["lines"]

    log(f"\n  Funcion: {func_name} ({n_lines}L) en {file_path}")

    # 1. Extraer codigo original
    try:
        source = Path(file_path).read_text(encoding="utf-8")
        lines = source.splitlines()
        func_source = "\n".join(lines[lineno - 1 : end_lineno])
    except Exception as e:
        log(f"  Error extrayendo: {e}")
        ERRORS += 1
        return False

    # 2. COMPACTAR (quitar huecos)
    compactado, anchors, stats = compactar(func_source)
    tokens_original = _estimar_tokens(func_source)
    tokens_compactado = _estimar_tokens(compactado)
    reduccion = round((1 - tokens_compactado / tokens_original) * 100, 1) if tokens_original else 0

    log(
        f"  Compactado: {stats['lineas_original']}L -> {stats['lineas_compactado']}L (-{reduccion}%)",
    )
    log(f"  Tokens: {tokens_original} -> {tokens_compactado} (-{reduccion}%)")

    # 3. LLM con codigo compacto
    prompt = build_refactor_prompt(func_name, compactado, stats["lineas_compactado"])
    t0 = time.time()
    response = llm(prompt)
    llm_time = round(time.time() - t0, 1)
    log(f"  LLM: {llm_time}s, {len(response)} chars")

    if not response:
        log("  LLM sin respuesta")
        ERRORS += 1
        return False

    # 4. DESCOMPACTAR respuesta
    response_descomp = descompactar(response, anchors)

    # 5. Aplicar
    if apply_refactored(file_path, lineno, end_lineno, response_descomp):
        REFACTORED += 1
        log("  Refactorizado con compactacion")
        return True
    ERRORS += 1
    return False


def scan_project() -> None:
    from pathlib import Path as _Path
    root = _Path.home() / "URA/ura_ia_1972"
    list(root.rglob("*.py"))


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Refactoriza funciones grandes con LLM")
    parser.add_argument("--scan", action="store_true", help="Escanear todo el proyecto")
    args = parser.parse_args()
    if args.scan:
        scan_project()
        return

    global REFACTORED, SKIPPED, ERRORS, MIN_LINES, MAX_FUNCTIONS

    log("=" * 60)
    log("  REFACTOR LARGE FUNCTIONS v2 (con compactacion)")
    log("=" * 60)
    log(f"  Modelo: {MODEL}")
    log(f"  Worker: {WORKER_ID}/{WORKER_TOTAL}")
    log(f"  Min lineas: {MIN_LINES}")
    log(f"  Max funciones: {MAX_FUNCTIONS}")

    large = get_large_functions(MIN_LINES)
    log(f"\n  Funciones grandes detectadas: {len(large)}")

    # Distribuir entre workers
    my_funcs = [f for i, f in enumerate(large) if i % WORKER_TOTAL == WORKER_ID]
    log(f"  Funciones para este worker: {len(my_funcs)}")

    t0 = time.time()
    for func in my_funcs[:MAX_FUNCTIONS]:
        refactor_one(func)

    elapsed = round(time.time() - t0, 1)
    log(f"\n{'=' * 60}")
    log("  RESUMEN")
    log(f"{'=' * 60}")
    log(f"  Refactorizados: {REFACTORED}")
    log(f"  Saltados: {SKIPPED}")
    log(f"  Errores: {ERRORS}")
    log(f"  Tiempo: {elapsed}s")
    log(f"{'=' * 60}")


if __name__ == "__main__":
    main()
