"""Migrated commands from ura.py — developer workflow, system ops, RAG, diagnostics."""

import contextlib
import json
import os
import shlex
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

from motor.core.config import UraConfig
from motor.core.executor import SubprocessExecutor

ROOT = Path(__file__).resolve().parent.parent.parent
TARGET = "10.164.1.99"
OLLAMA_PORT = 11434
MAINTENANCE_SCRIPT = ROOT / "scripts" / "pro" / "tuneladora_mantenimiento.py"
_executor = SubprocessExecutor()


def _memory_path() -> Path:
    return Path(os.environ.get("URA_MEMORY_DB", str(Path.home() / ".ura" / "memory.db")))


def _run(cmd, _desc):
    result = _executor.run(cmd, cwd=str(ROOT))
    if result.ok:
        return True, result.stdout
    if result.stderr:
        pass
    return False, result.stderr


def cmd_finalize(config: UraConfig, args) -> int:
    message = None
    for i, a in enumerate(args):
        if a == "-m" and i + 1 < len(args):
            message = args[i + 1]
            break

    ok, _output = _run(["python3", "tests/test_unit.py"], "Unit tests")
    if not ok:
        return 1

    for f in [
        "core/config_manager.py",
        "core/model_router_main.py",
        "scripts/pro/tuneladora_mantenimiento.py",
        "scripts/pro/tuneladora_mejora.py",
    ]:
        ok, _ = _run(["python3", "-m", "py_compile", f], f.split("/")[-1])
        if not ok:
            return 1

    from core.config_manager import validate_schema

    errors = validate_schema()
    if errors:
        for _e in errors:
            pass
        return 1

    ok, _ = _run(["python3", "core/model_router_main.py", "--test", "analizar bug en produccion"], "Router --test")
    if not ok:
        return 1

    staged = _executor.run(["git", "diff", "--cached", "--name-only"], cwd=str(ROOT))
    if staged.stdout.strip():
        _executor.run(["git", "add", "-A"], cwd=str(ROOT))
        if message:
            commit_msg = message
        else:
            files = staged.stdout.strip().split("\n")[:3]
            commit_msg = (
                f"Pipeline: {' '.join(files)}" if len(files) <= 3 else f"Pipeline: {files[0]} (+{len(files) - 1} más)"
            )
        ok, _ = _run(["git", "commit", "-m", commit_msg], f"commit: {commit_msg}")
        if not ok:
            return 1
    else:
        pass

    ok, _ = _run(["git", "push"], "push")
    if not ok:
        pass

    return 0


def cmd_test(config: UraConfig, args) -> int:
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

    _executor.run(["python3", "core/model_router_main.py", "--models"], cwd=str(ROOT))
    _executor.run(["python3", "mantenimiento/ura_maintenance.py", "--dry-run"], cwd=str(ROOT))
    return 0


def cmd_snapshot(config: UraConfig, args) -> int:
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    snap_dir = ROOT / "data" / "snapshots"
    snap_dir.mkdir(parents=True, exist_ok=True)
    fname = snap_dir / f"{timestamp}.json"

    r = _executor.run(["git", "rev-parse", "HEAD"], cwd=str(ROOT))
    test_r = _executor.run(
        ["python3", str(ROOT / "tests" / "test_unit.py")],
        cwd=str(ROOT),
    )
    test_pass = "PASS" if "TODOS LOS TESTS PASARON" in test_r.stdout else "FAIL"

    snap = {
        "date": datetime.now(UTC).isoformat(),
        "commit": r.stdout.strip(),
        "tests": test_pass,
        "branch": _executor.run(
            ["git", "branch", "--show-current"],
            cwd=str(ROOT),
        ).stdout.strip(),
    }
    with open(fname, "w") as f:  # noqa: PTH123
        json.dump(snap, f, indent=2)
    return 0


def cmd_maintenance(config: UraConfig, args):
    dry = "--dry-run" in args or "-d" in args
    if dry:
        return _executor.run(["python3", str(MAINTENANCE_SCRIPT), "--dry-run"], cwd=str(ROOT)).returncode
    return _executor.run(
        ["ssh", TARGET, "cd ~/URA/ura_ia_1972 && python3 mantenimiento/ura_maintenance.py"],
        cwd=str(ROOT),
    ).returncode


def cmd_rotate(config: UraConfig, args):
    return _executor.run(["bash", str(ROOT / "mantenimiento" / "rotate_logs.sh")], cwd=str(ROOT)).returncode


def cmd_health(config: UraConfig, args):
    return _executor.run(["python3", str(ROOT / "monitor" / "health_check.py")], cwd=str(ROOT)).returncode


def cmd_system(config: UraConfig, args):
    """Estado unificado del sistema: salud, memoria, version, pipeline."""
    from motor.observability.health import HealthRegistry
    from motor.intelligence.memory.hybrid import HybridMemory

    hr = HealthRegistry()
    hr.register_component("cli")
    hr.set_healthy("cli")

    mem = HybridMemory(db_path=str(_memory_path()))
    mem_health = mem.health()

    import subprocess as _sp

    version = "unknown"
    try:
        version = _sp.run(
            ["git", "describe", "--tags", "--abbrev=0"], capture_output=True, text=True, timeout=5, check=False
        ).stdout.strip()
    except Exception:  # noqa: S110
        pass

    lines = [
        f"URA v{version}",
        f"{'=' * 40}",
        f"  Salud:     {hr.snapshot().get('global', 'unknown')}",
        f"  Memoria:   {mem_health.get('total_records', 'N/A')} registros",
        f"  Vector:    {'OK' if mem_health.get('vector_store_ok') else 'OFF'}",
        f"  Python:    3.12",
        f"  Entorno:   {ROOT}",
        f"{'=' * 40}",
        f"  endpoints:",
        f"    /health   → metrics_server:{os.environ.get('METRICS_PORT', '9091')}",
        f"    /memory   → memoria hibrida",
        f"    /dashboard→ dashboard web",
        f"    /version  → version del sistema",
        f"{'=' * 40}",
    ]
    for line in lines:
        print(line)
    return 0


def cmd_alerts(config: UraConfig, args):
    return _executor.run(["python3", str(ROOT / "monitor" / "log_alerts.py")], cwd=str(ROOT)).returncode


def cmd_snc(config: UraConfig, args) -> int:
    """Estado del Sistema Nervioso Central — fetch desde GX10."""
    remote_state = Path.home() / "URA" / "logs" / "snc_state.json"

    with contextlib.suppress(Exception):
        _executor.run(
            ["rsync", "-q", f"ramon@{TARGET}:/home/ramon/.ura/run/ura_snc_state.json", str(remote_state)],
            timeout=10,
        )

    if remote_state.exists():
        try:
            with open(remote_state) as f:  # noqa: PTH123
                state = json.loads(f.read())
            ts = state.get("timestamp", "?")
            try:
                age = (datetime.now(UTC) - datetime.fromisoformat(ts)).total_seconds()
                f"{age:.0f}s" if age < 120 else f"{age / 60:.1f}min"
            except Exception:  # noqa: S110
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
        except Exception:  # noqa: S110
            pass
    else:
        pass

    return 0


def cmd_doctor(config: UraConfig, args) -> int:
    """Diagnóstico completo del sistema."""
    from core.config_manager import validate_schema

    e = validate_schema()
    if e:
        pass
    else:
        pass

    for f in ["core/config_manager.py", "core/model_router_main.py", "core/memory_engine.py", "ura.py"]:
        r = _executor.run(["python3", "-m", "py_compile", f], cwd=str(ROOT))

    r = _executor.run(
        ["python3", str(ROOT / "tests" / "test_unit.py")],
        cwd=str(ROOT),
    )
    if "TODOS LOS TESTS PASARON" in r.stdout:
        pass
    else:
        r.stdout.count("✗")

    r = _executor.run(["git", "log", "--oneline", "-3"], cwd=str(ROOT))
    for _line in r.stdout.strip().split("\n"):
        pass

    sf = Path.home() / "URA" / "logs" / "snc_state.json"
    if sf.exists():
        s = json.loads(sf.read_text())
        "🔴" if s.get("openclaw_active") else "⚫"
    else:
        pass

    r = _executor.run(
        [
            "ssh",
            "-o",
            "ConnectTimeout=3",
            "-o",
            "BatchMode=yes",
            f"ramon@{TARGET}",
            'docker ps --format "{{.Names}} ({{.Status}})" 2>/dev/null | head -6',
        ],
        timeout=10,
    )
    if r.returncode == 0 and r.stdout.strip():
        for _line in r.stdout.strip().split("\n"):
            pass
    else:
        pass

    return 0


def cmd_metrics(config: UraConfig, args) -> int:
    """Métricas del router: modelos, latencia, cache."""
    try:
        with urllib.request.urlopen(f"http://{TARGET}:{OLLAMA_PORT}/metrics", timeout=5) as r:  # nosec B310
            data = r.read().decode()
        for line in data.split("\n"):
            if any(k in line for k in ("model_selection", "latency_avg", "cache_hit", "prompt_cache")):
                pass
    except Exception:  # noqa: S110
        pass
    return 0


def cmd_dashboard(config: UraConfig, args) -> int:
    """Dashboard unificado — lee del SNC state file + Git + Config local."""
    remote_state = Path.home() / "URA" / "logs" / "snc_state.json"
    local_state = Path.home() / ".ura" / "run" / "ura_snc_state.json"

    state_file = remote_state if remote_state.exists() else (local_state if local_state.exists() else None)
    if state_file and state_file.exists():
        try:
            state = json.loads(state_file.read_text())
            ts = state.get("timestamp", "?")
            try:
                age = (datetime.now(UTC) - datetime.fromisoformat(ts)).total_seconds()
                f"{age:.0f}s" if age < 120 else f"{age / 60:.1f}min"
            except Exception:  # noqa: S110
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
        except Exception:  # noqa: S110
            pass
    else:
        pass

    result = _executor.run(["git", "log", "--oneline", "-3"], cwd=str(ROOT))
    if result.returncode == 0:
        for _line in result.stdout.strip().split("\n"):
            pass

    return 0


def cmd_index(config: UraConfig, args) -> int:
    """Indexar documentos en la memoria RAG."""
    force = "--force" in args or "-f" in args

    flag = "True" if force else "False"
    inner = (
        f"from core.memory_engine import index_documents; s=index_documents(force={flag}); print(s, file=sys.stderr)"
    )
    cmd = f'cd ~/URA/ura_ia_1972 && python3 -c "{inner}"'
    result = _executor.run(["ssh", TARGET, cmd], cwd=str(ROOT), timeout=60)
    if result.returncode != 0:
        return 1
    try:
        stats = json.loads(result.stdout.strip())
    except json.JSONDecodeError:
        return 1
    if "error" in stats:
        return 1

    return 0


def cmd_ask(config: UraConfig, args):
    """RAG completo: recupera documentos y genera respuesta con LLM."""
    question = " ".join(args) if args else None
    if not question:
        return 1

    safe_q = shlex.quote(question)
    inner_py = "from core.memory_engine import ask; print(ask(" + safe_q + "))"
    cmd = f'cd ~/URA/ura_ia_1972/ && python3 -c "{inner_py}"'
    result = _executor.run(["ssh", TARGET, cmd], cwd=str(ROOT), timeout=120)
    if result.ok and result.stdout:
        return 0
    if result.stderr:
        pass
    return result.returncode or 1


def cmd_memory(config: UraConfig, args) -> int:
    """Estadísticas y operaciones de la memoria híbrida."""
    from motor.intelligence.memory.hybrid import HybridMemory

    mem = HybridMemory(db_path=str(_memory_path()))
    health = mem.health()
    total = health.get("total_records", 0)

    print(f"Memoria Híbrida")
    print(f"{'=' * 40}")
    print(f"  Registros:     {total}")
    print(f"  Vector Store:  {'OK' if health.get('vector_store_ok') else 'OFF'}")
    print()

    if args and hasattr(args, "raw") and args.raw:
        cmd = args.raw[0] if args.raw else ""
        if cmd == "search" and len(args.raw) > 1:
            query = " ".join(args.raw[1:])
            results = mem.search(query, k=5)
            print(f"Búsqueda: '{query}' ({len(results)} resultados)")
            for i, r in enumerate(results, 1):
                print(f"  {i}. [{r.type.value}] {r.payload[:100]}...")
        elif cmd == "store" and len(args.raw) > 1:
            text = " ".join(args.raw[1:])
            rid = mem.store(payload=text)
            print(f"Almacenado: {rid}")
        elif cmd == "web" and len(args.raw) > 1:
            query = " ".join(args.raw[1:])
            try:
                import asyncio
                from core.mochila.tools import web_search as _web_search

                result = asyncio.run(_web_search(query, max_results=5))
                print(f"Web search: '{query}'")
                for item in result.get("results", []):
                    print(f"  - {item.get('title', '?')}")
                    print(f"    {item.get('snippet', '')[:120]}")
            except Exception as e:
                print(f"Web search falló: {e}")
        elif cmd == "backup":
            import shutil
            from datetime import UTC, datetime

            backup_dir = Path(os.environ.get("URA_BACKUP_DIR", str(Path.home() / ".ura" / "backups")))
            backup_dir.mkdir(parents=True, exist_ok=True)
            ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
            dest = backup_dir / f"memory_{ts}.db"
            shutil.copy2(str(_memory_path()), str(dest))
            print(f"Backup: {dest} ({dest.stat().st_size} bytes)")
        elif cmd == "restore" and len(args.raw) > 1:
            src = Path(args.raw[1])
            import shutil

            if not src.exists():
                print(f"Error: {src} no existe")
                return 1
            dest = _memory_path()
            # Backup actual antes de restaurar
            from datetime import UTC, datetime

            backup_dir = Path(os.environ.get("URA_BACKUP_DIR", str(Path.home() / ".ura" / "backups")))
            backup_dir.mkdir(parents=True, exist_ok=True)
            ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
            shutil.copy2(str(dest), str(backup_dir / f"pre_restore_{ts}.db"))
            shutil.copy2(str(src), str(dest))
            print(f"Restaurado: {src} → {dest}")
            print(f"Backup pre-restore: {backup_dir / f'pre_restore_{ts}.db'}")
        else:
            print("Subcomandos:")
            print("  ura memory search <query>     — buscar en memoria")
            print("  ura memory store <text>       — almacenar texto")
            print("  ura memory web <query>        — buscar en web")
            print("  ura memory backup             — respaldar memoria")
            print("  ura memory restore <archivo>  — restaurar desde backup")
    return 0


def _systemctl(args: list[str]) -> "subprocess.CompletedProcess":
    import subprocess as _sp

    r = _sp.run([*["systemctl", "--user"], *args], capture_output=True, text=True, timeout=30, check=False)
    if r.returncode == 0 or "Could not connect" not in r.stderr:
        return r
    return _sp.run([*["systemctl"], *args], capture_output=True, text=True, timeout=30, check=False)


def cmd_service(config: UraConfig, args) -> int:
    """Gestiona servicios del sistema (start/stop/status)."""
    if not _systemctl([]).stdout and not _systemctl([]).stderr:
        print("systemctl no disponible en este sistema")
        return 1

    if args and hasattr(args, "raw") and args.raw:
        action = args.raw[0]
        service = args.raw[1] if len(args.raw) > 1 else ""
        if action == "list":
            r = _systemctl(["list-units", "--type=service", "--all", "--no-pager", "--plain"])
            for line in r.stdout.splitlines():
                if "ura-" in line:
                    parts = line.split()
                    if len(parts) >= 3:
                        print(f"  {parts[0]:45} {parts[2]:15} {parts[1]}")
        elif service:
            r = _systemctl([action, service])
            if r.returncode == 0:
                print(f"systemctl {action} {service}: OK")
            else:
                print(f"systemctl {action} {service}: {r.stderr.strip() or r.stdout.strip()}")
        else:
            print("Uso: ura service <start|stop|restart|status> <nombre>")
    else:
        r = _systemctl(["list-units", "--type=service", "--all", "--no-pager", "--plain"])
        servicios = [l for l in r.stdout.splitlines() if "ura-" in l]
        print(f"Servicios URA ({len(servicios)}):")
        for s in servicios:
            parts = s.split()
            if len(parts) >= 3:
                print(f"  {parts[0]:45} {parts[2]:15} {parts[1]}")
    return 0


def cmd_audit(config: UraConfig, args) -> int:
    """Auditoría arquitectónica completa (ARQ)."""
    import json
    import subprocess
    import sys

    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts/pro/arq_auditor.py"), "--json"],
        capture_output=True, text=True, timeout=120, cwd=str(ROOT), check=False,
    )
    if r.returncode != 0 or not r.stdout:
        print(f"ARQ Auditor falló: {r.stderr[:200]}")
        return 1

    data = json.loads(r.stdout)
    blocks = data.get("blocks", {})
    total_fail = sum(1 for b in blocks.values() for f in b if f.get("level") in ("FAIL", "P0"))
    total_warn = sum(1 for b in blocks.values() for f in b if f.get("level") in ("WARNING", "MEDIUM"))
    files_scanned = data.get("files_scanned", 0)

    print(f"\n📊 Auditoría Arquitectónica — {data.get('version', '?')}")
    print(f"{'='*60}")
    print(f"  Archivos: {files_scanned}  |  FAIL: {total_fail}  |  WARN: {total_warn}")
    print()

    for bid in sorted(blocks.keys()):
        items = blocks[bid]
        if not items:
            print(f"  [{bid}] ✅ — 0 hallazgos")
            continue
        fails = sum(1 for f in items if f.get("level") in ("FAIL", "P0"))
        warns = sum(1 for f in items if f.get("level") in ("WARNING", "MEDIUM"))
        icon = "❌" if fails else "⚠️" if warns else "ℹ️"
        print(f"  [{bid}] {icon} — {len(items)} hallazgos ({fails} FAIL, {warns} WARN)")
        for f in items[:2]:
            if f.get("level") in ("FAIL", "P0", "WARNING", "MEDIUM"):
                print(f"         {f.get('type','').ljust(25)} {f.get('file','')}:{f.get('line','')}")

    veredicto = "❌ NO SUPERADO" if total_fail > 0 else "⚠️ CON ADVERTENCIAS" if total_warn > 0 else "✅ SUPERADO"
    print(f"\n{'='*60}")
    print(f"  Veredicto: {veredicto}")
    print(f"{'='*60}\n")
    return 1 if total_fail > 0 else 0
