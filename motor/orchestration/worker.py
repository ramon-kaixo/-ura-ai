"""Worker daemon — ejecuta tareas de la cola común en cada nodo del pool.

Modelo Opción C (work-stealing):
  - Reclama el trabajo ``pending``/``timeout`` de la cola común, priorizando
    las tareas de su propio ``node_id`` y robando las de otros cuando está
    ocioso.
  - Ejecuta cada tarea lanzando ``opencode run`` (comando configurable con
    ``URA_WORKER_CMD``).
  - Mantiene heartbeat de nodo (presencia) y de tarea durante la ejecución.
  - Al detenerse, pausa sus tareas ``in_progress`` y libera las ``assigned``
    para que otro nodo del pool las absorba.

Lanzamiento por nodo:
  - GX10: systemd user (ura-worker.service), env ``URA_NODE_ID=gx10``.
  - Mac:  launchd LaunchAgent (com.ura.worker.plist), env ``URA_NODE_ID=mac``.
"""

from __future__ import annotations

import logging
import os
import shlex
import subprocess
import threading
from contextlib import suppress
from pathlib import Path
from typing import Any

log = logging.getLogger("ura.worker")

_DEFAULT_POLL_INTERVAL_S = 5.0
_DEFAULT_TASK_HEARTBEAT_S = 15.0
_DEFAULT_CMD = "opencode run"
_MAX_OUTPUT_LOG = 2000


class WorkerError(Exception):
    """Error ejecutando una tarea."""


class NodeWorker:
    """Worker que reclama y ejecuta tareas en un nodo del pool."""

    def __init__(
        self,
        node_id: str = "",
        agent: str = "",
        poll_interval_s: float = _DEFAULT_POLL_INTERVAL_S,
        task_heartbeat_s: float = _DEFAULT_TASK_HEARTBEAT_S,
        runner: Any | None = None,
        cmd: str = "",
        repo: Path | None = None,
    ) -> None:
        from motor.orchestration.task_queue import TaskQueue

        self.node_id = node_id or os.environ.get("URA_NODE_ID", "unknown")
        self.agent = agent or f"worker-{self.node_id}"
        self.poll_interval_s = poll_interval_s
        self.task_heartbeat_s = task_heartbeat_s
        self._queue = runner or TaskQueue()
        self._cmd = cmd or os.environ.get("URA_WORKER_CMD", _DEFAULT_CMD)
        self._repo = repo or Path(os.environ.get("URA_WORKER_REPO", "."))
        self._stop = threading.Event()
        self._heartbeat_thread: threading.Thread | None = None
        self._current_task_id: str | None = None

    # ------------------------------------------------------------------
    # Ciclo principal
    # ------------------------------------------------------------------

    def run_once(self) -> bool:
        """Reclama y ejecuta una tarea si hay disponible. Devuelve True si ejecutó algo."""
        task = self._queue.claim_next(self.agent, self.node_id)
        if task is None:
            return False
        self._execute(task)
        return True

    def run(self) -> None:
        """Bucle principal del worker hasta que se llame a ``stop()``."""
        log.info("[WORKER] %s iniciado (poll=%.0fs, cmd=%s)", self.agent, self.poll_interval_s, self._cmd)
        self.mark_present()
        while not self._stop.is_set():
            try:
                did_work = self.run_once()
                if not did_work:
                    self._stop.wait(timeout=self.poll_interval_s)
            except WorkerError as e:
                log.error("[WORKER] Error ejecutando: %s", e)
            except Exception as e:
                log.exception("[WORKER] Error inesperado: %s", e)
                self._stop.wait(timeout=self.poll_interval_s)
        self.mark_absent()
        log.info("[WORKER] %s detenido", self.agent)

    def stop(self) -> None:
        self._stop.set()
        self._stop_task_heartbeat()
        if self._current_task_id:
            with suppress(Exception):
                self._queue.pause(self._current_task_id, self.node_id)

    # ------------------------------------------------------------------
    # Presencia de nodo (integración con WorkStealer)
    # ------------------------------------------------------------------

    def _stealer(self) -> Any:
        from motor.orchestration.worksteal import WorkStealer

        return WorkStealer(self._queue)

    def mark_present(self) -> None:
        with suppress(Exception):
            self._stealer().acquire(self.node_id)

    def mark_absent(self) -> None:
        with suppress(Exception):
            self._stealer().release(self.node_id)

    # ------------------------------------------------------------------
    # Ejecución
    # ------------------------------------------------------------------

    def _execute(self, task: Any) -> None:
        self._current_task_id = task.id
        try:
            started = self._queue.start(task.id)
            if started is None:
                log.warning("[WORKER] %s no pudo iniciarse (no assigned)", task.id)
                return
        except Exception as e:
            log.warning("[WORKER] start %s falló: %s", task.id, e)
            return

        self._start_task_heartbeat(task.id)
        try:
            commit_sha = self._run_opencode(task)
            self._queue.complete(task.id, commit_sha)
            log.info("[WORKER] %s completada", task.id)
        except WorkerError as e:
            self._queue.fail(task.id, str(e))
            log.error("[WORKER] %s falló: %s", task.id, e)
        except Exception as e:
            self._queue.fail(task.id, str(e))
            log.exception("[WORKER] %s error inesperado: %s", task.id, e)
        finally:
            self._stop_task_heartbeat()
            self._current_task_id = None

    def _build_command(self, task: Any) -> list[str]:
        desc = task.description.strip()
        age = shlex.quote(desc[:200])
        script = f'"{self._cmd}" "{age}"'
        return ["/bin/sh", "-c", script]

    def _run_opencode(self, task: Any) -> str:
        """Lanza ``opencode run`` para la tarea y devuelve el commit_sha si existe."""
        cmd = self._build_command(task)
        log.info("[WORKER] Ejecutando %s: %s", task.id, " ".join(cmd))
        try:
            result = subprocess.run(
                cmd,
                cwd=str(self._repo),
                capture_output=True,
                text=True,
                timeout=task.timeout_seconds,
                check=False,
            )
        except FileNotFoundError as e:
            raise WorkerError(
                f"No se encontró el ejecutor '{self._cmd}'. "
                "Configura URA_WORKER_CMD con la ruta de `opencode` del nodo."
            ) from e
        except subprocess.TimeoutExpired as e:
            raise WorkerError(f"Timeout ejecutando {task.id} ({task.timeout_seconds}s)") from e

        output = (result.stdout or "") + (result.stderr or "")
        if len(output) > _MAX_OUTPUT_LOG:
            output = output[-_MAX_OUTPUT_LOG:]
        if result.returncode != 0:
            raise WorkerError(f"opencode exit={result.returncode}: {output[-500:]}")

        return self._extract_commit(task.id, result.stdout or "")

    @staticmethod
    def _extract_commit(task_id: str, stdout: str) -> str:
        """Extrae el SHA de commit del contexto/resultado, si aplica."""
        for line in stdout.splitlines():
            stripped = line.strip()
            if stripped.startswith("commit:"):
                return stripped.split(":", 1)[1].strip().split()[0]
            if stripped.startswith("commit "):
                parts = stripped.split(" ", 1)[1].split()
                return parts[0] if parts else ""
        return ""

    # ------------------------------------------------------------------
    # Heartbeat de tarea
    # ------------------------------------------------------------------

    def _start_task_heartbeat(self, task_id: str) -> None:
        self._stop_heartbeat_thread()
        self._task_hb_stop = threading.Event()
        self._heartbeat_thread = threading.Thread(
            target=self._task_heartbeat_loop, args=(task_id, self._task_hb_stop), daemon=True
        )
        self._heartbeat_thread.start()

    def _task_heartbeat_loop(self, task_id: str, stop: threading.Event) -> None:
        while not stop.is_set():
            with suppress(Exception):
                self._queue.heartbeat(task_id)
            stop.wait(timeout=self.task_heartbeat_s)

    def _stop_task_heartbeat(self) -> None:
        self._stop_heartbeat_thread()

    def _stop_heartbeat_thread(self) -> None:
        if self._heartbeat_thread:
            self._task_hb_stop.set()
            self._heartbeat_thread.join(timeout=2)
            self._heartbeat_thread = None


def main() -> None:
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    parser = argparse.ArgumentParser(description="URA node worker (work-stealing pool)")
    parser.add_argument("--node-id", default=os.environ.get("URA_NODE_ID", "unknown"))
    parser.add_argument("--poll", type=float, default=_DEFAULT_POLL_INTERVAL_S)
    parser.add_argument("--cmd", default=os.environ.get("URA_WORKER_CMD", _DEFAULT_CMD))
    parser.add_argument("--repo", default=os.environ.get("URA_WORKER_REPO", "."))
    args = parser.parse_args()

    worker = NodeWorker(
        node_id=args.node_id,
        poll_interval_s=args.poll,
        cmd=args.cmd,
        repo=Path(args.repo),
    )
    try:
        worker.run()
    except KeyboardInterrupt:
        worker.stop()


if __name__ == "__main__":
    main()
