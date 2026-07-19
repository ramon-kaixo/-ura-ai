"""AuditLogger — registry of every message sent/received (ADR-028-05 OB01-OB06).

Thread-safe. Bounded memory. Indexed by correlation_id, source+destionation, message_kind.
"""

from __future__ import annotations

import contextlib
import threading
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from motor.platform.models import ProtocolEnvelope


@dataclass
class AuditRecord:
    direction: str  # "send" | "receive"
    message_id: str
    message_type: str
    message_kind: str
    source: str
    destination: str
    correlation_id: str
    timestamp: float
    payload_size: int = 0


AUDIT_BUFFER_MAX = 100_000


class AuditLogger:
    """Records every message sent and received (OB01-OB06).

    OB01: every send logged.
    OB02: every receive logged.
    OB03: indexed by correlation_id.
    OB04: indexed by source + destination.
    OB05: indexed by message_kind.
    OB06: processing time derived from send→receive pairs.
    """

    def __init__(self, max_records: int = AUDIT_BUFFER_MAX) -> None:
        self._max = max_records
        self._records: list[AuditRecord] = []
        self._by_correlation: dict[str, list[int]] = defaultdict(list)
        self._by_source_dest: dict[tuple[str, str], list[int]] = defaultdict(list)
        self._by_kind: dict[str, list[int]] = defaultdict(list)
        self._lock = threading.Lock()
        self._next_id = 0

    def _add(self, record: AuditRecord) -> None:
        idx = self._next_id
        self._next_id += 1
        self._records.append(record)
        self._by_correlation[record.correlation_id].append(idx)
        self._by_source_dest[(record.source, record.destination)].append(idx)
        self._by_kind[record.message_kind].append(idx)
        if len(self._records) > self._max:
            self._trim()

    def _trim(self) -> None:
        excess = len(self._records) - self._max
        if excess <= 0:
            return
        removed = self._records[:excess]
        self._records = self._records[excess:]
        for r in removed:
            corr_list = self._by_correlation.get(r.correlation_id)
            if corr_list:
                with contextlib.suppress(ValueError):
                    corr_list.remove(r.correlation_id)

    def log_send(self, envelope: ProtocolEnvelope) -> None:
        if envelope.routing.message_kind == "event":
            return
        rec = AuditRecord(
            direction="send",
            message_id=str(envelope.routing.message_id),
            message_type=envelope.routing.message_type,
            message_kind=envelope.routing.message_kind,
            source=envelope.routing.source,
            destination=envelope.routing.destination,
            correlation_id=str(envelope.trace.correlation_id or ""),
            timestamp=time.time(),
            payload_size=len(envelope.payload),
        )
        with self._lock:
            self._add(rec)

    def log_receive(self, envelope: ProtocolEnvelope) -> None:
        rec = AuditRecord(
            direction="receive",
            message_id=str(envelope.routing.message_id),
            message_type=envelope.routing.message_type,
            message_kind=envelope.routing.message_kind,
            source=envelope.routing.source,
            destination=envelope.routing.destination,
            correlation_id=str(envelope.trace.correlation_id or ""),
            timestamp=time.time(),
            payload_size=len(envelope.payload),
        )
        with self._lock:
            self._add(rec)

    def by_correlation(self, correlation_id: str) -> Sequence[AuditRecord]:
        with self._lock:
            indices = self._by_correlation.get(correlation_id, [])
            return [self._records[i] for i in indices if i < len(self._records)]

    def by_source_destination(self, source: str, destination: str) -> Sequence[AuditRecord]:
        with self._lock:
            indices = self._by_source_dest.get((source, destination), [])
            return [self._records[i] for i in indices if i < len(self._records)]

    def by_kind(self, kind: str) -> Sequence[AuditRecord]:
        with self._lock:
            indices = self._by_kind.get(kind, [])
            return [self._records[i] for i in indices if i < len(self._records)]

    @property
    def count(self) -> int:
        with self._lock:
            return len(self._records)

    def processing_time(self, correlation_id: str) -> float | None:
        """Return processing time (OB06) for a correlation chain."""
        records = self.by_correlation(correlation_id)
        sends = [r for r in records if r.direction == "send"]
        receives = [r for r in records if r.direction == "receive"]
        if sends and receives:
            return max(r.timestamp for r in receives) - min(s.timestamp for s in sends)
        return None
