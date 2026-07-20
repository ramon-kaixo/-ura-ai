"""WorkerManager — gestiona workers paralelos de refactorización.

Reemplaza launch_refactor_gx10.sh con una implementación Python.
Mantiene el handshake con sistema nervioso y el watchdog.
"""

from __future__ import annotations

import os
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from scripts.pro.tuneladora.config import Configuration
from scripts.pro.tuneladora.logger import Logger
from scripts.pro.refactor_worker import RefactorWorker


class WorkerManager:
    """Gestiona N workers de refactorización en paralelo."""

    def __init__(
        self,
        config: Configuration | None = None,
        log: Logger | None = None,
    ) -> None:
        self.config = config or Configuration()
        self.log = log or Logger(self.config.log_file)

    def handshake(self) -> dict[str, Any]:
        """Handshake con el sistema nervioso. Retorna métricas."""
        result: dict[str, Any] = {"activos": 0, "duplicados": 0}
        smap = self.config.sistema_map
        if not smap.exists():
            self.log.warn("Sin sistema_map.json — handshake omitido")
            return result
        try:
            import json  # noqa: PLC0415

            data = json.loads(smap.read_text(encoding="utf-8"))
            deps = data.get("dependency_graph", {})
            for n in deps.values():
                state = n.get("pipeline_state", "")
                if "ESPEJO" in state:
                    result["duplicados"] += 1
                elif "ZOMBIE" not in state:
                    result["activos"] += 1
        except Exception as e:  # noqa: BLE001
            self.log.warn(f"Handshake falló: {e}")
        self.log.info(f"Handshake: {result['activos']} activos, {result['duplicados']} duplicados")
        return result

    def run_workers(
        self,
        count: int = 4,
        model: str = "qwen2.5-coder:14b",
        timeout: int = 3600,
    ) -> list[dict[str, Any]]:
        """Lanza count workers en paralelo. Retorna resultados de cada uno."""
        self.log.info(f"Lanzando {count} workers (modelo={model}, timeout={timeout}s)")
        results: list[dict[str, Any]] = []
        t0 = time.time()

        with ThreadPoolExecutor(max_workers=count) as executor:
            futures = {}
            for i in range(count):
                worker = RefactorWorker(
                    worker_id=i + 1,
                    total_workers=count,
                    model=model,
                    ura_root=str(self.config.ura_root),
                    venv_python=self.config.venv_python,
                )
                futures[executor.submit(worker.run, timeout=timeout)] = i + 1

            for future in as_completed(futures):
                wid = futures[future]
                try:
                    result = future.result()
                    results.append(
                        {
                            "worker_id": wid,
                            "returncode": result.returncode,
                            "stdout": result.stdout[-300:] if result.stdout else "",
                            "stderr": result.stderr[-200:] if result.stderr else "",
                            "ok": result.returncode == 0,
                        }
                    )
                except TimeoutError:
                    self.log.error(f"Worker {wid} TIMEOUT ({timeout}s)")
                    results.append({"worker_id": wid, "returncode": -1, "error": "timeout", "ok": False})
                except Exception as e:  # noqa: BLE001
                    self.log.error(f"Worker {wid} error: {e}")
                    results.append({"worker_id": wid, "returncode": -1, "error": str(e), "ok": False})

        elapsed = time.time() - t0
        ok = sum(1 for r in results if r["ok"])
        err = sum(1 for r in results if not r["ok"])
        self.log.info(f"Workers completados: {ok} OK, {err} ERROR en {elapsed:.1f}s")
        return results

    def clean_temp_files(self) -> None:
        """Limpia archivos temporales de ejecuciones anteriores."""
        for p in Path("/tmp").glob("refactor_gx10_*"):
            p.unlink(missing_ok=True)
        for p in Path("/tmp").glob("refactor_watchdog*"):
            p.unlink(missing_ok=True)
        self.log.info("Temporales limpiados")
