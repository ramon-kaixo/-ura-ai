"""Auditor — Detecta tareas pendientes de revision, ejecuta gates, hace merge.

Flujo:
  1. Consulta tareas en estado 'review'
  2. Para cada tarea, checkout del commit en worktree aislado
  3. Ejecuta gates: ruff + mypy + pytest
  4. Si PASS -> merge a main + PATCH complete
  5. Si FAIL -> PATCH fail con error truncado (50 lineas max)
"""

from __future__ import annotations

import json
import logging
import subprocess
import urllib.request
from pathlib import Path

log = logging.getLogger(__name__)

_TASK_QUEUE_URL = "http://localhost:4097"
_REPO_ROOT = Path(__file__).parent.parent.parent
_MAX_ERROR_LINES = 50


class Auditor:
    """Detecta y audita tareas pendientes de revision."""

    def __init__(
        self,
        task_queue_url: str = _TASK_QUEUE_URL,
        repo_root: Path = _REPO_ROOT,
    ) -> None:
        self._queue_url = task_queue_url
        self._repo = repo_root

    def _api(self, method: str, path: str, data: dict[str, object] | None = None) -> dict[str, object]:
        """Llamada a la API de la cola."""
        url = f"{self._queue_url}{path}"
        body = json.dumps(data).encode() if data else None
        req = urllib.request.Request(url, data=body, method=method)  # noqa: S310
        req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310
                return json.loads(resp.read())
        except Exception as e:
            log.error("[AUDITOR] API error %s %s: %s", method, path, e)
            raise

    def _get_review_tasks(self) -> list[dict[str, object]]:
        """Obtiene tareas en estado review."""
        result = self._api("GET", "/tasks?status=review")
        return result.get("tasks", [])  # type: ignore[return-value]

    def _run_gate(self, name: str, cmd: list[str], cwd: Path) -> tuple[bool, str]:
        """Ejecuta un gate de validacion."""
        try:
            # Use a specific timeout since the original code had 120s but this may be too strict for CI
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
                cwd=str(cwd),
                check=False,
            )
            output = result.stdout + "\n" + result.stderr
            if result.returncode != 0:
                lines = output.strip().split("\n")
                truncated = "\n".join(lines[-_MAX_ERROR_LINES:])
                return False, truncated
            return True, "OK"
        except subprocess.TimeoutExpired:
            return False, f"TIMEOUT after 120s: {' '.join(cmd)}"
        except Exception as e:
            return False, f"ERROR: {e}"

    def _git(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        """Ejecuta un comando git con check=False."""
        return subprocess.run(
            ["git", *args],
            cwd=str(self._repo),
            capture_output=True,
            text=True,
            check=False,
        )

    def audit_task(self, task: dict) -> dict:
        """Audita una tarea individual."""
        task_id = task["id"]
        commit_sha = task.get("commit_sha", "")

        if not commit_sha:
            return {"task_id": task_id, "passed": False, "error": "No commit SHA"}

        log.info("[AUDITOR] Auditando %s (commit: %s)", task_id, commit_sha[:8])

        wt_path = Path(f"/tmp/audit-{task_id}")
        try:
            if wt_path.exists():
                self._git(["worktree", "remove", "--force", str(wt_path)])

            result = self._git(["worktree", "add", "-f", str(wt_path), commit_sha])
            if result.returncode != 0:
                return {"task_id": task_id, "passed": False, "error": f"Worktree failed: {result.stderr}"}

            gates = [
                ("ruff", ["python3", "-m", "ruff", "check", ".", "--statistics"]),
                ("mypy", ["python3", "-m", "mypy", "--no-incremental", "core", "motor", "shared"]),
                ("pytest", ["python3", "-m", "pytest", "tests/", "-x", "-q", "--tb=line", "--timeout=30"]),
            ]

            for gate_name, cmd in gates:
                passed, output = self._run_gate(gate_name, cmd, wt_path)
                if not passed:
                    log.warning("[AUDITOR] %s fallo en %s", task_id, gate_name)
                    return {"task_id": task_id, "passed": False, "error": f"{gate_name}:\n{output}"}

            log.info("[AUDITOR] %s aprobada — todos los gates pasaron", task_id)
            return {"task_id": task_id, "passed": True, "error": ""}

        finally:
            if wt_path.exists():
                self._git(["worktree", "remove", "--force", str(wt_path)])

    def merge_task(self, task: dict) -> dict:
        """Merge de la tarea aprobada a main (local only, no push)."""
        task_id = task["id"]
        commit_sha = task.get("commit_sha", "")

        if not commit_sha:
            return {"task_id": task_id, "merged": False, "error": "No commit SHA"}

        try:
            result = self._git(["checkout", "main"])
            if result.returncode != 0:
                return {"task_id": task_id, "merged": False, "error": f"Checkout failed: {result.stderr}"}

            result = self._git(["merge", "--no-ff", "-m", f"merge: {task_id}", commit_sha])
            if result.returncode != 0:
                self._git(["merge", "--abort"])
                return {"task_id": task_id, "merged": False, "error": f"Merge failed: {result.stderr}"}

            # Local merge only — do NOT push to main (branch protection policy).
            # Push is handled by the human via PR workflow.
            log.info("[AUDITOR] %s merged a main (local only, push via PR)", task_id)
            return {"task_id": task_id, "merged": True, "pushed": False, "error": ""}

        except Exception as e:
            return {"task_id": task_id, "merged": False, "error": str(e)}

    def run_cycle(self) -> dict:
        """Ejecuta un ciclo completo de auditoria."""
        log.info("[AUDITOR] Iniciando ciclo de auditoria")

        review_tasks = self._get_review_tasks()
        results = {"audited": 0, "approved": 0, "rejected": 0, "merged": 0}

        for task in review_tasks:
            results["audited"] += 1
            audit = self.audit_task(task)

            if audit["passed"]:
                results["approved"] += 1
                self._api("POST", f"/tasks/{task['id']}/complete", {"commit_sha": task.get("commit_sha", "")})
                merge = self.merge_task(task)
                if merge.get("merged"):
                    results["merged"] += 1
            else:
                results["rejected"] += 1
                self._api(
                    "POST",
                    f"/tasks/{task['id']}/fail",
                    {
                        "error": audit["error"],
                        "require_human": False,
                    },
                )

        log.info("[AUDITOR] Ciclo completado: %s", results)
        return results


def main():
    """Entry point for daemon mode."""
    import time

    logging.basicConfig(level=logging.INFO)
    auditor = Auditor()

    log.info("[AUDITOR] Daemon iniciado — ciclo cada 60s")
    while True:
        try:
            results = auditor.run_cycle()
            if results["audited"] > 0:
                log.info("[AUDITOR] Resultados: %s", results)
        except Exception as e:
            log.error("[AUDITOR] Error en ciclo: %s", e)
        time.sleep(60)


if __name__ == "__main__":
    main()
