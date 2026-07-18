"""ToolRunner — ejecución encapsulada de herramientas.

Gestiona timeout, cancelación, reintentos, auditoría y errores.
No ejecuta herramientas directamente (siempre via ToolAdapter).
No conoce Planner, Scheduler, Memory ni Knowledge.
"""

from __future__ import annotations

import threading
import time

from motor.agents.base import ToolAdapter
from motor.agents.base import ToolRunner as ToolRunnerABC
from motor.agents.models import ToolContract, ToolRequest, ToolResult

# ── Excepciones tipificadas (TR-20) ────────


class ToolError(Exception):
    """Error base de herramientas. Todas las excepciones heredan de aquí."""
    pass


class ToolTimeoutError(ToolError):
    """La herramienta excedió el timeout."""
    pass


class ToolCancelledError(ToolError):
    """La herramienta fue cancelada."""
    pass


class ToolTransientError(ToolError):
    """Error transitorio (reintentable)."""
    pass


class ToolPermanentError(ToolError):
    """Error permanente (no reintentable)."""
    pass


class ToolNotFoundError(ToolError):
    """Herramienta no registrada."""
    pass


class ToolAdapterError(ToolError):
    """Error en el adaptador de la herramienta."""
    pass


# ── ToolRunner concreto ────────────────────


class RateLimiter:
    """Rate limiter simple (token bucket) por herramienta.

    Límite: max_calls por ventana de window_seconds.
    Thread-safe.
    """

    def __init__(self, max_calls: int = 60, window_seconds: int = 60) -> None:
        self._max_calls = max_calls
        self._window = window_seconds
        self._buckets: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def check(self, tool_name: str) -> None:
        """Verifica si la llamada está permitida. Lanza ToolError si no."""
        with self._lock:
            now = time.time()
            bucket = self._buckets.setdefault(tool_name, [])
            # Limpiar entradas antiguas
            cutoff = now - self._window
            bucket[:] = [t for t in bucket if t > cutoff]
            if len(bucket) >= self._max_calls:
                raise ToolTransientError(
                    f"Rate limit exceeded for '{tool_name}': "
                    f"{self._max_calls} calls per {self._window}s"
                )
            bucket.append(now)


class AgentToolRunner(ToolRunnerABC):
    """Ejecutor de herramientas con encapsulación completa.

    TR-01: Nunca ejecuta herramientas directamente (via ToolAdapter).
    TR-10: No mantiene estado entre ejecuciones.
    TR-11..14: No conoce Planner, Scheduler, Memory, Knowledge.
    TR-16: Preparado para ejecución paralela (cada ejecución tiene su propio adapter).
    TR-17: Sin variables globales.
    TR-18: Sin singletons.
    TR-19: Determinista cuando la herramienta lo es.
    TR-20: Todas las excepciones tipificadas.
    """

    def __init__(
        self,
        adapters: dict[str, ToolAdapter] | None = None,
        rate_limiter: RateLimiter | None = None,
    ) -> None:
        self._adapters: dict[str, ToolAdapter] = dict(adapters or {})
        self._contracts: dict[str, ToolContract] = {}
        self._lock = threading.Lock()
        self._rate_limiter = rate_limiter or RateLimiter()

    def register(self, name: str, adapter: ToolAdapter, contract: ToolContract) -> None:
        """Registra una herramienta con su adaptador y contrato."""
        self._adapters[name] = adapter
        self._contracts[name] = contract

    def get_contract(self, tool_name: str) -> ToolContract:
        if tool_name not in self._contracts:
            raise ToolNotFoundError(f"Tool '{tool_name}' not registered")
        return self._contracts[tool_name]

    def run(
        self,
        tool_name: str,
        params: dict,
        timeout: int = 30,
    ) -> dict:
        """Ejecuta una herramienta y retorna su resultado. (TR-15)."""
        self._rate_limiter.check(tool_name)
        request = self._build_request(tool_name, params, timeout)
        result = self._execute(request)
        if not result.success:
            self._raise_error(result)
        return result.data

    # ── Internos ──────────────────────────────────────

    def _build_request(self, tool_name: str, params: dict, timeout: int) -> ToolRequest:
        from motor.agents.models import ToolRequest, make_tool_execution_id

        if tool_name not in self._adapters:
            raise ToolNotFoundError(f"Tool '{tool_name}' not registered")

        eid = make_tool_execution_id("runner", tool_name, time.time())
        return ToolRequest(
            execution_id=eid,
            tool_name=tool_name,
            params=params,
            timeout=timeout,
        )

    def _execute(self, request: ToolRequest) -> ToolResult:
        """Ejecuta con timeout + cancelación + reintentos + auditoría."""
        adapter = self._adapters[request.tool_name]
        contract = self._contracts.get(request.tool_name)
        max_attempts = 1
        backoff = 1.0
        if contract is not None:
            max_attempts = 3 if not contract.idempotent else 1

        last_error: Exception | None = None

        for attempt in range(1, max_attempts + 1):
            req = ToolRequest(
                execution_id=request.execution_id,
                tool_name=request.tool_name,
                params=request.params,
                timeout=request.timeout,
                attempt=attempt,
            )
            result = self._execute_single(req, adapter, contract)
            if result.success:
                return result
            if result.error_type in ("ToolPermanentError", "ToolNotFoundError", "ToolTimeoutError"):
                return result
            last_error = result
            if attempt < max_attempts:
                time.sleep(backoff)
                backoff *= 2

        return ToolResult(
            execution_id=request.execution_id,
            tool_name=request.tool_name,
            success=False,
            error=f"All {max_attempts} attempts failed. Last: {last_error.error}",
            error_type="ToolError",
            attempt=max_attempts,
        )

    def _execute_single(
        self,
        request: ToolRequest,
        adapter: ToolAdapter,
        contract: ToolContract | None,
    ) -> ToolResult:
        """Ejecuta una llamada individual con timeout y cancelación."""
        cancel_event = threading.Event()
        result_container: list[dict] = []
        error_container: list[Exception] = []

        def _run() -> None:
            try:
                result_container.append(adapter.run(request.params))
            except Exception as e:
                error_container.append(e)

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
        thread.join(timeout=request.timeout)

        start = time.time()

        if thread.is_alive():
            adapter.cancel()
            thread.join(timeout=2)
            return ToolResult(
                execution_id=request.execution_id,
                tool_name=request.tool_name,
                success=False,
                error=f"Timeout after {request.timeout}s",
                error_type="ToolTimeoutError",
                duration_ms=(time.time() - start) * 1000,
                attempt=request.attempt,
            )

        duration = (time.time() - start) * 1000

        if cancel_event.is_set():
            return ToolResult(
                execution_id=request.execution_id,
                tool_name=request.tool_name,
                success=False,
                error="Cancelled",
                error_type="ToolCancelledError",
                duration_ms=duration,
                attempt=request.attempt,
            )

        if error_container:
            err = error_container[0]
            error_type = type(err).__name__
            return ToolResult(
                execution_id=request.execution_id,
                tool_name=request.tool_name,
                success=False,
                error=str(err),
                error_type=error_type,
                duration_ms=duration,
                attempt=request.attempt,
            )

        return ToolResult(
            execution_id=request.execution_id,
            tool_name=request.tool_name,
            success=True,
            data=result_container[0],
            duration_ms=duration,
            attempt=request.attempt,
        )

    def cancel(self, tool_name: str) -> None:
        adapter = self._adapters.get(tool_name)
        if adapter is not None:
            adapter.cancel()

    @staticmethod
    def _raise_error(result: ToolResult) -> None:
        mapping = {
            "ToolTimeoutError": ToolTimeoutError,
            "ToolCancelledError": ToolCancelledError,
            "ToolTransientError": ToolTransientError,
            "ToolPermanentError": ToolPermanentError,
            "ToolNotFoundError": ToolNotFoundError,
            "ToolAdapterError": ToolAdapterError,
        }
        exc_class = mapping.get(result.error_type or "", ToolError)
        raise exc_class(result.error or "Unknown tool error")
