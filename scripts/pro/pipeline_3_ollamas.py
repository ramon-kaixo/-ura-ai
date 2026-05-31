#!/usr/bin/env python3
"""Pipeline multi-Ollama: distribuye archivos entre N instancias de Ollama.

Cada instancia de Ollama procesa sus archivos asignados en paralelo.
El reparto es cíclico para balancear carga.

Requiere: 2-3 instancias de ollama serve en puertos diferentes del GX10.
  Puerto 11434: ollama serve (original)
  Puerto 11435: OLLAMA_HOST=127.0.0.1:11435 OLLAMA_MODELS=/tmp/ollama_models2 ollama serve
  Puerto 11436: OLLAMA_HOST=127.0.0.1:11436 OLLAMA_MODELS=/tmp/ollama_models3 ollama serve

Uso:
  python scripts/pro/pipeline_3_ollamas.py
  OLLAMA_PORTS=11434,11435 python scripts/pro/pipeline_3_ollamas.py  # 2 puertos
"""

import os
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

URA_ROOT = Path(os.environ.get("URA_ROOT", os.path.expanduser("~/URA/ura_ia_1972")))
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "10.164.1.99")
PORTS = [int(p) for p in os.environ.get("OLLAMA_PORTS", "11434").split(",")]

# Archivos de los 10 que reportaron funciones >100 líneas
TARGETS_FILE = os.environ.get("TARGETS_FILE", "")

if TARGETS_FILE and Path(TARGETS_FILE).exists():
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
        "core/openclaw_connector.py",
        "scripts/pro/sandbox_industrial.py",
        "agents/ura_api.py",
    ]


def process_file(pair: tuple) -> tuple[str, bool, str]:
    idx, file_rel = pair
    port = PORTS[idx % len(PORTS)]
    url = f"http://{OLLAMA_HOST}:{port}"
    file_path = URA_ROOT / file_rel

    if not file_path.exists():
        return (file_rel, False, f"no existe: {file_path}")

    env = os.environ.copy()
    env["OLLAMA_URL"] = url
    env.setdefault("ENGLISH_THINK", "1")
    env.setdefault("CHUNK_LINES", "60")
    env["REFACTOR_MODE"] = "chunk"
    env["PYTHONUNBUFFERED"] = "1"

    cmd = [
        sys.executable,
        str(URA_ROOT / "scripts/pro/refactor_large_functions.py"),
        str(file_path),
    ]

    t0 = time.time()
    proc = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=3600)
    elapsed = time.time() - t0
    ok = proc.returncode == 0
    tail = (
        (proc.stdout + "\n" + proc.stderr)[-600:] if proc.stdout or proc.stderr else "(sin output)"
    )
    return (file_rel, ok, f"{elapsed:.0f}s | puerto {port}\n{tail}")


def main() -> None:
    print("═" * 70)
    print(f"🏭 PIPELINE MULTI-OLLAMA — {len(PORTS)} instancias, {len(TARGETS)} archivos")
    print("═" * 70)
    print(f"📍 Puertos: {PORTS}")
    print("📦 Archivos:")
    for i, t in enumerate(TARGETS):
        port = PORTS[i % len(PORTS)]
        print(f"   [{port}] {t}")

    start = time.time()
    results: list[tuple[str, bool, str]] = []
    pairs = list(enumerate(TARGETS))

    with ProcessPoolExecutor(max_workers=min(10, len(TARGETS))) as executor:
        futures = {executor.submit(process_file, p): p for p in pairs}
        for future in as_completed(futures):
            p = futures[future]
            try:
                rel, ok, detail = future.result()
                results.append((rel, ok, detail))
                icon = "✅" if ok else "❌"
                print(f"\n{icon} {rel} — {'OK' if ok else 'FAIL'}\n{detail[:300]}")
            except Exception as e:
                rel = p[1]
                results.append((rel, False, str(e)))
                print(f"\n❌ {rel} — EXCEPCIÓN: {e}")

    elapsed = time.time() - start
    ok_count = sum(1 for _, ok, _ in results if ok)
    fail_count = len(results) - ok_count

    print(f"\n{'=' * 70}")
    print(f"🏁 {ok_count}/{len(results)} archivos OK en {elapsed:.0f}s ({fail_count} fallos)")
    for rel, ok, detail in results:
        print(f"  {'✅' if ok else '❌'} {rel}")


if __name__ == "__main__":
    main()
