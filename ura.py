#!/usr/bin/env python3
"""URA CLI — Punto de entrada central del sistema.
Comandos: finalize, test, status, clean.
"""

import json
import shlex
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent
TEST_SCRIPT = ROOT / "tests" / "integration_smoke.sh"
MAINTENANCE_SCRIPT = ROOT / "mantenimiento" / "ura_maintenance.py"

# Valores por defecto para comandos de monitor
import contextlib

# PROFILE STARTUP
_STARTUP_START = time.perf_counter()

from core.config_manager import CONFIG as _CFG

_CONFIG_LOAD_TIME = time.perf_counter() - _STARTUP_START

TARGET = _CFG["ollama"]["host"]
OLLAMA_PORT = _CFG["ollama"]["port"]


def _run(cmd, desc):
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
    if result.returncode == 0:
        return True, result.stdout
    if result.stderr:
        pass
    return False, result.stderr


def cmd_finalize(args) -> int:
    message = None
    for i, a in enumerate(args):
        if a == "-m" and i + 1 < len(args):
            message = args[i + 1]
            break


    # CAPA 0: Unit tests (lo de ayer no se repite)
    ok, _output = _run(["python3", "tests/test_unit.py"], "Unit tests")
    if not ok:
        return 1

    # CAPA 1: Schema + compilación (instantáneo)
    ok, _ = _run(["python3", "-m", "py_compile", "core/config_manager.py"], "config_manager")
    if not ok:
        return 1
    ok, _ = _run(["python3", "-m", "py_compile", "core/model_router.py"], "model_router")
    if not ok:
        return 1
    ok, _ = _run(["python3", "-m", "py_compile", "mantenimiento/ura_maintenance.py"], "ura_maintenance")
    if not ok:
        return 1
    ok, _ = _run(["python3", "-m", "py_compile", "mantenimiento/ura_maintenance_remote.py"], "ura_maintenance_remote")
    if not ok:
        return 1

    from core.config_manager import validate_schema
    errors = validate_schema()
    if errors:
        for _e in errors:
            pass
        return 1

    # CAPA 2: Smoke test (Ollama inference)
    ok, _ = _run(["python3", "core/model_router.py", "--test", "analizar bug en produccion"], "Router --test")
    if not ok:
        return 1

    # CAPA 3: Commit (solo si hay cambios staged)
    staged = subprocess.run(["git", "diff", "--cached", "--name-only"],
                            capture_output=True, text=True, cwd=ROOT)
    if staged.stdout.strip():
        subprocess.run(["git", "add", "-A"], cwd=ROOT)

        if message:
            commit_msg = message
        else:
            files = staged.stdout.strip().split("\n")[:3]
            commit_msg = f"Pipeline: {' '.join(files)}" if len(files) <= 3 else f"Pipeline: {files[0]} (+{len(files)-1} más)"

        ok, _ = _run(["git", "commit", "-m", commit_msg], f"commit: {commit_msg}")
        if not ok:
            return 1
    else:
        pass

    # CAPA 4: Push
    ok, _ = _run(["git", "push"], "push")
    if not ok:
        pass

    return 0


def cmd_test(args) -> int:

    from core.config_manager import validate_config, validate_schema
    errors = validate_schema()
    if errors:
        for _e in errors:
            pass
    else:
        pass


    warnings = validate_config()
    if warnings:
        pass
    else:
        pass

    subprocess.run(["python3", "core/model_router.py", "--models"], cwd=ROOT)

    subprocess.run(["python3", "mantenimiento/ura_maintenance.py", "--dry-run"], cwd=ROOT)

    return 0


def cmd_maintenance(args):
    """Mantenimiento: local con dry-run, remoto sin dry-run."""
    dry = "--dry-run" in args or "-d" in args
    if dry:
        return subprocess.run(["python3", str(MAINTENANCE_SCRIPT), "--dry-run"], cwd=ROOT).returncode
    return subprocess.run(
        ["ssh", f"{TARGET}", "cd ~/URA/ura_ia_1972 && python3 mantenimiento/ura_maintenance.py"],
        cwd=ROOT,
    ).returncode


def cmd_rotate(args):
    return subprocess.run(["bash", str(ROOT / "mantenimiento" / "rotate_logs.sh")], cwd=ROOT).returncode


def cmd_snc(args) -> int:
    """Estado del Sistema Nervioso Central — fetch desde GX10."""
    remote_state = Path.home() / "URA" / "logs" / "snc_state.json"

    # Intentar rsync del state file
    with contextlib.suppress(Exception):
        subprocess.run(
            ["rsync", "-q", f"ramon@{TARGET}:/home/ramon/.ura/run/ura_snc_state.json", str(remote_state)],
            timeout=10, capture_output=True,
        )

    if remote_state.exists():
        try:
            with open(remote_state) as f:
                state = json.loads(f.read())
            ts = state.get("timestamp", "?")
            try:
                from datetime import datetime
                age = (datetime.now() - datetime.fromisoformat(ts)).total_seconds()
                f"{age:.0f}s" if age < 120 else f"{age/60:.1f}min"
            except Exception:
                pass

            state.get("status", "?")
            for info in state.get("services", {}).values():
                "✅" if info.get("ok") else "❌"
                if not info.get("ok") and info.get("repair_result"):
                    f" → {info['repair_result']}"
            if state.get("repair_attempts"):
                for n in state["repair_attempts"].values():
                    if n > 0:
                        pass
        except Exception:
            pass
    else:
        pass

    return 0


def cmd_health(args):
    return subprocess.run(["python3", str(ROOT / "monitor" / "health_check.py")], cwd=ROOT).returncode


def cmd_alerts(args):
    return subprocess.run(["python3", str(ROOT / "monitor" / "log_alerts.py")], cwd=ROOT).returncode


def cmd_index(args) -> int:
    """Indexar documentos en la memoria RAG."""
    force = "--force" in args or "-f" in args

    cmd = f"cd ~/URA/ura_ia_1972 && python3 -c \"from core.memory_engine import index_documents; s=index_documents(force={'True' if force else 'False'}); print(s)\""
    result = subprocess.run(["ssh", TARGET, cmd], capture_output=True, text=True, cwd=ROOT, timeout=60)
    if result.returncode != 0:
        return 1
    try:
        stats = json.loads(result.stdout.strip())
    except json.JSONDecodeError:
        return 1
    if "error" in stats:
        return 1

    return 0


def cmd_ask(args):
    """Consulta RAG: busca en documentos y responde con contexto."""
    question = " ".join(args) if args else None
    if not question:
        return 1


    safe_q = shlex.quote(question)
    cmd = f"cd ~/URA/ura_ia_1972 && python3 -c \"from core.memory_engine import query; r=query({safe_q}); [print(f'[{x.get(chr(39)+chr(39))}] ({x.get(chr(39)+chr(39),0):.2f}) {x.get(chr(39)+chr(39),chr(39)+chr(39))[:200]}') for x in r]\""
    return subprocess.run(["ssh", TARGET, cmd], cwd=ROOT, timeout=30).returncode


def cmd_memory(args) -> int:
    """Estadisticas de la memoria RAG."""
    try:
        from core.memory_engine import load_manifest
        manifest = load_manifest()
        if manifest.get("files"):
            for _fname, _info in sorted(manifest["files"].items()):
                pass
    except Exception:
        return 1
    return 0


def cmd_snapshot(args) -> int:
    """Guardar snapshot del estado del repo."""
    import json
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    snap_dir = ROOT / "data" / "snapshots"
    snap_dir.mkdir(parents=True, exist_ok=True)
    fname = snap_dir / f"{timestamp}.json"

    r = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=ROOT)
    test_r = subprocess.run(["python3", str(ROOT / "tests" / "test_unit.py")], capture_output=True, text=True, cwd=ROOT)
    test_pass = "PASS" if "TODOS LOS TESTS PASARON" in test_r.stdout else "FAIL"

    snap = {
        "date": datetime.now().isoformat(),
        "commit": r.stdout.strip(),
        "tests": test_pass,
        "branch": subprocess.run(["git","branch","--show-current"], capture_output=True, text=True, cwd=ROOT).stdout.strip(),
    }
    with open(fname, "w") as f:
        json.dump(snap, f, indent=2)
    return 0


def cmd_doctor(args) -> int:
    """Diagnóstico completo del sistema."""
    # 1. Schema
    from core.config_manager import validate_schema
    e = validate_schema()
    if e:
        pass
    else:
        pass

    # 2. Compilación
    for f in ["core/config_manager.py", "core/model_router.py", "core/memory_engine.py", "ura.py"]:
        r = subprocess.run(["python3", "-m", "py_compile", f], cwd=ROOT, capture_output=True)

    # 3. Tests
    r = subprocess.run(["python3", str(ROOT / "tests" / "test_unit.py")], cwd=ROOT, capture_output=True, text=True)
    if "TODOS LOS TESTS PASARON" in r.stdout:
        pass
    else:
        r.stdout.count("✗")

    # 4. Git
    r = subprocess.run(["git", "log", "--oneline", "-3"], cwd=ROOT, capture_output=True, text=True)
    for _line in r.stdout.strip().split("\n"):
        pass

    # 5. SNC
    sf = Path.home() / "URA" / "logs" / "snc_state.json"
    if sf.exists():
        import json
        s = json.loads(sf.read_text())
        "🔴" if s.get("openclaw_active") else "⚫"
    else:
        pass

    # 6. Docker (condicional)
    r = subprocess.run(
        ["ssh", "-o", "ConnectTimeout=3", "-o", "BatchMode=yes", f"ramon@{TARGET}",
         'docker ps --format "{{.Names}} ({{.Status}})" 2>/dev/null | head -6'],
        capture_output=True, text=True, timeout=10,
    )
    if r.returncode == 0 and r.stdout.strip():
        for _line in r.stdout.strip().split("\n"):
            pass
    else:
        pass

    return 0


def cmd_metrics(args) -> int:
    """Métricas del router: modelos, latencia, cache."""
    try:
        import urllib.request
        r = urllib.request.urlopen(f"http://{TARGET}:{OLLAMA_PORT}/metrics", timeout=5)
        data = r.read().decode()
        for line in data.split("\n"):
            if "model_selection" in line and "count" in line:
                pass
            if "latency_avg" in line:
                pass
            if "cache_hit" in line or "prompt_cache" in line:
                pass
    except Exception:
        pass
    return 0


def cmd_status(args) -> int:
    """Dashboard unificado — lee del SNC state file."""
    remote_state = Path.home() / "URA" / "logs" / "snc_state.json"
    local_state = Path.home() / ".ura" / "run" / "ura_snc_state.json"


    # 1. SNC State (fuente de verdad)
    state_file = remote_state if remote_state.exists() else (local_state if local_state.exists() else None)
    if state_file and state_file.exists():
        try:
            state = json.loads(state_file.read_text())
            ts = state.get("timestamp", "?")
            try:
                age = (datetime.now() - datetime.fromisoformat(ts)).total_seconds()
                f"{age:.0f}s" if age < 120 else f"{age/60:.1f}min"
            except Exception:
                pass
            state.get("status", "UNKNOWN")
            for info in state.get("services", {}).values():
                "✅" if info.get("ok") else "❌"
                if not info.get("ok") and info.get("repair_result"):
                    f" → {info['repair_result']}"
            if state.get("repair_attempts"):
                for n in state["repair_attempts"].values():
                    if n > 0:
                        pass
        except Exception:
            pass
    else:
        pass

    # 2. Git
    result = subprocess.run(["git", "log", "--oneline", "-3"], capture_output=True, text=True, cwd=ROOT)
    if result.returncode == 0:
        for _line in result.stdout.strip().split("\n"):
            pass

    # 3. Config local

    return 0


def main():
    _MAIN_START = time.perf_counter()
    _MAIN_LOAD_TIME = _MAIN_START - _STARTUP_START

    if len(sys.argv) < 2:
        return 0

    cmd = sys.argv[1]
    args = sys.argv[2:]

    if cmd == "finalize":
        return cmd_finalize(args)
    if cmd == "test":
        return cmd_test(args)
    if cmd in ("clean", "maintenance"):
        return cmd_maintenance(args)
    if cmd == "rotate":
        return cmd_rotate(args)
    if cmd in ("heartbeat", "snc"):
        return cmd_snc(args)
    if cmd == "health":
        return cmd_health(args)
    if cmd in ("alerts", "logs"):
        return cmd_alerts(args)
    if cmd == "doctor":
        return cmd_doctor(args)
    if cmd == "metrics":
        return cmd_metrics(args)
    if cmd == "snapshot":
        return cmd_snapshot(args)
    if cmd == "status":
        return cmd_status(args)
    if cmd == "index":
        return cmd_index(args)
    if cmd == "ask":
        return cmd_ask(args)
    return 1


if __name__ == "__main__":
    sys.exit(main())
