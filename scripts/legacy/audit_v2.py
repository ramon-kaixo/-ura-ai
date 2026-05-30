#!/usr/bin/env python3
"""
audit_v2.py — Auditoría masiva v2 con retry, backoff y rate limiting.
"""

import json
import os
import time
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime

PROJECT = Path.home() / "URA" / "ura_ia_1972"
OUTDIR = Path.home() / "logs" / "auditoria_pendientes"
OUTDIR.mkdir(parents=True, exist_ok=True)
API_URL = "http://10.164.1.99:8288/v1/chat/completions"
MODEL = "codestral-22b"
TIMEOUT = 480
MAX_RETRIES = 3
RETRY_DELAY = 10
INTER_REQUEST_DELAY = 3

AUDITADOS = {
    "core/sandbox.py",
    "core/autonomous_agent.py",
    "core/hermetic_states.py",
    "core/conversation_truncator.py",
    "core/system_prompt.py",
    "core/action_signer.py",
    "core/central_router.py",
    "core/timeout_manager.py",
    "core/security/command_whitelist.py",
    "core/security/jailbreak_guard.py",
    "core/security/input_sanitizer.py",
    "agents/registry.py",
    "core/payment_guardian.py",
    "core/forensic_scribe.py",
    "core/ura_metaconsciousness.py",
    "core/ura_value_system.py",
    "core/smart_cache.py",
    "core/code_assistant.py",
    "core/dual_verification.py",
    "core/error_cross_reference.py",
    "core/conflict_detector.py",
    "core/research_pipeline.py",
    "core/vocabulary_department.py",
    "core/sandbox_orchestrator.py",
}

IGNORE_DIRS = {".venv", "tests", "node_modules", "__pycache__", ".git", "archive", "docs"}

SYSTEM_PROMPT = """Eres un revisor de código Python senior en el proyecto URA.
Tu tarea: encontrar SOLO bugs reales que romperían en producción.

Reglas:
1. SOLO reporta bugs con formato: LINEA | QUE FALLA | COMO ARREGLARLO
2. NO reportes estilo PEP8, sugerencias ni opiniones
3. Si no hay bugs: responde SOLO "OK"
4. Máximo 3 líneas por bug. Se conciso."""

TEMPLATE = """Revisa este archivo Python del proyecto URA:

{filename} ({line_count} líneas)
{context}

Código:
```python
{code}
```"""

BUG_PROMPT = """Al final de tu revisión, clasifica el resultado:
- Si encontraste bugs reales: enuméralos con formato LINEA | DESCRIPCIÓN
- Si no hay bugs: escribe SOLO "OK"
- Si el archivo es trivial o solo contiene definiciones simples: escribe "TRIVIAL"

¿Tiene bugs reales este archivo?"""


def call_api(payload: dict, retries: int = MAX_RETRIES) -> dict | None:
    """Llama a la API con retry y backoff exponencial."""
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                API_URL,
                data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:  # nosec B310
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            if e.code == 503 or e.code == 500:
                wait = RETRY_DELAY * (2**attempt)
                print(f"  ⚠️ HTTP {e.code}, reintentando en {wait}s...")
                time.sleep(wait)
            else:
                return None
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            wait = RETRY_DELAY * (2**attempt)
            print(f"  ⚠️ {e}, reintentando en {wait}s...")
            time.sleep(wait)
        except Exception:
            return None
    return None


def get_context(filepath: str) -> str:
    """Contexto basado en la ruta del archivo."""
    parts = Path(filepath).parts
    ctx_map = {
        "agents": "Agente autónomo del sistema URA.",
        "connectors": "Conector externo (API, DB, servicio web).",
        "dashboard": "Archivo del dashboard web.",
        "handlers": "Manejador de eventos/webhooks.",
        "nodes": "Nodo de procesamiento en flujos.",
        "scripts": "Script de utilidad/herramienta.",
        "services": "Servicio del sistema (router, whisper, etc.).",
    }
    if len(parts) >= 2 and parts[0] in ctx_map:
        return ctx_map[parts[0]]
    name = Path(filepath).stem.lower()
    if "test" in name:
        return "Test unitario/de integración."
    if "config" in name or "setting" in name:
        return "Archivo de configuración."
    return "Archivo del sistema URA."


def review_file(filepath: str) -> dict:
    """Revisa un archivo con el modelo."""
    full_path = PROJECT / filepath
    if not full_path.exists():
        return {"status": "not_found", "result": "", "bugs": None, "trivial": False}

    try:
        code = full_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return {
            "status": "error",
            "result": "Error leyendo archivo",
            "bugs": None,
            "trivial": False,
        }

    line_count = len(code.split("\n"))
    MAX_CHARS = 12000
    if len(code) > MAX_CHARS:
        code = code[:MAX_CHARS] + "\n\n... [ARCHIVO TRUNCADO] ..."

    user_msg = TEMPLATE.format(
        filename=filepath, line_count=line_count, context=get_context(filepath), code=code
    )

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        "max_tokens": 1200,
        "temperature": 0.1,
    }

    data = call_api(payload)
    if data is None:
        return {
            "status": "error",
            "result": "Sin respuesta tras reintentos",
            "bugs": None,
            "trivial": False,
        }

    try:
        content = data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError):
        return {"status": "error", "result": "Respuesta malformada", "bugs": None, "trivial": False}

    # Clasificar resultado
    content_lower = content.lower()
    if content_lower.strip() == "ok":
        return {"status": "ok", "result": content, "bugs": False, "trivial": True}
    if "trivial" in content_lower:
        return {"status": "ok", "result": "[TRIVIAL]", "bugs": None, "trivial": True}

    has_bugs = any(
        kw in content_lower for kw in ["linea", "línea", "bug", "error", "falla", "fix", "arreglar"]
    )
    return {"status": "ok", "result": content, "bugs": has_bugs, "trivial": False}


def main():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    out_file = OUTDIR / f"audit_v2_{timestamp}.json"
    report_file = OUTDIR / f"reporte_v2_{timestamp}.md"

    # Obtener archivos pendientes
    all_files = []
    for root, dirs, files in os.walk(PROJECT):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        for f in files:
            if f.endswith(".py"):
                all_files.append(os.path.relpath(os.path.join(root, f), PROJECT))

    pending = sorted([f for f in all_files if f not in AUDITADOS])
    total = len(pending)

    print("╔══════════════════════════════════════════╗")
    print(f"║  AUDITORÍA v2 — {timestamp}                   ║")
    print(f"║  Archivos pendientes: {total:<20} ║")
    print(f"║  Modelo: {MODEL:<31} ║")
    print(f"║  API: {API_URL} ║")
    print("╚══════════════════════════════════════════╝")

    results = {}
    bugs_found = 0
    errors = 0
    trivial = 0
    start_time = time.time()

    for i, filepath in enumerate(pending, 1):
        print(f"\n[{i}/{total}] {filepath}")
        result = review_file(filepath)
        results[filepath] = result

        if result["status"] == "error":
            errors += 1
            print(f"  ❌ ERROR: {result['result'][:80]}")
        elif result["trivial"]:
            trivial += 1
            print(f"  ⏭️ TRIVIAL ({result.get('result', '?')[:50]})")
        elif result["bugs"]:
            bugs_found += 1
            first = result["result"].split("\n")[0][:120]
            print(f"  🔴 BUG: {first}")
        else:
            trivial += 1
            print(f"  ✅ OK ({len(Path(filepath).read_text().split(chr(10)))} líneas)")

        elapsed = time.time() - start_time
        rate = i / elapsed if elapsed > 0 else 0
        eta = (total - i) / rate if rate > 0 else 0
        print(f"  ⏱️ {elapsed:.0f}s transcurridos, ~{eta:.0f}s restantes")

        # Guardar progreso cada 5 archivos
        if i % 5 == 0 or i == total:
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "v": 2,
                        "timestamp": timestamp,
                        "total": total,
                        "processed": i,
                        "bugs": bugs_found,
                        "errors": errors,
                        "trivial": trivial,
                        "results": results,
                    },
                    f,
                    ensure_ascii=False,
                    indent=2,
                )
            print(f"  💾 Guardado: {i}/{total}")

        # Delay entre peticiones
        time.sleep(INTER_REQUEST_DELAY)

    # Reporte Markdown
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(f"# Auditoría Completa URA v2 — {timestamp}\n\n")
        f.write(
            f"**Total:** {total} | **Bugs:** {bugs_found} | **Errores:** {errors} | **Triviales/OK:** {trivial}\n"
        )
        f.write(f"**Duración:** {time.time() - start_time:.0f}s | **Modelo:** {MODEL}\n\n")
        f.write("---\n\n")
        for filepath, r in results.items():
            if r["status"] == "error":
                f.write(f"## {filepath}\n⚠️ {r['result']}\n\n")
            elif r["bugs"]:
                f.write(f"## {filepath}\n```\n{r['result']}\n```\n\n")

    # Copiar al proyecto
    import shutil

    dest = PROJECT / "docs" / f"AUDITORIA_PENDIENTES_{timestamp}.md"
    shutil.copy2(report_file, dest)
    print(f"\n{'=' * 50}")
    print(f"COMPLETADO: {total} archivos | {bugs_found} bugs | {errors} errores")
    print(f"Reporte: {report_file}")
    print(f"Copiado: {dest}")


if __name__ == "__main__":
    main()
