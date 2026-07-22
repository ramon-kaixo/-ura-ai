"""TraceMiddleware — wraps subsystem boundaries with distributed tracing.

OBS-02: No subsystem creates a new trace_id; only propagates.
OBS-08: Tracing never modifies functional behavior.
OBS-09: System works if tracing fails.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

from motor.platform.tracing import (
    TraceContext,
    TraceExporter,
    record_latency,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from motor.platform.models import (
        ProtocolEnvelope,
    )

_T = Any  # return type


class TraceMiddleware:
    """Wraps a subsystem callable with distributed tracing.

    Creates or propagates TraceContext and records latencies.
    OBS-08: never modifies the result.
    OBS-09: fails silently.

    Usage:
        middleware = TraceMiddleware(source="f25", destination="f26")
        result = middleware.wrap(memory.append, envelope, "memory.append")
    """

    def __init__(
        self,
        source: str,
        destination: str,
        exporter: TraceExporter | None = None,
    ) -> None:
        self._source = source
        self._destination = destination
        self._exporter = exporter

    def wrap(
        self,
        fn: Callable[..., _T],
        *args: Any,
        message_type: str = "unknown",
        message_kind: str = "command",
        tags: dict[str, str] | None = None,
        envelope: ProtocolEnvelope | None = None,
        **kwargs: Any,
    ) -> _T:
        """Wrap a call with tracing.

        If an envelope with trace header is provided, propagates the
        trace context. Otherwise creates a new one.

        OBS-02: trace_id from incoming envelope is propagated.
        OBS-08: result is never modified.
        OBS-09: silent on tracing failure.
        """
        # Build or propagate trace context
        if envelope and envelope.trace.trace_id.value:
            ctx = TraceContext.from_header(
                envelope.trace,
                self._source,
                self._destination,
            )
        else:
            ctx = TraceContext(
                source=self._source,
                destination=self._destination,
            )

        if self._exporter:
            ctx.set_exporter(self._exporter)

        start_ns = time.monotonic_ns()
        error = False

        try:
            with ctx.span(
                message_type=message_type,
                message_kind=message_kind,
                tags=tags,
            ):
                return fn(*args, **kwargs)
        except Exception:
            error = True
            raise
        finally:
            duration_ns = time.monotonic_ns() - start_ns
            try:
                record_latency(f"{self._source}→{self._destination}", duration_ns, error=error)
            except Exception:
                logging.getLogger("ura.platform.middleware").debug(  # noqa: F821
                    "record_latency failed",
                    exc_info=True,
                )


# ── Wrapper decorator ───────────────────────


def traced(
    source: str,
    destination: str,
    message_type: str | None = None,
    message_kind: str = "command",
    exporter: TraceExporter | None = None,
) -> Callable[..., Any]:
    """Decorator that wraps a function with tracing.

    Usage:
        @traced(source="f25", destination="f26", message_type="memory.append")
        def append_to_memory(entry):
            ...
    """

    def decorator(fn: Callable[..., _T]) -> Callable[..., _T]:
        middleware = TraceMiddleware(
            source=source,
            destination=destination,
            exporter=exporter,
        )

        def wrapper(*args: Any, **kwargs: Any) -> _T:
            mt = message_type or fn.__name__
            return middleware.wrap(
                fn,
                *args,
                **kwargs,
                message_type=mt,
                message_kind=message_kind,
            )

        wrapper.__name__ = fn.__name__
        wrapper.__qualname__ = fn.__qualname__
        return wrapper

    return decorator
