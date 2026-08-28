"""Failover — Deteccion de caida del orquestador y modo autonomo.

Componentes:
  1. OrchestratorHealthChecker: sonda periodica del orquestador (GX10)
  2. RemoteExecutor: SSH unificado con retry y timeout
  3. WorktreeManager: lifecycle completo de worktrees
  4. AutonomousFailover: controlador que asume control cuando el orquestador cae

Flujo de failover:
  1. HealthChecker detecta caida del orquestador (3 fallos consecutivos)
  2. AutonomousFailover activa modo autonomo
  3. WorktreeManager crea aislamiento por tarea
  4. RemoteExecutor valida via SSH contra el nodo remoto
  5. Merge bloqueado si validacion falla
  6. Cuando orquestador responde, retorna a modo normal
"""

from __future__ import annotations

import json
import logging
import shlex
import subprocess
import threading
import time
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from motor.core.utils import atomic_write_json

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_REPO = Path(__file__).parent.parent.parent
_DEFAULT_WORKTREE_DIR = Path("/tmp/ura-worktrees")
_SSH_TIMEOUT_S = 30
_HEALTH_CHECK_INTERVAL_S = 10
_HEALTH_CHECK_TIMEOUT_S = 5
_FAILURE_THRESHOLD = 3
_RECOVERY_THRESHOLD = 2


# ---------------------------------------------------------------------------
# Orchestrator Health Checker
# ---------------------------------------------------------------------------


class OrchestratorState(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    DOWN = "down"


@dataclass
class HealthCheckResult:
    """Resultado de un health check."""

    state: OrchestratorState
    latency_ms: float
    consecutive_failures: int
    last_check: str
    error: str = ""


class OrchestratorHealthChecker:
    """Sonda periodica del orquestador con anti-flapping.

    Anti-flapping rules:
      - DOWN: >= failure_threshold failures within failure_window_s (default: 5 in 60s)
      - NORMAL: >= recovery_threshold consecutive successes (default: 3)
      - Prevents rapid state oscillation when orchestrator is unstable.
    """

    def __init__(
        self,
        orchestrator_url: str = "http://100.72.103.12:4097",
        interval_s: float = _HEALTH_CHECK_INTERVAL_S,
        timeout_s: float = _HEALTH_CHECK_TIMEOUT_S,
        failure_threshold: int = 5,
        recovery_threshold: int = 3,
        failure_window_s: float = 60.0,
    ) -> None:
        self._url = orchestrator_url
        self._interval_s = interval_s
        self._timeout_s = timeout_s
        self._failure_threshold = failure_threshold
        self._recovery_threshold = recovery_threshold
        self._failure_window_s = failure_window_s

        self._state = OrchestratorState.HEALTHY
        self._consecutive_failures = 0
        self._consecutive_recoveries = 0
        self._failure_timestamps: list[float] = []  # For time-windowed anti-flapping
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._callbacks: list[Any] = []

    @property
    def state(self) -> OrchestratorState:
        with self._lock:
            return self._state

    @property
    def is_down(self) -> bool:
        return self.state == OrchestratorState.DOWN

    def on_state_change(self, callback: Any) -> None:
        """Registra callback para cambios de estado: callback(new_state, old_state)."""
        self._callbacks.append(callback)

    def _probe(self) -> HealthCheckResult:
        """Ejecuta un solo health check."""
        import urllib.request
        from urllib.error import URLError

        start = time.monotonic()
        try:
            req = urllib.request.Request(f"{self._url}/health")  # noqa: S310
            with urllib.request.urlopen(req, timeout=self._timeout_s) as resp:  # noqa: S310
                json.loads(resp.read())
                latency = (time.monotonic() - start) * 1000
                return HealthCheckResult(
                    state=OrchestratorState.HEALTHY,
                    latency_ms=round(latency, 1),
                    consecutive_failures=self._consecutive_failures,
                    last_check=time.strftime("%Y-%m-%dT%H:%M:%S"),
                )
        except (URLError, OSError, TimeoutError, json.JSONDecodeError) as e:
            latency = (time.monotonic() - start) * 1000
            return HealthCheckResult(
                state=OrchestratorState.DOWN,
                latency_ms=round(latency, 1),
                consecutive_failures=self._consecutive_failures + 1,
                last_check=time.strftime("%Y-%m-%dT%H:%M:%S"),
                error=str(e),
            )

    def _update_state(self, result: HealthCheckResult) -> None:
        """Actualiza estado basado en resultado del check con anti-flapping."""
        with self._lock:
            old_state = self._state
            now = time.monotonic()

            if result.error:
                self._consecutive_failures += 1
                self._consecutive_recoveries = 0
                self._failure_timestamps.append(now)

                # Prune old failures outside the window
                cutoff = now - self._failure_window_s
                self._failure_timestamps = [t for t in self._failure_timestamps if t > cutoff]

                # Anti-flapping: only go DOWN if >= threshold failures within window
                if len(self._failure_timestamps) >= self._failure_threshold:
                    self._state = OrchestratorState.DOWN
                elif self._consecutive_failures >= 1:
                    self._state = OrchestratorState.DEGRADED
            else:
                self._consecutive_recoveries += 1
                self._consecutive_failures = 0
                self._failure_timestamps.clear()

                # Anti-flapping: need consecutive recoveries to exit DOWN
                if self._state == OrchestratorState.DOWN:
                    if self._consecutive_recoveries >= self._recovery_threshold:
                        self._state = OrchestratorState.HEALTHY
                elif self._state == OrchestratorState.DEGRADED:
                    self._state = OrchestratorState.HEALTHY

            if self._state != old_state:
                log.warning(
                    "[HEALTH] State: %s → %s (failures=%d/%d in %.0fs, recoveries=%d/%d)",
                    old_state.value,
                    self._state.value,
                    len(self._failure_timestamps),
                    self._failure_threshold,
                    self._failure_window_s,
                    self._consecutive_recoveries,
                    self._recovery_threshold,
                )
                for cb in self._callbacks:
                    try:
                        cb(self._state, old_state)
                    except Exception as e:
                        log.error("[HEALTH] Callback error: %s", e)

    def _loop(self) -> None:
        """Loop principal de health checking."""
        while not self._stop.is_set():
            result = self._probe()
            self._update_state(result)
            self._stop.wait(timeout=self._interval_s)

    def start(self) -> None:
        """Inicia el health checker en background."""
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="health-checker")
        self._thread.start()
        log.info("[HEALTH] Started (interval=%ds, url=%s)", self._interval_s, self._url)

    def stop(self) -> None:
        """Detiene el health checker."""
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)
        log.info("[HEALTH] Stopped")

    def check_now(self) -> HealthCheckResult:
        """Ejecuta un check inmediato (sincrono)."""
        result = self._probe()
        self._update_state(result)
        return result


# ---------------------------------------------------------------------------
# Remote Executor — SSH unificado
# ---------------------------------------------------------------------------


@dataclass
class RemoteResult:
    """Resultado de una ejecucion remota."""

    success: bool
    stdout: str
    stderr: str
    returncode: int
    command: str
    host: str
    duration_s: float


class RemoteExecutor:
    """Ejecutor SSH unificado con retry y timeout.

    Usa ControlMaster para multiplexar conexiones cuando es posible.
    Reintenta automaticamente en fallos transitorios.
    """

    def __init__(
        self,
        default_host: str = "ramon@100.72.103.12",
        timeout_s: int = _SSH_TIMEOUT_S,
        max_retries: int = 2,
        retry_delay_s: float = 2.0,
    ) -> None:
        self._default_host = default_host
        self._timeout_s = timeout_s
        self._max_retries = max_retries
        self._retry_delay_s = retry_delay_s

    def run(
        self,
        command: str,
        host: str | None = None,
        timeout_s: int | None = None,
        cwd: str | None = None,
    ) -> RemoteResult:
        """Ejecuta un comando via SSH con retry."""
        target_host = host or self._default_host
        timeout = timeout_s or self._timeout_s

        if cwd:
            # Security: sanitize cwd to prevent command injection
            safe_cwd = str(Path(cwd).resolve())
            command = f"cd {safe_cwd} && {command}"

        # Security: quote the entire command for the remote shell
        quoted_command = shlex.quote(command)

        last_error = ""
        for attempt in range(self._max_retries + 1):
            start = time.monotonic()
            try:
                result = subprocess.run(
                    [
                        "ssh",
                        "-o",
                        "StrictHostKeyChecking=no",
                        "-o",
                        "BatchMode=yes",
                        "-o",
                        f"ConnectTimeout={timeout}",
                        "-o",
                        "ControlMaster=auto",
                        "-o",
                        "ControlPath=/tmp/ura-ssh-%r@%h:%p",
                        "-o",
                        "ControlPersist=60",
                        target_host,
                        quoted_command,
                    ],
                    capture_output=True,
                    text=True,
                    timeout=timeout + 5,
                    check=False,
                )
                duration = time.monotonic() - start

                if result.returncode == 0:
                    return RemoteResult(
                        success=True,
                        stdout=result.stdout,
                        stderr=result.stderr,
                        returncode=0,
                        command=command,
                        host=target_host,
                        duration_s=round(duration, 2),
                    )

                last_error = result.stderr.strip()
                log.warning(
                    "[SSH] Command failed (attempt %d/%d): %s — %s",
                    attempt + 1,
                    self._max_retries + 1,
                    command[:60],
                    last_error[:100],
                )

            except subprocess.TimeoutExpired:
                duration = time.monotonic() - start
                last_error = f"Timeout after {timeout}s"
                log.warning(
                    "[SSH] Timeout (attempt %d/%d): %s",
                    attempt + 1,
                    self._max_retries + 1,
                    command[:60],
                )
            except Exception as e:
                duration = time.monotonic() - start
                last_error = str(e)
                log.warning(
                    "[SSH] Error (attempt %d/%d): %s",
                    attempt + 1,
                    self._max_retries + 1,
                    last_error[:100],
                )

            if attempt < self._max_retries:
                time.sleep(self._retry_delay_s)

        return RemoteResult(
            success=False,
            stdout="",
            stderr=last_error,
            returncode=-1,
            command=command,
            host=target_host,
            duration_s=round(duration, 2),
        )

    def is_reachable(self, host: str | None = None) -> bool:
        """Verifica si un host es alcanzable via SSH."""
        result = self.run("echo ok", host=host, timeout_s=5)
        return result.success and "ok" in result.stdout

    def cleanup_control_socket(self, host: str | None = None) -> bool:
        """Cierra el socket de ControlMaster para un host."""
        target_host = host or self._default_host
        # Parse user@host:port
        user_host = target_host.split(":")[0]
        try:
            subprocess.run(
                ["ssh", "-o", "ControlMaster=no", "-O", "exit", user_host],
                capture_output=True,
                timeout=5,
                check=False,
            )
            log.info("[SSH] Control socket closed for %s", user_host)
            return True
        except Exception as e:
            log.debug("[SSH] Error closing control socket: %s", e)
            return False

    def connection_status(self, host: str | None = None) -> dict[str, Any]:
        """Verifica el estado de la conexión SSH multiplexada."""
        target_host = host or self._default_host
        user_host = target_host.split(":")[0]
        try:
            result = subprocess.run(
                ["ssh", "-O", "check", user_host],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            alive = result.returncode == 0
            return {
                "host": user_host,
                "alive": alive,
                "control_path": f"/tmp/ura-ssh-{user_host.replace('@', '-')}",
            }
        except Exception as e:
            return {"host": user_host, "alive": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Worktree Manager — Lifecycle completo
# ---------------------------------------------------------------------------


class WorktreeState(StrEnum):
    CREATING = "creating"
    ACTIVE = "active"
    VALIDATING = "validating"
    MERGING = "merging"
    CLEANING = "cleaning"
    DONE = "done"
    FAILED = "failed"


@dataclass
class Worktree:
    """Un worktree activo."""

    task_id: str
    path: Path
    branch: str
    base_commit: str
    state: WorktreeState
    created_at: str = ""
    error: str = ""


class WorktreeManager:
    """Gestiona el lifecycle completo de worktrees aislados.

    Crea worktrees por tarea, valida via SSH, y bloquea merge
    si la validacion falla.
    """

    def __init__(
        self,
        repo_root: Path | str = _DEFAULT_REPO,
        worktree_dir: Path | str = _DEFAULT_WORKTREE_DIR,
        remote_executor: RemoteExecutor | None = None,
    ) -> None:
        self._repo = Path(repo_root)
        self._wt_dir = Path(worktree_dir)
        self._wt_dir.mkdir(parents=True, exist_ok=True)
        self._executor = remote_executor or RemoteExecutor()
        self._worktrees: dict[str, Worktree] = {}
        self._lock = threading.Lock()

    @property
    def active_count(self) -> int:
        with self._lock:
            return sum(
                1 for wt in self._worktrees.values() if wt.state not in (WorktreeState.DONE, WorktreeState.FAILED)
            )

    def create(self, task_id: str, branch: str | None = None) -> Worktree:
        """Crea un worktree aislado para una tarea."""
        branch = branch or f"feature-{task_id}"
        wt_path = self._wt_dir / task_id

        # Get current HEAD as base
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(self._repo),
            capture_output=True,
            text=True,
            check=False,
        )
        base_commit = result.stdout.strip() if result.returncode == 0 else "HEAD"

        # Remove existing worktree if any
        if wt_path.exists():
            subprocess.run(
                ["git", "worktree", "remove", "--force", str(wt_path)],
                cwd=str(self._repo),
                capture_output=True,
                check=False,
            )

        # Create worktree
        result = subprocess.run(
            ["git", "worktree", "add", "-b", branch, str(wt_path), base_commit],
            cwd=str(self._repo),
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            raise RuntimeError(f"Failed to create worktree: {result.stderr}")

        from datetime import UTC, datetime

        wt = Worktree(
            task_id=task_id,
            path=wt_path,
            branch=branch,
            base_commit=base_commit,
            state=WorktreeState.ACTIVE,
            created_at=datetime.now(UTC).isoformat(),
        )

        with self._lock:
            self._worktrees[task_id] = wt

        log.info("[WORKTREE] Created: %s at %s (branch: %s)", task_id, wt_path, branch)
        return wt

    def validate(
        self,
        task_id: str,
        remote_host: str | None = None,
        interface_contract: str = "INTERFACE_CONTRACTS.md",
    ) -> tuple[bool, str]:
        """Valida un worktree via SSH contra el nodo remoto.

        Ejecuta pytest en el worktree remoto y verifica contratos.
        Retorna (passed, error_message).
        """
        wt = self._worktrees.get(task_id)
        if not wt:
            return False, f"Worktree not found: {task_id}"

        with self._lock:
            wt.state = WorktreeState.VALIDATING

        # Sync worktree to remote
        remote_path = "/home/ramon/URA/ura_ia_1972"
        sync_result = subprocess.run(
            [
                "rsync",
                "-avz",
                "--delete",
                "--exclude=.git",
                "--exclude=__pycache__",
                "--exclude=.pytest_cache",
                f"{wt.path}/",
                f"{self._executor._default_host.split('@')[1] if '@' in self._executor._default_host else self._executor._default_host}:{remote_path}/worktrees/{task_id}/",
            ],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )

        if sync_result.returncode != 0:
            with self._lock:
                wt.state = WorktreeState.FAILED
                wt.error = f"Sync failed: {sync_result.stderr[:200]}"
            return False, wt.error

        # Run validation on remote
        validate_cmd = (
            f"cd {remote_path}/worktrees/{task_id} && python3 -m pytest tests/ -x -q --tb=line --timeout=30 2>&1"
        )
        result = self._executor.run(validate_cmd, host=remote_host)

        if not result.success or result.returncode != 0:
            error = result.stderr or result.stdout
            with self._lock:
                wt.state = WorktreeState.FAILED
                wt.error = error[:500]
            log.warning("[WORKTREE] Validation FAILED for %s: %s", task_id, error[:200])
            return False, error

        with self._lock:
            wt.state = WorktreeState.ACTIVE
        log.info("[WORKTREE] Validation PASSED for %s", task_id)
        return True, ""

    def merge(self, task_id: str) -> tuple[bool, str]:
        """Merge del worktree a main. Bloqueado si validacion fallo."""
        wt = self._worktrees.get(task_id)
        if not wt:
            return False, f"Worktree not found: {task_id}"

        if wt.state == WorktreeState.FAILED:
            return False, f"Merge BLOCKED: validation failed — {wt.error[:200]}"

        with self._lock:
            wt.state = WorktreeState.MERGING

        try:
            # Checkout main
            result = subprocess.run(
                ["git", "checkout", "main"],
                cwd=str(self._repo),
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                return False, f"Checkout main failed: {result.stderr}"

            # Merge
            result = subprocess.run(
                ["git", "merge", "--no-ff", "-m", f"merge: {task_id}", wt.branch],
                cwd=str(self._repo),
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                subprocess.run(
                    ["git", "merge", "--abort"],
                    cwd=str(self._repo),
                    capture_output=True,
                    check=False,
                )
                with self._lock:
                    wt.state = WorktreeState.FAILED
                    wt.error = f"Merge conflict: {result.stderr[:300]}"
                return False, wt.error

            with self._lock:
                wt.state = WorktreeState.DONE
            log.info("[WORKTREE] Merged %s to main", task_id)
            return True, ""

        except Exception as e:
            with self._lock:
                wt.state = WorktreeState.FAILED
                wt.error = str(e)
            return False, str(e)

    def cleanup(self, task_id: str) -> None:
        """Limpia un worktree."""
        wt = self._worktrees.get(task_id)
        if not wt:
            return

        with self._lock:
            wt.state = WorktreeState.CLEANING

        subprocess.run(
            ["git", "worktree", "remove", "--force", str(wt.path)],
            cwd=str(self._repo),
            capture_output=True,
            check=False,
        )

        with self._lock:
            wt.state = WorktreeState.DONE
        log.info("[WORKTREE] Cleaned up: %s", task_id)

    def cleanup_all(self) -> int:
        """Limpia todos los worktrees. Retorna count eliminados."""
        count = 0
        with self._lock:
            task_ids = list(self._worktrees.keys())

        for task_id in task_ids:
            self.cleanup(task_id)
            count += 1
        return count

    def list_active(self) -> list[Worktree]:
        """Lista worktrees activos."""
        with self._lock:
            return [wt for wt in self._worktrees.values() if wt.state != WorktreeState.DONE]


# ---------------------------------------------------------------------------
# Autonomous Failover Controller
# ---------------------------------------------------------------------------


class FailoverMode(StrEnum):
    NORMAL = "normal"
    AUTONOMOUS = "autonomous"


class AutonomousFailover:
    """Controlador de failover autonomo.

    Cuando el orquestador (GX10) cae, este modulo:
    1. Activa modo autonomo
    2. Crea worktrees aislados por tarea
    3. Valida via SSH contra el nodo remoto
    4. Bloquea merge si validacion falla
    5. Cuando orquestador responde, retorna a modo normal

    Uso:
        failover = AutonomousFailover()
        failover.start()  # Inicia health checking
        # ... trabaja normalmente ...
        # Cuando GX10 cae, automaticamente entra en modo autonomo
    """

    def __init__(
        self,
        health_checker: OrchestratorHealthChecker | None = None,
        worktree_manager: WorktreeManager | None = None,
        remote_executor: RemoteExecutor | None = None,
        state_path: Path | str | None = None,
    ) -> None:
        self._executor = remote_executor or RemoteExecutor()
        self._health = health_checker or OrchestratorHealthChecker()
        self._worktrees = worktree_manager or WorktreeManager(remote_executor=self._executor)
        self._mode = FailoverMode.NORMAL
        self._lock = threading.Lock()

        if state_path:
            self._state_path = Path(state_path)
        else:
            self._state_path = Path.home() / ".ura" / "failover-state.json"
            self._state_path.parent.mkdir(parents=True, exist_ok=True)

        # Register callback for state changes
        self._health.on_state_change(self._on_health_change)

    @property
    def mode(self) -> FailoverMode:
        with self._lock:
            return self._mode

    @property
    def is_autonomous(self) -> bool:
        return self.mode == FailoverMode.AUTONOMOUS

    def _on_health_change(self, new_state: OrchestratorState, old_state: OrchestratorState) -> None:
        """Callback when orchestrator health changes. Thread-safe state transitions."""
        with self._lock:
            if new_state == OrchestratorState.DOWN and old_state != OrchestratorState.DOWN:
                if self._mode == FailoverMode.AUTONOMOUS:
                    return
                self._mode = FailoverMode.AUTONOMOUS
                log.critical("[FAILOVER] Entering AUTONOMOUS mode — orchestrator DOWN")
                atomic_write_json(
                    self._state_path,
                    {
                        "mode": "autonomous",
                        "entered_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                        "reason": "orchestrator_down",
                    },
                )
            elif new_state == OrchestratorState.HEALTHY and old_state == OrchestratorState.DOWN:
                if self._mode == FailoverMode.NORMAL:
                    return
                self._mode = FailoverMode.NORMAL
                log.info("[FAILOVER] Exiting autonomous mode — orchestrator RECOVERED")
                atomic_write_json(
                    self._state_path,
                    {
                        "mode": "normal",
                        "exited_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                        "reason": "orchestrator_recovered",
                    },
                )
                # Cleanup worktrees
                cleaned = self._worktrees.cleanup_all()
                if cleaned > 0:
                    log.info("[FAILOVER] Cleaned up %d worktrees after recovery", cleaned)

    def start(self) -> None:
        """Inicia el sistema de failover."""
        self._health.start()
        log.info("[FAILOVER] Started (mode=%s)", self._mode.value)

    def stop(self) -> None:
        """Detiene el sistema de failover."""
        self._health.stop()
        self._worktrees.cleanup_all()
        log.info("[FAILOVER] Stopped")

    def execute_task(
        self,
        task_id: str,
        command: str,
        remote_host: str | None = None,
    ) -> tuple[bool, str]:
        """Ejecuta una tarea con aislamiento y validacion.

        En modo normal: ejecuta directamente.
        En modo autonomo: crea worktree, valida via SSH, bloquea merge si falla.
        """
        if self.mode == FailoverMode.NORMAL:
            # Normal mode: execute directly
            result = self._executor.run(command, host=remote_host)
            return result.success, result.stderr

        # Autonomous mode: worktree isolation + remote validation
        log.info("[FAILOVER] Autonomous task execution: %s", task_id)

        try:
            # 1. Create isolated worktree
            wt = self._worktrees.create(task_id)

            # 2. Execute in worktree
            safe_path = str(Path(wt.path).resolve())
            result = self._executor.run(
                command,
                host=remote_host,
                cwd=safe_path,
            )

            if not result.success:
                with self._lock:
                    wt.state = WorktreeState.FAILED
                    wt.error = result.stderr[:500]
                return False, result.stderr

            # 3. Validate via remote pytest
            passed, error = self._worktrees.validate(task_id, remote_host=remote_host)

            if not passed:
                log.warning("[FAILOVER] Task %s FAILED validation: %s", task_id, error[:200])
                return False, error

            # 4. Merge blocked if validation failed (already checked above)
            log.info("[FAILOVER] Task %s PASSED validation", task_id)
            return True, ""

        except Exception as e:
            log.error("[FAILOVER] Task %s error: %s", task_id, e)
            return False, str(e)

    def get_status(self) -> dict[str, Any]:
        """Retorna estado actual del failover."""
        return {
            "mode": self._mode.value,
            "orchestrator_state": self._health.state.value,
            "active_worktrees": self._worktrees.active_count,
            "health_url": self._health._url,
        }
