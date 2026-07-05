"""Migrated commands from ura.py — developer workflow, system ops, RAG, diagnostics."""

import contextlib
import json
import shlex
import subprocess
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

from motor.core.config import UraConfig

ROOT = Path(__file__).resolve().parent.parent.parent
TARGET = "10.164.1.99"
OLLAMA_PORT = 11434
MAINTENANCE_SCRIPT = ROOT / "mantenimiento" / "ura_maintenance.py"


def _run(cmd, desc):
    print(f"  {desc}...", end=" ", flush=True, file=sys.stderr)
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT, check=False)
    if result.returncode == 0:
        print("\033[32mOK\033[0m", file=sys.stderr)
        return True, result.stdout
    print("\033[31mFALLÓ\033[0m", file=sys.stderr)
    if result.stderr:
        print(f"    {result.stderr.strip()[:200]}", file=sys.stderr)
    return False, result.stderr


def cmd_finalize(config: UraConfig, args):
    message = None
    for i, a in enumerate(args):
        if a == "-m" and i + 1 < len(args):
            message = args[i + 1]
            break

    print("\n\033[1mURA Pipeline de Finalización\033[0m", file=sys.stderr)
    print("=" * 40, file=sys.stderr)

    print("\n[0/5] Unit tests (56 checks: imports, schema, cache, IPs)", file=sys.stderr)
    ok, output = _run(["python3", "tests/test_unit.py"], "Unit tests")
    if not ok:
        print("  Ejecuta: python3 tests/test_unit.py", file=sys.stderr)
        return 1

    print("\n[1/5] Schema y compilación", file=sys.stderr)
    for f in ["core/config_manager.py", "core/model_router.py",
              "mantenimiento/ura_maintenance.py", "mantenimiento/ura_maintenance_remote.py"]:
        ok, _ = _run(["python3", "-m", "py_compile", f], f.split("/")[-1])
        if not ok:
            return 1

    from core.config_manager import validate_schema
    errors = validate_schema()
    if errors:
        print("  \033[31mERRORES DE ESQUEMA:\033[0m", file=sys.stderr)
        for e in errors:
            print(f"    - {e}", file=sys.stderr)
        return 1
    print("  Schema JSON... \033[32mOK\033[0m", file=sys.stderr)

    print("\n[2/5] Smoke test (clasificación + ruteo)", file=sys.stderr)
    ok, _ = _run(["python3", "core/model_router.py", "--test", "analizar bug en produccion"], "Router --test")
    if not ok:
        return 1

    staged = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True, text=True, cwd=ROOT, check=False,
    )
    if staged.stdout.strip():
        print("\n[3/5] Git: stage + commit", file=sys.stderr)
        subprocess.run(["git", "add", "-A"], cwd=ROOT, check=False)
        if message:
            commit_msg = message
        else:
            files = staged.stdout.strip().split("\n")[:3]
            commit_msg = (
                f"Pipeline: {' '.join(files)}" if len(files) <= 3
                else f"Pipeline: {files[0]} (+{len(files) - 1} más)"
            )
        ok, _ = _run(["git", "commit", "-m", commit_msg], f"commit: {commit_msg}")
        if not ok:
            return 1
    else:
        print("\n[3/5] Git: sin cambios para commitear", file=sys.stderr)

    print("\n[4/5] Git push", file=sys.stderr)
    ok, _ = _run(["git", "push"], "push")
    if not ok:
        print("  \033[33mPush falló (¿no hay remote?). Cambios solo en local.\033[0m", file=sys.stderr)

    print("\n\033[32m✅ PIPELINE COMPLETADO\033[0m", file=sys.stderr)
    return 0


def cmd_test(config: UraConfig, args):
    print("\n\033[1mURA Test Suite\033[0m", file=sys.stderr)
    print("=" * 40, file=sys.stderr)

    print("\n[Schema]", file=sys.stderr)
    from core.config_manager import get_base_dir, get_role, validate_config, validate_schema
    errors = validate_schema()
    if errors:
        print(f"  \033[31m{len(errors)} errores de esquema\033[0m", file=sys.stderr)
        for e in errors:
            print(f"    - {e}", file=sys.stderr)
    else:
        print("  \033[32mSchema OK\033[0m", file=sys.stderr)

    print("\n[Config]", file=sys.stderr)
    print(f"  Rol:      {get_role()}", file=sys.stderr)
    print(f"  Base dir: {get_base_dir()}", file=sys.stderr)
    from core.config_manager import CONFIG
    print(f"  Ollama:   {CONFIG['ollama']['host']}:{CONFIG['ollama']['port']}", file=sys.stderr)
    warnings = validate_config()
    if warnings:
        print(f"\n[Validación] \033[33m{warnings}\033[0m", file=sys.stderr)
    else:
        print("\n[Validación] \033[32mPaths OK\033[0m", file=sys.stderr)

    print("\n[Router]", file=sys.stderr)
    subprocess.run(["python3", "core/model_router.py", "--models"], cwd=ROOT, check=False)
    print("\n[Mantenimiento]", file=sys.stderr)
    subprocess.run(["python3", "mantenimiento/ura_maintenance.py", "--dry-run"], cwd=ROOT, check=False)
    return 0


def cmd_snapshot(config: UraConfig, args):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    snap_dir = ROOT / "data" / "snapshots"
    snap_dir.mkdir(parents=True, exist_ok=True)
    fname = snap_dir / f"{timestamp}.json"

    r = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=ROOT, check=False)
    test_r = subprocess.run(
        ["python3", str(ROOT / "tests" / "test_unit.py")],
        capture_output=True, text=True, cwd=ROOT, check=False,
    )
    test_pass = "PASS" if "TODOS LOS TESTS PASARON" in test_r.stdout else "FAIL"

    snap = {
        "date": datetime.now().isoformat(),
        "commit": r.stdout.strip(),
        "tests": test_pass,
        "branch": subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True, text=True, cwd=ROOT, check=False,
        ).stdout.strip(),
    }
    with open(fname, "w") as f:
        json.dump(snap, f, indent=2)
    print(f"Snapshot guardado: {fname}", file=sys.stderr)
    return 0


def cmd_maintenance(config: UraConfig, args):
    dry = "--dry-run" in args or "-d" in args
    if dry:
        print("\nEjecutando mantenimiento local (dry-run)...", file=sys.stderr)
        return subprocess.run(["python3", str(MAINTENANCE_SCRIPT), "--dry-run"], cwd=ROOT, check=False).returncode
    print("\nEjecutando mantenimiento REMOTO en GX10...", file=sys.stderr)
    return subprocess.run(
        ["ssh", f"{TARGET}", "cd ~/URA/ura_ia_1972 && python3 mantenimiento/ura_maintenance.py"],
        cwd=ROOT, check=False,
    ).returncode


def cmd_rotate(config: UraConfig, args):
    return subprocess.run(["bash", str(ROOT / "mantenimiento" / "rotate_logs.sh")], cwd=ROOT, check=False).returncode


def cmd_health(config: UraConfig, args):
    print("\nURA Health Check — GX10", file=sys.stderr)
    return subprocess.run(["python3", str(ROOT / "monitor" / "health_check.py")], cwd=ROOT, check=False).returncode


def cmd_alerts(config: UraConfig, args):
    print("\nURA Log Alerts — Sincronizando desde GX10", file=sys.stderr)
    return subprocess.run(["python3", str(ROOT / "monitor" / "log_alerts.py")], cwd=ROOT, check=False).returncode


def cmd_snc(config: UraConfig, args):
    """Estado del Sistema Nervioso Central — fetch desde GX10."""
    print("\nURA SNC — Fetching desde GX10...", file=sys.stderr)
    print(f"{'=' * 50}", file=sys.stderr)

    remote_state = Path.home() / "URA" / "logs" / "snc_state.json"

    with contextlib.suppress(Exception):
        subprocess.run(
            ["rsync", "-q", f"ramon@{TARGET}:/home/ramon/.ura/run/ura_snc_state.json", str(remote_state)],
            timeout=10, capture_output=True, check=False,
        )

    if remote_state.exists():
        try:
            with open(remote_state) as f:
                state = json.loads(f.read())
            ts = state.get("timestamp", "?")
            try:
                age = (datetime.now() - datetime.fromisoformat(ts)).total_seconds()
                age_str = f"{age:.0f}s" if age < 120 else f"{age / 60:.1f}min"
            except Exception:
                age_str = "?"

            status = state.get("status", "?")
            color = "\033[32m" if status == "OK" else "\033[31m"
            print(f"  Estado:    {color}{status}\033[0m (hace {age_str})", file=sys.stderr)
            print(f"  Timestamp: {ts}", file=sys.stderr)
            print(f"  OpenClaw:  {'🔴 ACTIVO' if state.get('openclaw_active') else '⚫ reposo'}", file=sys.stderr)
            print("\n  Servicios:", file=sys.stderr)
            for svc, info in state.get("services", {}).items():
                icon = "✅" if info.get("ok") else "❌"
                repair = ""
                if not info.get("ok") and info.get("repair_result"):
                    repair = f" → {info['repair_result']}"
                print(f"    {icon} {svc}{repair}", file=sys.stderr)
            if state.get("repair_attempts"):
                print("\n  Intentos de reparación:", file=sys.stderr)
                for svc, n in state["repair_attempts"].items():
                    if n > 0:
                        print(f"    {svc}: {n}", file=sys.stderr)
        except Exception as e:
            print(f"  Error: {e}", file=sys.stderr)
    else:
        print("  ⚠ Sin estado — ¿GX10 accesible? ¿SNC corriendo?", file=sys.stderr)
        print(f"  Verifica: ssh ramon@{TARGET} systemctl status snc", file=sys.stderr)

    print("\n  Monitor continuo: python3 monitor/snc_remote.py", file=sys.stderr)
    return 0


def cmd_doctor(config: UraConfig, args):
    """Diagnóstico completo del sistema."""
    print(f"\n{'=' * 60}", file=sys.stderr)
    print("  URA Doctor — Diagnóstico completo", file=sys.stderr)
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", file=sys.stderr)
    print(f"{'=' * 60}", file=sys.stderr)

    print("\n[1/6] Schema", file=sys.stderr)
    from core.config_manager import get_base_dir, get_role, validate_schema
    e = validate_schema()
    if e:
        print(f"  \033[31m{e[0]}\033[0m", file=sys.stderr)
    else:
        print(f"  \033[32mOK\033[0m — {get_role()} @ {get_base_dir()}", file=sys.stderr)

    print("\n[2/6] Compilación", file=sys.stderr)
    for f in ["core/config_manager.py", "core/model_router.py", "core/memory_engine.py", "ura.py"]:
        r = subprocess.run(["python3", "-m", "py_compile", f], cwd=ROOT, capture_output=True, check=False)
        icon = "\033[32m✓\033[0m" if r.returncode == 0 else "\033[31m✗\033[0m"
        print(f"  {icon} {f}", file=sys.stderr)

    print("\n[3/6] Tests (113)", file=sys.stderr)
    r = subprocess.run(
        ["python3", str(ROOT / "tests" / "test_unit.py")],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    if "TODOS LOS TESTS PASARON" in r.stdout:
        print("  \033[32m113/113 OK\033[0m", file=sys.stderr)
    else:
        fails = r.stdout.count("✗")
        print(f"  \033[31m{fails} tests fallaron\033[0m", file=sys.stderr)

    print("\n[4/6] Git", file=sys.stderr)
    r = subprocess.run(["git", "log", "--oneline", "-3"], cwd=ROOT, capture_output=True, text=True, check=False)
    for line in r.stdout.strip().split("\n"):
        print(f"  {line}", file=sys.stderr)

    print("\n[5/6] SNC State", file=sys.stderr)
    sf = Path.home() / "URA" / "logs" / "snc_state.json"
    if sf.exists():
        s = json.loads(sf.read_text())
        claw = "🔴" if s.get("openclaw_active") else "⚫"
        print(f"  Estado: {s.get('status', '?')} | OpenClaw: {claw} | {s.get('timestamp', '?')}", file=sys.stderr)
    else:
        print("  \033[33mSin estado remoto\033[0m", file=sys.stderr)

    print("\n[6/6] Docker (GX10)", file=sys.stderr)
    r = subprocess.run(
        ["ssh", "-o", "ConnectTimeout=3", "-o", "BatchMode=yes", f"ramon@{TARGET}",
         'docker ps --format "{{.Names}} ({{.Status}})" 2>/dev/null | head -6'],
        capture_output=True, text=True, timeout=10, check=False,
    )
    if r.returncode == 0 and r.stdout.strip():
        for line in r.stdout.strip().split("\n"):
            print(f"  {line}", file=sys.stderr)
    else:
        print("  \033[33mNo accesible\033[0m", file=sys.stderr)

    print(f"\n{'=' * 60}", file=sys.stderr)
    return 0


def cmd_metrics(config: UraConfig, args):
    """Métricas del router: modelos, latencia, cache."""
    print("\nURA Metrics — GX10", file=sys.stderr)
    print(f"{'=' * 50}", file=sys.stderr)
    try:
        r = urllib.request.urlopen(f"http://{TARGET}:{OLLAMA_PORT}/metrics", timeout=5)
        data = r.read().decode()
        print(f"  (datos de http://{TARGET}:{OLLAMA_PORT}/metrics)\n", file=sys.stderr)
        for line in data.split("\n"):
            if any(k in line for k in ("model_selection", "latency_avg", "cache_hit", "prompt_cache")):
                print(f"  {line}", file=sys.stderr)
    except Exception as e:
        print(f"  \033[33mNo se pudo conectar: {e}\033[0m", file=sys.stderr)
    print(f"\n{'=' * 50}", file=sys.stderr)
    return 0


def cmd_dashboard(config: UraConfig, args):
    """Dashboard unificado — lee del SNC state file + Git + Config local."""
    remote_state = Path.home() / "URA" / "logs" / "snc_state.json"
    local_state = Path.home() / ".ura" / "run" / "ura_snc_state.json"

    print(f"\n{'=' * 60}", file=sys.stderr)
    print(f"  URA Status Dashboard — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", file=sys.stderr)
    print(f"{'=' * 60}", file=sys.stderr)

    print("\n[SNC — Sistema Nervioso Central]", file=sys.stderr)
    state_file = remote_state if remote_state.exists() else (local_state if local_state.exists() else None)
    if state_file and state_file.exists():
        try:
            state = json.loads(state_file.read_text())
            ts = state.get("timestamp", "?")
            try:
                age = (datetime.now() - datetime.fromisoformat(ts)).total_seconds()
                age_str = f"{age:.0f}s" if age < 120 else f"{age / 60:.1f}min"
            except Exception:
                age_str = "?"
            status = state.get("status", "UNKNOWN")
            color = "\033[32m" if status == "OK" else "\033[31m"
            print(f"  Estado:    {color}{status}\033[0m (hace {age_str})", file=sys.stderr)
            print(f"  OpenClaw:  {'🔴 ACTIVO' if state.get('openclaw_active') else '⚫ reposo'}", file=sys.stderr)
            print("\n  Servicios:", file=sys.stderr)
            for svc, info in state.get("services", {}).items():
                icon = "✅" if info.get("ok") else "❌"
                repair = ""
                if not info.get("ok") and info.get("repair_result"):
                    repair = f" → {info['repair_result']}"
                print(f"    {icon} {svc}{repair}", file=sys.stderr)
            if state.get("repair_attempts"):
                print("\n  Intentos de reparación:", file=sys.stderr)
                for svc, n in state["repair_attempts"].items():
                    if n > 0:
                        print(f"    {svc}: {n}", file=sys.stderr)
        except Exception as e:
            print(f"  Error leyendo state file: {e}", file=sys.stderr)
    else:
        print("  ⚠ Sin estado del SNC. ¿SNC corriendo en GX10?", file=sys.stderr)
        print("  Ejecuta en GX10: python3 monitor/snc.py", file=sys.stderr)

    print("\n[Git]", file=sys.stderr)
    result = subprocess.run(["git", "log", "--oneline", "-3"], capture_output=True, text=True, cwd=ROOT, check=False)
    if result.returncode == 0:
        for line in result.stdout.strip().split("\n"):
            print(f"  {line}", file=sys.stderr)

    print("\n[Config local]", file=sys.stderr)
    from core.config_manager import get_base_dir, get_role
    print(f"  Rol:      {get_role()}", file=sys.stderr)
    print(f"  Base dir: {get_base_dir()}", file=sys.stderr)

    print(f"\n{'=' * 60}", file=sys.stderr)
    return 0


def cmd_index(config: UraConfig, args):
    """Indexar documentos en la memoria RAG."""
    force = "--force" in args or "-f" in args
    print(f"\nURA Memory Index {'(force)' if force else ''} [REMOTO en GX10]", file=sys.stderr)
    print(f"{'=' * 50}", file=sys.stderr)
    print("  Ejecutando indexación en sandbox mejora-continua...", file=sys.stderr)

    flag = "True" if force else "False"
    inner = (
        "from core.memory_engine import index_documents; "
        f"s=index_documents(force={flag}); print(s, file=sys.stderr)"
    )
    cmd = f"cd ~/URA/ura_ia_1972 && python3 -c \"{inner}\""
    result = subprocess.run(["ssh", TARGET, cmd], capture_output=True, text=True, cwd=ROOT, timeout=60, check=False)
    if result.returncode != 0:
        print(f"  \033[31mError: {result.stderr[:200]}\033[0m", file=sys.stderr)
        return 1
    try:
        stats = json.loads(result.stdout.strip())
    except json.JSONDecodeError as e:
        print(f"  \033[31mJSON decode error: {e}\033[0m", file=sys.stderr)
        print(f"  Raw output: {result.stdout[:300]}", file=sys.stderr)
        return 1
    if "error" in stats:
        print(f"  \033[33m{stats['error']}\033[0m", file=sys.stderr)
        return 1

    print(f"  Nuevos:     {stats.get('new', 0)}", file=sys.stderr)
    print(f"  Modificados:{stats.get('modified', 0)}", file=sys.stderr)
    print(f"  Sin cambios:{stats.get('unchanged', 0)}", file=sys.stderr)
    print(f"  Eliminados: {stats.get('deleted', 0)}", file=sys.stderr)
    print(f"  Chunks:     {stats.get('chunks_added', 0)}", file=sys.stderr)
    print("  \033[32mIndexación completada\033[0m", file=sys.stderr)
    return 0


def cmd_ask(config: UraConfig, args):
    """Consulta RAG: busca en documentos y responde con contexto."""
    question = " ".join(args) if args else None
    if not question:
        print('Uso: python3 ura.py ask "pregunta"', file=sys.stderr)
        return 1

    print(f"\nURA Memory — Buscando en GX10: {question}", file=sys.stderr)
    print(f"{'=' * 50}", file=sys.stderr)

    safe_q = shlex.quote(question)
    inner_py = (
        "from core.memory_engine import query; r=query(" + safe_q + "); "
        "for x in r: print(f\"[{x.get(chr(39)+chr(39))}] "
        "({x.get(chr(39)+chr(39), 0):.2f}) "
        "{x.get(chr(39)+chr(39), chr(39)+chr(39))[:200]}\")"
    )
    cmd = f"cd ~/URA/ura_ia_1972/ && python3 -c \"{inner_py}\""
    return subprocess.run(["ssh", TARGET, cmd], cwd=ROOT, timeout=30, check=False).returncode


def cmd_memory(config: UraConfig, args):
    """Estadisticas de la memoria RAG."""
    print("\nURA Memory Stats", file=sys.stderr)
    print(f"{'=' * 50}", file=sys.stderr)
    try:
        from core.memory_engine import DOCS_DIR, _chromadb_available, load_manifest
        manifest = load_manifest()
        print(f"  Documentos:  {manifest.get('total_documents', 0)}", file=sys.stderr)
        print(f"  Chunks:      {manifest.get('total_chunks', 0)}", file=sys.stderr)
        print(f"  Indexado:    {manifest.get('indexed_at', 'nunca')}", file=sys.stderr)
        print(f"  ChromaDB:    {'instalado' if _chromadb_available() else 'NO instalado'}", file=sys.stderr)
        print(f"  Directorio:  {DOCS_DIR}", file=sys.stderr)
        if manifest.get("files"):
            print("\n  Archivos indexados:", file=sys.stderr)
            for fname, info in sorted(manifest["files"].items()):
                print(f"    {fname} ({info.get('chunks', 0)} chunks)", file=sys.stderr)
    except Exception as e:
        print(f"  Error: {e}", file=sys.stderr)
        return 1
    return 0
