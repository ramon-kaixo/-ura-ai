"""Refactoriza funciones grandes. Modelo: DeepSeek 6.7B."""

import contextlib
import logging
import os
import subprocess
import sys
import threading

from core.agents.constants import MODELOS, SCRIPTS, URA_ROOT

log = logging.getLogger("ura.multi_agent.ejecutor")


class AgenteEjecutor:
    """Refactoriza funciones grandes. Modelo: DeepSeek 6.7B."""

    MODELO = MODELOS["ejecutor"]

    def ejecutar(self, workers: int = 4, timeout: int = 3600) -> dict:
        resultados = {"ok": 0, "err": 0, "workers": []}
        workers_list = []

        for i in range(workers):
            env = os.environ.copy()
            env["REFACTOR_WORKER_ID"] = str(i)
            env["REFACTOR_WORKER_TOTAL"] = str(workers)
            env["REFACTOR_MODEL"] = self.MODELO
            env["REFACTOR_MODEL_FALLBACK"] = "qwen2.5-coder:14b"
            env["MIN_LINES"] = "80"
            from core.config_manager import get_ollama_url

            env["OLLAMA_URL"] = get_ollama_url()
            env["URA_ROOT"] = str(URA_ROOT)

            proc = subprocess.Popen(
                [sys.executable, "-u", str(SCRIPTS / "refactor_large_functions.py")],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=str(URA_ROOT),
            )
            workers_list.append(proc)

        for i, proc in enumerate(workers_list):
            dead_man = threading.Timer(300, lambda p=proc: p.kill())
            dead_man.daemon = True
            dead_man.start()
            try:
                out = proc.communicate(timeout=timeout)[0] or ""
                ok = out.count("✅ OK")
                err = out.count("❌ Error")
                resultados["ok"] += ok
                resultados["err"] += err
                resultados["workers"].append({"id": i + 1, "ok": ok, "err": err})
            except subprocess.TimeoutExpired:
                proc.kill()
                with contextlib.suppress(Exception):
                    proc.wait(timeout=5)
                resultados["workers"].append({"id": i + 1, "ok": 0, "err": 1, "timeout": True})
            finally:
                dead_man.cancel()
                if proc.poll() is None:
                    try:
                        proc.terminate()
                        proc.wait(timeout=5)
                    except Exception:
                        log.exception("Error terminating worker process")
                        with contextlib.suppress(Exception):
                            proc.kill()

        return resultados
