#!/usr/bin/env python3
"""Lanzador simplificado: procesa archivos en lotes de N, sin bloqueos.

Cada lote = 1 archivo por instancia de Ollama. Salida en tiempo real.
Sin ProcessPoolExecutor (que bufferiza). Sin subprocess.run (bloqueante con capture).

Uso:
  python scripts/pro/batch_launcher.py
  BATCH_SIZE=4 TARGETS_FILE=/tmp/targets.txt python scripts/pro/batch_launcher.py
"""

import os
import subprocess
import sys
import time
from pathlib import Path

URA_ROOT = Path(os.environ.get("URA_ROOT", os.path.expanduser("~/URA/ura_ia_1972")))
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "10.164.1.99")
PORTS = [int(p) for p in os.environ.get("OLLAMA_PORTS", "11434,11436,11437,11438").split(",")]
BATCH_SIZE = int(os.environ.get("BATCH_SIZE", str(len(PORTS))))

TARGETS_FILE = os.environ.get("TARGETS_FILE", "")
if TARGETS_FILE:
    TARGETS = [line.strip() for line in Path(TARGETS_FILE).read_text().splitlines() if line.strip()]
else:
    TARGETS = [
        "core/central_router.py",
        "core/ura_panel.py",
        "ura_panel.py",
        "core/agente_administrativo_contable.py",
        "core/agente_cocina_navarra_temporada.py",
        "core/agente_gastronomo_musica.py",
        "benchmarks/STRESS_TEST_125.py",
    ]


def process_one(file_rel: str, port: int) -> bool:
    file_path = URA_ROOT / file_rel
    if not file_path.exists():
        print(f"  ⚠️  {file_rel} — no existe")
        return False

    url = f"http://{OLLAMA_HOST}:{port}"
    cmd = [
        sys.executable,
        str(URA_ROOT / "scripts/pro/refactor_large_functions.py"),
        str(file_path),
    ]
    env = os.environ.copy()
    env["OLLAMA_URL"] = url
    env.setdefault("ENGLISH_THINK", "1")
    env.setdefault("CHUNK_LINES", "60")
    env["REFACTOR_MODE"] = "chunk"
    env["PYTHONUNBUFFERED"] = "1"

    t0 = time.time()
    # Use Popen for live output, no buffer
    proc = subprocess.Popen(
        cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
    )
    out, _ = proc.communicate(timeout=1800)
    elapsed = time.time() - t0

    ok = proc.returncode == 0
    tail = (out or "")[-300:]
    icon = "✅" if ok else "❌"
    print(f"  {icon} {file_rel} — {elapsed:.0f}s | puerto {port}")
    if tail.strip():
        print(f"     {tail.strip()[:200]}")
    return ok


def main():
    print(f"🚀 BATCH LAUNCHER — {len(TARGETS)} archivos, batch={BATCH_SIZE}, puertos={PORTS}")
    start = time.time()
    ok_count = 0
    fail_count = 0
    total = len(TARGETS)

    for i in range(0, total, BATCH_SIZE):
        batch = TARGETS[i : i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        total_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE
        print(
            f"\n📦 Lote {batch_num}/{total_batches} ({len(batch)} archivos) — {i}/{total} completados"
        )

        procs = []
        for j, file_rel in enumerate(batch):
            port = PORTS[j % len(PORTS)]
            print(f"  🚀 [{port}] {file_rel}")
            proc = subprocess.Popen(
                [
                    sys.executable,
                    str(URA_ROOT / "scripts/pro/refactor_large_functions.py"),
                    str(URA_ROOT / file_rel),
                ],
                env={
                    **os.environ,
                    "OLLAMA_URL": f"http://{OLLAMA_HOST}:{port}",
                    "REFACTOR_MODEL": "qwen2.5-coder:14b",
                    "ENGLISH_ONLY": "1",
                    "CHUNK_LINES": "60",
                    "REFACTOR_MODE": "chunk",
                    "PYTHONUNBUFFERED": "1",
                },
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            procs.append((proc, file_rel, port))

        for proc, file_rel, port in procs:
            t0 = time.time()
            try:
                out, _ = proc.communicate(timeout=3600)
                elapsed = time.time() - t0
                ok = proc.returncode == 0
                if ok:
                    ok_count += 1
                    print(f"  ✅ {file_rel} — {elapsed:.0f}s")
                else:
                    fail_count += 1
                    print(f"  ❌ {file_rel} — {elapsed:.0f}s (rc={proc.returncode})")
                    tail = (out or "")[-200:]
                    if tail.strip():
                        print(f"     {tail.strip()[:200]}")
            except subprocess.TimeoutExpired:
                proc.kill()
                fail_count += 1
                print(f"  ⏰ {file_rel} — TIMEOUT (30min)")
            except Exception as e:
                fail_count += 1
                print(f"  💥 {file_rel} — {e}")

    elapsed = time.time() - start
    print(f"\n{'=' * 60}")
    print(f"🏁 {ok_count}/{total} OK, {fail_count} fallos — {elapsed:.0f}s ({elapsed / 3600:.1f}h)")


if __name__ == "__main__":
    main()
