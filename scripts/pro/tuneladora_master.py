#!/usr/bin/env python3
"""tuneladora_master.py — Orquestador de Excavacion Autonoma (AEA).

Modos:
  --use-delta-check    : Modo Delta diario (solo archivos modificados, ~100% ahorro)
  --force-all          : Modo Profundo mensual (auditoria total, reset integridad)
  --intensive-audit    : Auditoria intensiva (ruff + bandit + radon + F821 completo)

Log: /var/log/ura_tunel.log

Reglas de Oro:
  1. El Guardian es la unica fuente de verdad para limpieza
  2. Cero Ciga (analisis de redundancia innecesario)
  3. Reporte de auditoria obligatorio tras cada ciclo
"""

import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

URA_ROOT = Path(os.environ.get("URA_ROOT", os.path.expanduser("~/URA/ura_ia_1972")))
LOG_FILE = Path(os.environ.get("TUNEL_LOG", str(URA_ROOT / "logs" / "ura_tunel.log")))
NERVIOSO = URA_ROOT / ".nervioso"

os.chdir(str(URA_ROOT))


def log(msg: str) -> None:
    """Escribe al log de la tuneladora."""
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    try:
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except PermissionError:
        pass


def modo_delta() -> int:
    """Modo Delta diario: solo procesar archivos modificados."""
    log("Δ MODO DELTA — Delta-Check activo")
    log("⏱️  Inicio: " + datetime.now(UTC).isoformat()[:19])

    # Handshake con Guardian
    index_path = NERVIOSO / "sistema_map.json"
    if not index_path.exists():
        log("📋 Indexando sistema nervioso...")
        subprocess.run(
            [sys.executable, "scripts/openclaw_indexer.py", "scan"],
            capture_output=True,
            timeout=120,
        )

    delta_snap = NERVIOSO / "delta_snapshots" / "ultimo_ciclo.json"
    ahorro = 0
    if delta_snap.exists():
        idx = json.loads(index_path.read_text(encoding="utf-8"))
        deps = idx.get("dependency_graph", {})
        snap = json.loads(delta_snap.read_text(encoding="utf-8")).get("files", {})

        total = sum(
            1
            for n in deps.values()
            if "ESPEJO" not in n.get("pipeline_state", "")
            and "ZOMBIE" not in n.get("pipeline_state", "")
        )
        cambiados = sum(
            1
            for rel, node in deps.items()
            if rel in snap and snap[rel].get("blake2b") != node.get("checksum_blake2b_8")
        )
        nuevos = sum(1 for rel in deps if rel not in snap)
        sin_cambio = total - cambiados - nuevos

        ahorro = round(sin_cambio / max(total, 1) * 100, 1)
        log(
            f"Δ Delta: {total} activos, {cambiados} modificados, {nuevos} nuevos, {sin_cambio} sin cambios ({ahorro}% ahorro)",
        )
    else:
        log("Δ Primer ciclo — sin snapshot previo, procesando todo")

    log("🚀 Lanzando 4 workers...")
    t0 = time.time()

    result = subprocess.run(
        ["bash", "scripts/pro/launch_refactor_gx10.sh"],
        capture_output=True,
        text=True,
        timeout=86400,
    )

    elapsed = time.time() - t0
    log(result.stdout[-500:] if len(result.stdout) > 500 else result.stdout)
    log(result.stderr[-200:] if len(result.stderr) > 200 else result.stderr)

    # Guardar delta snapshot
    from openclaw_firmador import delta_snapshot

    delta_snapshot("ultimo_ciclo")

    # Reporte final
    H = int(elapsed // 3600)
    M = int((elapsed % 3600) // 60)
    S = int(elapsed % 60)

    reporte = (
        f"══════════════════════════════════════\n"
        f"  📊 INFORME DE EXCAVACION — Modo Delta\n"
        f"══════════════════════════════════════\n"
        f"  ⏱️  Duracion: {H}h {M}m {S}s\n"
        f"  Δ  Ahorro:   {ahorro}% archivos no modificados\n"
        f"  🧠 Ciga-Free: Guardian excluyo duplicados/zombies\n"
        f"  💾 Delta snapshot: guardado para proximo ciclo\n"
        f"  🌱 Proximo ciclo: en 24h (modo Delta)\n"
        f"══════════════════════════════════════\n"
        f"  Fin: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    log(reporte)

    return result.returncode


import os
from pathlib import Path


def helper1() -> None:
    """Helper function to clean delta snapshots."""
    delta_dir = Path("NERVIOSO") / "delta_snapshots"
    if delta_dir.exists():
        subprocess.run(["rm", "-rf", str(delta_dir)], check=False)


def helper2() -> None:
    """Helper function to rebuild the nervous system from scratch."""
    subprocess.run(
        [sys.executable, "scripts/openclaw_indexer.py", "scan"], capture_output=True, timeout=120,
    )


def helper3(label: str) -> None:
    """Helper function to create a snapshot of F821 errors."""
    subprocess.run(
        [sys.executable, "scripts/pro/f821_watch.py", "snapshot", "--label", label],
        capture_output=True,
        timeout=60,
    )


def helper4(target: str) -> str:
    """Helper function to compare the F821 errors with a target."""
    cmp = subprocess.run(
        [sys.executable, "scripts/pro/f821_watch.py", "compare", "--target", target],
        capture_output=True,
        text=True,
        timeout=60,
    )
    return "OK" if cmp.returncode == 0 else "REG RESION"


def helper5() -> None:
    """Helper function to create a delta snapshot for the next cycle."""
    from openclaw_firmador import delta_snapshot

    delta_snapshot("ultimo_ciclo")


def modo_profundo() -> int:
    """Modo Profundo mensual: audit, reset integrity."""
    log("⚠️  MODO PROFUNDO — Audit monthly")
    log("⏱️  Start: " + datetime.now(UTC).isoformat()[:19])

    helper1()
    log("🧹 Delta snapshots cleaned")

    helper2()
    log("🔧 Rebuilding nervous system from scratch...")

    ruff = subprocess.run(
        ["ruff", "check", "--select", "F821,F841,E402", "--output-format", "concise", "."],
        capture_output=True,
        text=True,
        timeout=300,
    )
    f821_count = ruff.stdout.count("F821")
    f841_count = ruff.stdout.count("F841")
    log(f"  ruff: {f821_count} F821, {f841_count} F841")

    helper3(f"profundo-{datetime.now().strftime('%Y%m')}")

    log("🚀 Starting full refactoring (--force-all)...")
    t0 = time.time()

    result = subprocess.run(
        ["bash", "scripts/pro/launch_refactor_gx10.sh"],
        capture_output=True,
        text=True,
        timeout=86400,
    )

    elapsed = time.time() - t0
    H = int(elapsed // 3600)
    M = int((elapsed % 3600) // 60)
    S = int(elapsed % 60)

    f821_result = helper4(f"profundo-{datetime.now().strftime('%Y%m')}")

    helper5()

    reporte = (
        f"══════════════════════════════════════\n"
        f" 📊 EXCAVATION REPORT — Mode Profundo\n"
        f"══════════════════════════════════════\n"
        f" ⏱️ Duration: {H}h {M}m {S}s\n"
        f" 🔍 F821: {f821_count} → {f821_result}\n"
        f" 🧹 Delta snapshots: cleaned\n"
        f" 💾 Nervous system: rebuilt\n"
        f" 🌱 Next cycle: mode Delta daily\n"
        f"══════════════════════════════════════\n"
        f" End: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    log(reporte)

    return result.returncode


def main() -> None:
    DIA = datetime.now().day

    if "--force-all" in sys.argv or DIA == 1:
        sys.exit(modo_profundo())
    else:
        sys.exit(modo_delta())


if __name__ == "__main__":
    main()
