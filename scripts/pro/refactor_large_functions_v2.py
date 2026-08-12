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
import time
import urllib.request
from pathlib import Path

# Agregar directorio de scripts al path
SCRIPT_DIR = Path(__file__).parent

from compactador_espacios import compactar
from fraccionador_ast import fraccionar as _fraccionar_ast

# Memoria persistente del refactor (TASK-20260812-020, filosofía RAMON:
# determinismo + memoria + reglas + revisiones).
try:
    from memoria_refactor import consultar_funcion, registrar_intento
except ImportError:  # pragma: no cover
    def consultar_funcion(*_a, **_k):  # type: ignore[no-redef]
        return {"estado": "sin_intentar", "intentos": []}

    def registrar_intento(*_a, **_k):  # type: ignore[no-redef]
        return {}

# Contexto de rama (TASK-20260812-021, diseño RAMON: "conocimiento con lógica"):
# el LLM recibe de dónde viene y hacia dónde va la función, no conocimiento general.
try:
    from contexto_rama import construir_contexto_rama as _construir_rama
except ImportError:  # pragma: no cover
    def _construir_rama(*_a, **_k):  # type: ignore[no-redef]
        return ""


def _construir_contexto_rama(file_path: str, func_name: str, func_source: str) -> str:
    """Wrapper que construye el contexto de rama con cache de archivo."""
    try:
        fuente = Path(file_path).read_text(encoding="utf-8")
    except OSError:
        fuente = ""
    return _construir_rama(URA_ROOT, file_path, func_name, func_source, fuente)

# Verificación con tests (TASK-20260812-019): si el archivo tiene tests que lo
# cubren, se verifica antes/después del refactor. Degrada con gracia.
VERIFICAR_TESTS = os.environ.get("REFACTOR_VERIFY_TESTS", "1") == "1"
try:
    from verificador_tests import _tests_para_archivo, ejecutar_tests, verificar_con_tests
except ImportError:  # pragma: no cover
    VERIFICAR_TESTS = False

# Usar model_router (puerto 11435) para enrutamiento inteligente con temperatura por modelo
# Si no está disponible, cae directo a Ollama (11434)
# Nota (TASK-20260812-020): el router escucha en 127.0.0.1, no en la IP de red local.
OLLAMA_URL = os.environ.get("OLLAMA_URL", os.environ.get("MODEL_ROUTER_URL", "http://127.0.0.1:11435"))
OLLAMA_FALLBACK_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
WORKER_ID = int(os.environ.get("REFACTOR_WORKER_ID", "0"))
WORKER_TOTAL = int(os.environ.get("REFACTOR_WORKER_TOTAL", "1"))

# Valores por defecto — enviar "auto" para que el router seleccione el mejor modelo
# con temperatura optimizada por arquitectura (Qwen=0.0, DeepSeek=0.2, etc.)
MODEL = os.environ.get("REFACTOR_MODEL", "auto")
MODEL_FALLBACK = os.environ.get("REFACTOR_MODEL_FALLBACK", "qwen2.5-coder:14b")
URA_ROOT = Path(os.environ.get("URA_ROOT", Path("~/URA/ura_ia_1972").expanduser()))
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
        except Exception:  # noqa: S110
            pass
    return min(optimo, max_modelo)


def _estimar_tokens(codigo: str) -> int:
    return max(len(codigo) // 4, 1)


def log(msg: str) -> None:
    pass


def _ollama_request(url: str, payload: dict) -> dict:
    """Envía request a Ollama/router. Retorna respuesta JSON o dict vacío."""
    req = urllib.request.Request(  # noqa: S310
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=600) as r:  # noqa: S310
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
        "/.sandbox_packages/",  # librerías externas (fastapi, numpy...) — no refactorear
        "/site-packages/",
        "/dist-packages/",
        "/.attic/",
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
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):  # noqa: SIM102
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


def _extraer_llamadores(file_path: str, func_name: str, fuente_archivo: str = "") -> str:
    """Extrae los llamadores de la función (contexto para el LLM).

    Determinista (AST): encuentra dónde se llama a func_name en el archivo y
    devuelve las líneas de contexto. Así el LLM sabe la firma de uso real.
    """
    if not fuente_archivo:
        try:
            fuente_archivo = Path(file_path).read_text(encoding="utf-8")
        except OSError:
            return ""
    try:
        tree = ast.parse(fuente_archivo)
    except SyntaxError:
        return ""
    lineas = fuente_archivo.splitlines()
    llamadas: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == func_name and node.lineno and node.lineno <= len(lineas):
            llamadas.append(lineas[node.lineno - 1].strip())
    if not llamadas:
        return ""
    unicas = list(dict.fromkeys(llamadas))[:5]
    return "\n".join(f"  {c}" for c in unicas)


def build_refactor_prompt(
    func_name: str,
    func_source: str,
    n_lines: int,
    llamadores: str = "",
    contexto_rama: str = "",
) -> str:
    firma = _extraer_firma(func_source)
    contexto_llamadores = (
        f"\nLLAMADORES DE LA FUNCION (contexto — NO los modifiques):\n{llamadores}\n"
        if llamadores
        else ""
    )
    contexto_conexiones = (
        f"\nCONEXIONES DEL CODIGO (de donde viene / hacia donde va — usa esta informacion "
        f"para no romper nada, pero NO la modifiques):\n{contexto_rama}\n"
        if contexto_rama
        else ""
    )
    return f"""Eres un ingeniero senior de Python con 20 anos de experiencia en refactorizacion.
Tu especialidad es extraer helpers de funciones monoliticas sin cambiar el comportamiento.

CONTEXTO:
  Funcion: \"{func_name}\" ({n_lines} lineas)
  FIRMA EXACTA (el sistema la conservara intacta — NO la reescribas):
  {firma}
  Los imports disponibles son los que ya estan en el codigo
{contexto_llamadores}{contexto_conexiones}
OBJETIVO (MODO QUIRURGICO):
  Identifica los bloques de codigo que pueden extraerse como funciones helper.
  NO reescribas la funcion principal: SOLO crea las helpers nuevas.

FORMATO DE RESPUESTA (obligatorio):
  Devuelve SOLO las funciones helper nuevas, una tras otra.
  NO incluyas la funcion original, ni explicaciones, ni markdown.
  Si la funcion no necesita helpers, responde exactamente: PASS

RESTRICCIONES (no negociables):
  1. Cada helper: nombre descriptivo, parametros explicitos, sin efectos secundarios
  2. Las helpers NO usan variables globales de la funcion original (pasarlas por parametro)
  3. NO uses imports nuevos
  4. Las helpers van a nivel de modulo (sin indentacion)
  5. NO dupliques nombres de funciones existentes

[CODIGO]
{func_source}"""


def _extraer_firma(codigo: str) -> str:
    """Extrae la firma (def ... :) de la primera función del código."""
    try:
        tree = ast.parse(codigo)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                args = [a.arg for a in node.args.args]
                return f"{node.name}({', '.join(args)})"
    except SyntaxError:
        return ""
    return ""


def apply_refactored(file_path: str, lineno: int, end_lineno: int, new_code: str) -> bool:
    path = Path(file_path)
    original = path.read_text(encoding="utf-8")
    lines = original.splitlines()

    new_code = clean_llm_response(new_code)
    if not new_code:
        log("  Respuesta LLM vacia tras limpiar")
        return False

    # Validar que la firma NO cambió (TASK-20260812-020): el LLM a veces la
    # altera pese a la restricción, rompiendo los llamadores del archivo.
    try:
        firma_original = _extraer_firma("\n".join(lines[lineno - 1 : lineno]))
        firma_nueva = _extraer_firma(new_code)
        if firma_original and firma_nueva and firma_original != firma_nueva:
            log(f"  Firma cambiada: '{firma_original}' -> '{firma_nueva}' — rechazado")
            return False
    except Exception as e:
        log(f"  No se pudo validar firma: {e}")

    try:
        compile(new_code, file_path, "exec")
    except SyntaxError as e:
        log(f"  Error sintaxis en respuesta: {e}")
        return False

    # Normalización determinista del DESPUÉS (TASK-20260812-020, diseño RAMON):
    # aplicar ruff fix+format a la respuesta ANTES de insertarla, para que la
    # indentación y estilo encajen con el archivo. Sin LLM (determinista).
    try:
        tmp = Path("/tmp") / f"_refactor_{os.getpid()}.py"
        tmp.write_text(new_code, encoding="utf-8")
        subprocess.run(
            [str(URA_ROOT / ".venv" / "bin" / "ruff"), "check", "--fix", "--unsafe-fixes", str(tmp)],
            capture_output=True, timeout=30, check=False,
        )
        subprocess.run(
            [str(URA_ROOT / ".venv" / "bin" / "ruff"), "format", str(tmp)],
            capture_output=True, timeout=30, check=False,
        )
        new_code_normalizado = tmp.read_text(encoding="utf-8")
        tmp.unlink(missing_ok=True)
        if new_code_normalizado.strip():
            new_code = new_code_normalizado
    except Exception as e:
        log(f"  Normalizacion ruff no disponible: {e}")

    new_lines = new_code.splitlines()
    result = lines[: lineno - 1] + new_lines + lines[end_lineno:]
    new_content = "\n".join(result)

    try:
        compile(new_content, file_path, "exec")
    except SyntaxError as e:
        # Sin reintento con LLM (determinista): si el reemplazo rompe el
        # archivo, se rechaza el refactor. El verificador de tests tampoco
        # llegaría a aplicarse sobre código roto.
        log(f"  Error sintaxis post-reemplazo: {e} — refactor rechazado (determinista)")
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


def refactor_one(func: dict) -> bool:  # noqa: PLR0915
    """Refactoriza una funcion con compactacion."""
    global REFACTORED, SKIPPED, ERRORS  # noqa: PLW0603

    file_path = func["file"]
    func_name = func["function"]
    lineno = func["lineno"]
    end_lineno = func["end_lineno"]
    n_lines = func["lines"]

    log(f"\n  Funcion: {func_name} ({n_lines}L) en {file_path}")

    # Memoria: regla determinista — si la función ya se completó o está
    # bloqueada para este modelo, no se reintenta (mínimo LLM).
    funcion_id = f"{file_path}:{func_name}"
    memoria_func = consultar_funcion(URA_ROOT, funcion_id)
    if memoria_func.get("estado") == "completada":
        log(f"  Memoria: {func_name} ya completada — saltando")
        SKIPPED += 1
        return False
    if memoria_func.get("estado") == "necesita_otro_modelo":
        log(f"  Memoria: {func_name} necesita otro modelo — intentando igual (fallback activo)")

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
    compactado, _anchors, stats = compactar(func_source)
    tokens_original = _estimar_tokens(func_source)
    tokens_compactado = _estimar_tokens(compactado)
    reduccion = round((1 - tokens_compactado / tokens_original) * 100, 1) if tokens_original else 0

    log(
        f"  Compactado: {stats['lineas_original']}L -> {stats['lineas_compactado']}L (-{reduccion}%)",
    )
    log(f"  Tokens: {tokens_original} -> {tokens_compactado} (-{reduccion}%)")

    # 2.5 FRACCIONAR por bloques (diseño RAMON, TASK-20260812-019): si la
    # función compactada excede el contexto óptimo, se parte por bloques
    # funcionales (AST) para que cada petición LLM sea pequeña.
    max_ctx = _ajustar_contexto(tokens_compactado)
    fragmentos = _fraccionar_ast(compactado, max_lineas=max(30, stats["lineas_compactado"] // 2 + 1))
    if len(fragmentos) > 1:
        log(f"  Fraccionado en {len(fragmentos)} bloques (contexto optimo ~{max_ctx} tokens)")

    # Baseline de tests (antes del refactor)
    baseline_tests = None
    if VERIFICAR_TESTS:
        try:
            tests_archivo = _tests_para_archivo(file_path)
            if tests_archivo:
                baseline_tests = ejecutar_tests(tests_archivo, timeout=30)
                if baseline_tests["ok"]:
                    log(f"  Tests baseline OK ({baseline_tests['ejecutados']})")
                else:
                    log(f"  Tests baseline con fallos ({baseline_tests['fallidos']}) — no bloqueará")
        except Exception as e:
            log(f"  Baseline tests no disponible: {e}")

    # 3. LLM con codigo compacto (por fragmentos)
    partes_refactorizadas: list[str] = []
    errores_frac = 0
    for idx, fragmento in enumerate(fragmentos):
        n_lineas_frac = fragmento.count("\n") + 1
        prompt = build_refactor_prompt(
            func_name,
            fragmento,
            n_lineas_frac,
            llamadores=_extraer_llamadores(file_path, func_name),
            contexto_rama=_construir_contexto_rama(file_path, func_name, fragmento),
        )
        t0 = time.time()
        response = llm(prompt)
        llm_time = round(time.time() - t0, 1)
        log(f"  LLM[{idx + 1}/{len(fragmentos)}]: {llm_time}s, {len(response)} chars")

        if not response:
            log("  LLM sin respuesta en fragmento")
            errores_frac += 1
            continue

        # 4. LIMPIAR respuesta (TASK-20260812-020): el LLM devuelve SOLO helpers.
        response_limpia = clean_llm_response(response)
        partes_refactorizadas.append(response_limpia)

    if errores_frac:
        log(f"  {errores_frac} fragmentos sin respuesta LLM")
        ERRORS += 1
        return False

    # Respuesta combinada de todos los fragmentos (solo helpers)
    codigo_helpers = "\n\n".join(partes_refactorizadas)

    # Normalización determinista de la respuesta (TASK-20260812-021): ruff
    # format para estandarizar indentación y quitar residuos de markdown.
    try:
        tmp = Path("/tmp") / f"_helpers_{os.getpid()}.py"
        tmp.write_text(codigo_helpers, encoding="utf-8")
        subprocess.run(
            [str(URA_ROOT / ".venv" / "bin" / "ruff"), "format", str(tmp)],
            capture_output=True, timeout=30, check=False,
        )
        norm = tmp.read_text(encoding="utf-8")
        tmp.unlink(missing_ok=True)
        if norm.strip():
            codigo_helpers = norm
    except Exception as e:
        log(f"  Normalizacion helpers no disponible: {e}")

    # Si el LLM no generó helpers (respondió PASS o solo código), no hay refactor
    if "PASS" in codigo_helpers.upper() and len(codigo_helpers.strip()) < 20:
        log("  LLM: no requiere helpers (PASS)")
        SKIPPED += 1
        registrar_intento(URA_ROOT, funcion_id, MODEL, "rechazo", "PASS (sin helpers)")
        return False

    # 4.5 EDICIÓN QUIRÚRGICA con AST (TASK-20260812-021, solución al 100%):
    # 1º intento: modo "solo helpers". 2º intento: modo diff completo.
    try:
        from edicion_ast import aplicar_helpers, diff_quirurgico

        firma_orig = _extraer_firma(func_source)
        fuente_original = Path(file_path).read_text(encoding="utf-8")

        # Intento 1: modo solo helpers
        ok_edicion, resultado = aplicar_helpers(fuente_original, codigo_helpers, firma_orig)
        if not ok_edicion:
            # Intento 2: el LLM devolvió la función completa — diff quirúrgico
            log(f"  Modo helpers falló ({resultado[:40]}...) — intentando diff quirúrgico")
            ok_edicion, resultado = diff_quirurgico(fuente_original, codigo_helpers, firma_orig)

        if not ok_edicion:
            log(f"  ❌ Edición rechazada (determinista): {resultado}")
            SKIPPED += 1
            registrar_intento(URA_ROOT, funcion_id, MODEL, "rechazo", f"edicion: {resultado[:40]}")
            return False
        codigo_final = resultado
    except ImportError:
        log("  edicion_ast no disponible — usando flujo anterior")
        codigo_final = codigo_helpers

    # 4.6 VERIFICAR con tests ANTES de aplicar (TASK-20260812-019):
    # si la edición rompe tests que antes pasaban, NO se aplica.
    if VERIFICAR_TESTS and baseline_tests is not None and baseline_tests["ok"]:
        try:
            veredicto = verificar_con_tests(
                file_path,
                antes=baseline_tests,
                nuevo_contenido=codigo_final,
                timeout=30,
            )
            if veredicto["veredicto"] == "rompe":
                log(f"  ❌ Refactor rechazado: rompe tests ({veredicto.get('regresiones', '')})")
                SKIPPED += 1
                registrar_intento(URA_ROOT, funcion_id, MODEL, "rechazo", "rompe tests")
                return False
            log(f"  ✅ Verificación tests: {veredicto['veredicto']}")
        except Exception as e:
            log(f"  Verificación tests no disponible: {e}")

    # 5. Aplicar (escribir el archivo con las helpers insertadas)
    if apply_refactored(file_path, lineno, end_lineno, codigo_final):
        REFACTORED += 1
        log("  Refactorizado con edicion quirurgica (helpers insertadas, original intacta)")
        registrar_intento(URA_ROOT, funcion_id, MODEL, "exito", "edicion quirurgica aplicada")
        return True
    ERRORS += 1
    registrar_intento(URA_ROOT, funcion_id, MODEL, "error", "apply_refactored fallo")
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

    global REFACTORED, SKIPPED, ERRORS, MIN_LINES, MAX_FUNCTIONS  # noqa: PLW0602

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
