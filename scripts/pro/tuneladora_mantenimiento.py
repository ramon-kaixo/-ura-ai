#!/usr/bin/env python3
"""TUNELADORA DE MANTENIMIENTO — Flujo unificado con commit/rollback.

FLUJO CORRECTO:
  Ligero (6h):   token_screen + scanner + ruff + auto_reglas
  Medio (24h):   + poda + refactor_v2 + compactadora + scanner_salida + inspectores
  Profundo (7d): + refactor 4 workers + watermarks + backup + commit/rollback

FUSIONADO CON:
  - ciclo_autonomo_gx10.py (commit/rollback basado en F821)
  - analizar_fallo_conciencia.py (diagnóstico de conciencia)
  - master_conciencia.py (testing de acciones)
  - pareto_router.py (gestión de datos)
  - ura_self_modify.py (auto-mejora del prompt)
"""

import json
import os
import socket
import subprocess
import sys
from datetime import datetime
from pathlib import Path

URA_ROOT = Path(os.environ.get("URA_ROOT", "/home/ramon/URA/ura_ia_1972"))
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://10.164.1.99:11434")
MODEL_ROUTER = "http://10.164.1.99:11435"
RUFF = str(URA_ROOT / ".venv/bin/ruff")
VENV_PYTHON = str(URA_ROOT / ".venv/bin/python3")
LOG_DIR = Path("/opt/ura/logs/tuneladora_mantenimiento")
REPORT_DIR = Path(str(URA_ROOT) + "/docs/pro/reports")
NERVIOSO = Path(str(URA_ROOT) + "/.nervioso")

MAGICDNS_GX10 = "gx10-64c3-1.tail7b3cf3.ts.net"
MAGICDNS_MAC = "mac-mini-de-ramon.tail7b3cf3.ts.net"


def _resolve_host(hostname: str, default: str = "") -> str:
    try:
        return socket.gethostbyname(hostname)
    except OSError:
        return default


def _load_devices(root: Path) -> dict[str, str]:
    defaults = {
        "gx10_principal": "10.164.1.99",
        "gx10_wifi": "10.164.1.247",
        "gx10_tailscale": _resolve_host(MAGICDNS_GX10, "100.72.103.12"),
        "mac_ethernet": "10.164.1.26",
        "mac_tailscale": _resolve_host(MAGICDNS_MAC, "100.123.81.101"),
    }
    try:
        with open(root / "config" / "dispositivos.json") as f:
            cfg = json.load(f)
        d = cfg.get("dispositivos", {})
        gx10 = d.get("gx10-64c3", {})
        mac = d.get("mac-mini-de-ramon", {})
        result = {
            "gx10_principal": gx10.get("ip_cable", defaults["gx10_principal"]),
            "gx10_wifi": gx10.get("ip_wifi", defaults["gx10_wifi"]),
            "gx10_tailscale": gx10.get("ip_tailscale", defaults["gx10_tailscale"]),
            "mac_ethernet": mac.get("ip_cable", defaults["mac_ethernet"]),
            "mac_tailscale": mac.get("ip_tailscale", defaults["mac_tailscale"]),
        }
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        result = dict(defaults)
    dynamic = _resolve_host(MAGICDNS_GX10)
    if dynamic:
        result["gx10_tailscale"] = dynamic
    return result

DISPOSITIVOS = _load_devices(URA_ROOT)


def log(msg) -> None:
    pass


def run(cmd, timeout=120):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=str(URA_ROOT))
        return r.returncode, r.stdout, r.stderr
    except Exception as e:
        return -1, "", str(e)


def detectar_nivel() -> str:
    now = datetime.now()
    hora, dia = now.hour, now.weekday()
    if dia == 0 and 2 <= hora <= 4:
        return "profundo"
    if hora in (0, 6, 12, 18):
        return "medio" if hora == 3 else "ligero"
    return "ligero"


def health_check():
    metrics = {}
    rc, out, _ = run(["free", "-m"])
    if rc == 0:
        for line in out.splitlines():
            if "Mem:" in line:
                parts = line.split()
                if len(parts) > 2:
                    metrics["ram_usada_mb"] = int(parts[2])
    rc, out, _ = run(["ps", "aux"])
    metrics["zombies"] = out.count(" Z ") if out else 0
    try:
        usage = os.statvfs("/")
        metrics["disco_libre_gb"] = round((usage.f_frsize * usage.f_bavail) / 1e9, 1)
    except Exception:
        pass
    alertas = []
    if metrics.get("ram_usada_mb", 0) > 90000:
        alertas.append("RAM >90GB")
    if metrics.get("zombies", 0) > 5:
        alertas.append(f"Zombies: {metrics['zombies']}")
    return metrics, alertas


def check_ollama():
    try:
        rc, out, _ = run(["curl", "-s", "--max-time", "3", f"{OLLAMA_URL}/api/tags"])
        if rc == 0 and "models" in out:
            return json.loads(out).get("models", [])
    except Exception:
        pass
    return []


def check_model_router():
    try:
        rc, out, _ = run(["curl", "-s", "--max-time", "3", f"{MODEL_ROUTER}/health"])
        return rc == 0 and "ok" in out
    except Exception:
        return False


def check_dispositivos():
    resultados = {}
    for nombre, ip in DISPOSITIVOS.items():
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            resultados[nombre] = sock.connect_ex((ip, 22)) == 0
            sock.close()
        except Exception:
            resultados[nombre] = False
    return resultados


# -- Steps comunes --


def step_token_screen():
    log("  Token screen (RAM check)...")
    rc, _, _ = run(
        [VENV_PYTHON, "scripts/pro/token_screen.py", "--texto", "test", "--json"], timeout=15,
    )
    return rc == 0


def step_scanner_entrada() -> None:
    log("  Scanner entrada (snapshot)...")
    run([VENV_PYTHON, "scripts/pro/scanner_autoajuste.py", "--json"], timeout=30)


def step_scanner_salida() -> None:
    log("  Scanner salida (diff)...")
    run([VENV_PYTHON, "scripts/pro/scanner_autoajuste.py", "--diff", "--json"], timeout=30)


def step_orphan_scanner() -> int:
    log("  Orphan systemd units...")
    _rc, out, _ = run([VENV_PYTHON, "scripts/pro/systemd_orphan_scanner.py", "--json"], timeout=30)
    try:
        data = json.loads(out)
        return data.get("total", 0)
    except (json.JSONDecodeError, TypeError):
        return -1


def step_poda() -> None:
    log("  Poda mecanica...")
    run([VENV_PYTHON, "scripts/pro/poda_mecanica.py", "--json"], timeout=30)


def step_refactor(workers=1, model="deepseek-coder:6.7b", fallback="qwen2.5-coder:14b"):
    log(f"  Refactor ({workers} workers, {model})...")
    env = os.environ.copy()
    env["REFACTOR_WORKER_TOTAL"] = str(workers)
    env["REFACTOR_MODEL"] = model
    env["REFACTOR_MODEL_FALLBACK"] = fallback
    env["MIN_LINES"] = "80"
    env["OLLAMA_URL"] = OLLAMA_URL
    env["URA_ROOT"] = str(URA_ROOT)

    procs = []
    for i in range(workers):
        env["REFACTOR_WORKER_ID"] = str(i)
        proc = subprocess.Popen(
            [VENV_PYTHON, "-u", "scripts/pro/refactor_large_functions_v2.py"],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=str(URA_ROOT),
        )
        procs.append(proc)

    total_ok = total_err = 0
    for i, proc in enumerate(procs):
        try:
            out = proc.communicate(timeout=3600)[0] or ""
            ok = out.count("Refactorizado")
            err = out.count("Error")
            total_ok += ok
            total_err += err
            log(f"    W{i + 1}: {ok} OK, {err} ERROR")
        except subprocess.TimeoutExpired:
            proc.kill()
            log(f"    W{i + 1}: TIMEOUT")
    return total_ok, total_err


def step_compactadora() -> None:
    log("  Compactadora + auto-reglas...")
    run([VENV_PYTHON, "scripts/pro/compactadora.py", "--estado"], timeout=15)
    run([VENV_PYTHON, "scripts/pro/auto_reglas.py", "--generar"], timeout=30)


def step_inspectores():
    log("  Inspectores (validacion)...")
    rc, _, _ = run([VENV_PYTHON, "scripts/pro/inspectores.py", "--json"], timeout=60)
    return rc == 0


# -- Steps de ciclo_autonomo (fusionados) --


def snapshot_f821(label="pre-mantenimiento") -> None:
    log("  Snapshot F821...")
    run([VENV_PYTHON, "scripts/pro/f821_watch.py", "snapshot", "--label", label], timeout=30)


def audit_delta(target="pre-mantenimiento"):
    log("  Auditoria F821 delta...")
    rc, out, _ = run([VENV_PYTHON, "scripts/pro/f821_watch.py", "compare", "--target", target], timeout=30)
    return rc == 0, out


def git_commit_if_stable() -> None:
    log("  Git commit (si F821 estable)...")
    run(["git", "add", "-u"], timeout=30)
    run(["git", "commit", "-m", f"mantenimiento: {datetime.now().strftime('%Y-%m-%d %H:%M')} — F821 estable"], timeout=30)


def git_rollback() -> None:
    log("  Git rollback (F821 regreso)...")
    run(["git", "checkout", "."], timeout=30)


# -- Steps de analizar_fallo_conciencia (fusionados) --


def step_diagnostico_conciencia():
    log("  Diagnostico de conciencia...")
    rc, _out, _ = run([VENV_PYTHON, "scripts/pro/analizar_fallo_conciencia.py"], timeout=60)
    return rc == 0


# -- Steps de master_conciencia (fusionados) --


def step_testing_acciones():
    log("  Testing de acciones URA...")
    rc, _out, _ = run([VENV_PYTHON, "scripts/pro/master_conciencia.py"], timeout=120)
    return rc == 0


# -- Steps de pareto_router (fusionados) --


def step_gestion_datos():
    log("  Gestion de datos (Pareto 20/80)...")
    rc, _, _ = run([VENV_PYTHON, "scripts/pro/pareto_router.py", "--clasificar"], timeout=60)
    return rc == 0


# -- Steps de ura_self_modify (fusionados) --


def step_auto_mejora_prompt():
    log("  Auto-mejora del prompt URA...")
    rc, _, _ = run([VENV_PYTHON, "scripts/pro/ura_self_modify.py"], timeout=60)
    return rc == 0


# -- Niveles --


def revision_ligera():
    log("REVISION LIGERA (6h)")
    token_ok = step_token_screen()
    step_scanner_entrada()
    run([RUFF, "check", "--fix", "--select", "F841,F401", "."], timeout=120)
    run([RUFF, "format", "."], timeout=60)
    _rc, out, _ = run([RUFF, "check", "--select", "F821", "."], timeout=60)
    f821 = out.count("F821")
    step_compactadora()
    step_scanner_salida()
    return {"ruff_f821": f821, "token_screen": token_ok}


def revision_media():
    log("REVISION MEDIA (24h)")
    health, alertas = health_check()
    if alertas:
        log(f"  ALERTAS: {alertas}")
    token_ok = step_token_screen()
    step_scanner_entrada()
    orphan_count = step_orphan_scanner()
    run([RUFF, "check", "--fix", "."], timeout=120)
    run([RUFF, "format", "."], timeout=60)
    step_poda()
    ok, err = step_refactor(workers=1)
    step_compactadora()
    step_scanner_salida()
    inspectores_ok = step_inspectores()
    _rc, out, _ = run([RUFF, "check", "--select", "F821", "."], timeout=60)
    return {
        "health": health,
        "token_screen": token_ok,
        "orphan_units": orphan_count,
        "refactor_ok": ok,
        "refactor_err": err,
        "inspectores_ok": inspectores_ok,
        "f821_final": out.count("F821"),
    }


def revision_profunda():
    log("REVISION PROFUNDA (SEMANAL)")
    results = {}
    health, alertas = health_check()
    models = check_ollama()
    router_ok = check_model_router()
    dispositivos = check_dispositivos()
    log(f"  RAM: {health.get('ram_usada_mb', '?')}MB, Router: {'OK' if router_ok else 'DOWN'}")

    # Preflight + Snapshot (de ciclo_autonomo)
    snapshot_f821("pre-profundo")

    token_ok = step_token_screen()
    results["token_screen"] = token_ok
    step_scanner_entrada()
    results["orphan_units"] = step_orphan_scanner()
    run([RUFF, "check", "--fix", "--unsafe-fixes", "."], timeout=300)
    run([RUFF, "format", "."], timeout=120)
    step_poda()
    ok, err = step_refactor(workers=4)
    results["refactor_ok"] = ok
    results["refactor_err"] = err
    step_compactadora()
    step_scanner_salida()
    inspectores_ok = step_inspectores()
    results["inspectores_ok"] = inspectores_ok
    run([VENV_PYTHON, "scripts/pro/watermark_aggregator.py", "--auto-reglas"], timeout=30)

    # Auditoria delta (de ciclo_autonomo)
    f821_ok, _delta_out = audit_delta("pre-profundo")
    _rc, out, _ = run([RUFF, "check", "--select", "F821", "."], timeout=60)
    results["f821_final"] = out.count("F821")

    # Commit o Rollback (de ciclo_autonomo)
    if f821_ok:
        git_commit_if_stable()
        results["git"] = "committed"
    else:
        git_rollback()
        results["git"] = "rollback"

    # Nuevos steps fusionados
    step_diagnostico_conciencia()
    step_testing_acciones()
    step_gestion_datos()
    step_auto_mejora_prompt()

    # Reporte
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    reporte = {
        "tuneladora": "mantenimiento_profundo",
        "fecha": datetime.now().isoformat(),
        "health": health,
        "alertas": alertas,
        "dispositivos": {k: "OK" if v else "DOWN" for k, v in dispositivos.items()},
        "models_disponibles": len(models),
        "refactor_ok": ok,
        "refactor_err": err,
        "f821_final": results["f821_final"],
        "git": results["git"],
    }
    reporte_path = REPORT_DIR / f"reporte_semanal_{datetime.now().strftime('%Y%m%d')}.json"
    reporte_path.write_text(json.dumps(reporte, indent=2, ensure_ascii=False))
    results["reporte"] = str(reporte_path)
    return results


def main() -> int:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    NERVIOSO.mkdir(parents=True, exist_ok=True)
    nivel = detectar_nivel()
    log("=" * 55)
    log(f"  TUNELADORA MANTENIMIENTO — Nivel: {nivel.upper()}")
    log("=" * 55)
    _health, alertas = health_check()
    if alertas:
        log(f"  ALERTAS: {alertas}")
    if nivel == "profundo":
        resultado = revision_profunda()
    elif nivel == "medio":
        resultado = revision_media()
    else:
        resultado = revision_ligera()
    estado = {
        "ultima_ejecucion": datetime.now().isoformat(),
        "nivel": nivel,
        "resultado": resultado,
    }
    (NERVIOSO / "estado_mantenimiento.json").write_text(
        json.dumps(estado, indent=2, ensure_ascii=False),
    )
    log("Mantenimiento completado")
    return 0


if __name__ == "__main__":
    sys.exit(main())
