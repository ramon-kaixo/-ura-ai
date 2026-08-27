"""Work-Stealing Rebalance — reasignación de tareas entre nodos del pool.

Modelo Opción C:
  - Un nodo que se detiene (para revisión/consulta) marca sus tareas en
    ``in_progress`` como ``paused`` (reservadas a él), y libera a la cola
    común sus tareas ``assigned`` para que otro nodo las termine.
  - Los nodos activos con su cola propia vacía reclaman tareas ``pending``
    de la cola común (work-stealing por ociosidad).
  - ``paused`` NO se roba: solo el nodo que la pausó la reanuda (``resume``).

No toca el núcleo (``core/``), solo ``motor/orchestration/``.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from motor.orchestration.node_registry import NodeRegistry
    from motor.orchestration.task_queue import TaskQueue

log = logging.getLogger(__name__)

# Umbral de tiempo (segundos) para considerar que un nodo se ha detenido
# sin haberse marcado manualmente. Un nodo "vivo" renueva su reserva con
# más frecuencia que este valor; por debajo se asume offline.
_OFFLINE_THRESHOLD_S = 120.0
# Intervalo de barrido del rebalanceador en segundo plano.
_REBALANCE_INTERVAL_S = 30.0


class WorkStealer:
    """Reasigna tareas cuando un nodo del pool se detiene.

    - ``acquire()/release()``: el worker de un nodo registra/libera su
      presencia con timestamp, de modo que el rebalanceador sepa quién está
      vivo (detección por heartbeat de nodo, no de tarea).
    - ``rebalance()``: libera ``assigned``/``in_progress`` de nodos offline a
      la cola común y las ``in_progress`` de un nodo que se detiene las pausa.
    """

    def __init__(
        self,
        queue: TaskQueue,
        registry: NodeRegistry | None = None,
        offline_threshold_s: float = _OFFLINE_THRESHOLD_S,
    ) -> None:
        self._queue = queue
        self._registry = registry
        self._offline_threshold_s = offline_threshold_s
        self._node_last_seen: dict[str, float] = {}
        self._lock = threading.RLock()
        self._registered_nodes: set[str] = set()
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    # ------------------------------------------------------------------
    # Presencia de nodos (heartbeat de nodo)
    # ------------------------------------------------------------------

    def acquire(self, node_id: str) -> None:
        """Registra/marca como presente al nodo worker dado."""
        with self._lock:
            self._node_last_seen[node_id] = time.time()
            self._registered_nodes.add(node_id)

    def release(self, node_id: str) -> None:
        """Marca al nodo como detenido y pausa sus tareas en progreso.

        Opción C: el trabajo ``in_progress`` queda ``paused`` (reservado al
        nodo) y no se reparte a otros; las ``assigned`` se liberan a la cola
        común para que otro nodo del pool las absorba.
        """
        with self._lock:
            self._node_last_seen.pop(node_id, None)
            self._registered_nodes.discard(node_id)
        self._queue.park_in_progress(node_id)
        self._queue.release_pending(node_id)

    def is_present(self, node_id: str) -> bool:
        """Devuelve True si el nodo ha renovado su presencia recientemente."""
        with self._lock:
            last = self._node_last_seen.get(node_id)
            if last is None:
                return False
            return (time.time() - last) < self._offline_threshold_s

    # ------------------------------------------------------------------
    # Rebalanceo
    # ------------------------------------------------------------------

    def rebalance(self, force: bool = False) -> dict[str, int]:
        """Reasigna tareas de nodos ausentes a la cola común.

        Para cada nodo registrado cuyo heartbeat de nodo haya expirado:
          - ``in_progress``/``assigned`` → ``paused`` (reservadas al nodo).
          - Si ``force`` es True, además las ``paused`` se liberan a la
            cola común (rebalanceo explícito).
        Devuelve recuento por acción.
        """
        with self._lock:
            expired = [
                n
                for n in self._registered_nodes
                if (time.time() - self._node_last_seen.get(n, 0.0)) >= self._offline_threshold_s
            ]
            active = [n for n in self._registered_nodes if n not in expired]

        counts: dict[str, int] = {"parked": 0, "released": 0, "stolen_released": 0}

        for node_id in expired:
            parked = self._queue.park_in_progress(node_id)
            released = self._queue.release_pending(node_id)
            counts["parked"] += parked
            counts["released"] += released
            if released or parked:
                log.warning(
                    "[WORKSTEAL] Nodo %s offline → %d pausadas, %d liberadas",
                    node_id,
                    parked,
                    released,
                )
            if force:
                counts["stolen_released"] += self._queue.release_all_paused(node_id)

        if not active:
            log.info("[WORKSTEAL] Rebalance: todos los nodos sin actividad, 0 acciones")
        return counts

    def steal_available(self, node_id: str, limit: int = 5) -> list:
        """Lista tareas ``pending`` que este nodo puede reclamar (work-stealing)."""
        return self._queue.steal_available(node_id, limit)

    # ------------------------------------------------------------------
    # Rebalanceador en segundo plano
    # ------------------------------------------------------------------

    def start(self, interval_s: float = _REBALANCE_INTERVAL_S) -> None:
        """Arranca el barrido periódico de rebalanceo en un hilo daemon."""
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, args=(interval_s,), daemon=True, name="worksteal-rebalance")
        self._thread.start()
        log.info("[WORKSTEAL] Rebalanceador iniciado (intervalo=%.0fs)", interval_s)

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None

    def _loop(self, interval_s: float) -> None:
        while not self._stop.is_set():
            try:
                self.rebalance()
            except Exception as e:
                log.error("[WORKSTEAL] Error en rebalance: %s", e)
            self._stop.wait(timeout=interval_s)

    def status(self) -> dict:
        """Estado del rebalanceador."""
        with self._lock:
            nodes = {n: self.is_present(n) for n in sorted(self._registered_nodes)}
        return {
            "offline_threshold_s": self._offline_threshold_s,
            "nodes": nodes,
            "running": bool(self._thread and self._thread.is_alive()),
        }
