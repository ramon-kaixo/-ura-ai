#!/usr/bin/env python3
"""refactor_4_motores.py — Orquestador de 4 workers de refactorización en paralelo.

Lanza 4 workers (deepseek-coder:6.7b con compactación) en paralelo,
cada uno procesando ~10 funciones >80 líneas vía round-robin.
"""

PLUGIN = {
    "name": "refactor_4_motores",
    "phase": "refactor",
    "timeout": 900,
    "blocking": False,
    "needs_file": False,
}

import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
URA_ROOT = Path(os.environ.get("URA_ROOT", "/home/ramon/URA/ura_ia_1972"))
REFACTOR_SCRIPT = SCRIPT_DIR / "refactor_large_functions_v2.py"
MODEL = "auto"  # Router selecciona el mejor modelo con temperatura optimizada
NUM_WORKERS = 4
WORKER_TIMEOUT = 600


def log(msg) -> None:
    print(f"[{time.strftime("%H:%M:%S")}] {msg}")


def worker_task(worker_id):
    env = os.environ.copy()
    env["REFACTOR_WORKER_ID"] = str(worker_id)
    env["WORKER_ID"] = str(worker_id)
    env["REFACTOR_WORKER_TOTAL"] = str(NUM_WORKERS)
    env["WORKER_TOTAL"] = str(NUM_WORKERS)
    env["REFACTOR_MODEL"] = MODEL
    env["REFACTOR_MODEL_FALLBACK"] = "auto"
    env["OLLAMA_URL"] = "http://10.164.1.99:11435"
    env["MIN_LINES"] = "80"
    env["URA_ROOT"] = str(URA_ROOT)

    cmd = [sys.executable, str(REFACTOR_SCRIPT)]
    return subprocess.run(
        cmd,
        env=env,
        capture_output=True,
        text=True,
        timeout=WORKER_TIMEOUT,
        cwd=str(URA_ROOT),
    )


def main():
    log("=" * 60)
    log("  REFACTOR 4 MOTORES — Workers paralelos")
    log("=" * 60)
    log(f"  Modelo: {MODEL}")
    log(f"  Workers: {NUM_WORKERS}")
    log(f"  Timeout por worker: {WORKER_TIMEOUT}s")
    log("")

    t0 = time.time()
    results = {"ok": 0, "fail": 0, "timeout": 0, "workers": []}

    with ThreadPoolExecutor(max_workers=NUM_WORKERS) as executor:
        futures = {
            executor.submit(worker_task, wid): wid
            for wid in range(NUM_WORKERS)
        }

        for future in as_completed(futures):
            wid = futures[future]
            try:
                result = future.result()
                if result.returncode == 0:
                    log(f"  \u2705 Worker {wid} OK")
                    results["ok"] += 1
                else:
                    log(f"  \u274c Worker {wid} fall\u00f3 (exit {result.returncode})")
                    results["fail"] += 1
                results["workers"].append({
                    "id": wid,
                    "exit_code": result.returncode,
                })
            except subprocess.TimeoutExpired:
                log(f"  \u23f0 Worker {wid} timeout ({WORKER_TIMEOUT}s)")
                results["timeout"] += 1

    elapsed = round(time.time() - t0, 1)
    log(f"\n{'=' * 60}")
    log(f"  RESUMEN — {elapsed}s")
    log(f"  OK: {results['ok']} | Fail: {results['fail']} | Timeout: {results['timeout']}")
    log(f"{'=' * 60}")

    return results


if __name__ == "__main__":
    main()
