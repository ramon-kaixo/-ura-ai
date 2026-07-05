from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class StageDefinition:
    name: str
    plugin: str
    config: dict = field(default_factory=dict)
    timeout: int = 30
    optional: bool = False


@dataclass
class PipelineDefinition:
    name: str
    version: str = ""
    description: str = ""
    stages: list[StageDefinition] = field(default_factory=list)


@dataclass
class StageResult:
    name: str
    ok: bool
    plugin: str
    output: dict = field(default_factory=dict)
    error: str = ""
    duration_ms: float = 0.0


@dataclass
class PipelineResult:
    ok: bool
    name: str
    stages: list[StageResult] = field(default_factory=list)
    error: str = ""
    duration_ms: float = 0.0
