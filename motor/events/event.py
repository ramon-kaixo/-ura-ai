from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True)
class Event:
    topic: str
    payload: EventPayload
    timestamp: str = ""
    source: str = "system"
    id: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            object.__setattr__(self, "timestamp", datetime.now(UTC).isoformat())
        if not self.id:
            object.__setattr__(self, "id", uuid.uuid4().hex[:12])


class EventPayload:
    pass


@dataclass
class SystemStarted(EventPayload):
    python_version: str = ""
    ura_version: str = ""


@dataclass
class SystemShutdown(EventPayload):
    reason: str = ""


@dataclass
class SystemDegraded(EventPayload):
    subsystem: str = ""
    since: str = ""


@dataclass
class SystemRestored(EventPayload):
    subsystem: str = ""


@dataclass
class PipelineStarted(EventPayload):
    name: str = ""
    config: dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineCompleted(EventPayload):
    name: str = ""
    result: dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineFailed(EventPayload):
    name: str = ""
    error: str = ""


@dataclass
class PluginLoaded(EventPayload):
    name: str = ""
    version: str = ""


@dataclass
class PluginUnloaded(EventPayload):
    name: str = ""


@dataclass
class PluginError(EventPayload):
    name: str = ""
    error: str = ""


@dataclass
class HookEvent(EventPayload):
    plugin: str = ""
    hook: str = ""
    context: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutorStarted(EventPayload):
    cmd: str = ""


@dataclass
class ExecutorCompleted(EventPayload):
    cmd: str = ""
    returncode: int = -1
    duration_ms: float = 0.0


@dataclass
class ConfigChanged(EventPayload):
    old: dict[str, Any] = field(default_factory=dict)
    new: dict[str, Any] = field(default_factory=dict)
    keys: list[str] = field(default_factory=list)
