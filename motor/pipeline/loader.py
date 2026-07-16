from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from motor.pipeline.definition import PipelineDefinition, StageDefinition

if TYPE_CHECKING:
    from motor.plugin.registry_v2 import PluginRegistryV2

log = logging.getLogger("ura.pipeline.loader")


class PipelineLoader:
    def __init__(self, registry: PluginRegistryV2) -> None:
        self._registry = registry

    def load(self, path: str | Path) -> PipelineDefinition:
        path = Path(path)
        source = path.read_text(encoding="utf-8")

        if path.suffix in (".yaml", ".yml"):
            import yaml

            data = yaml.safe_load(source)
        elif path.suffix == ".json":
            import json

            data = json.loads(source)
        else:
            raise ValueError(f"Pipeline format not supported: {path.suffix}")

        if not isinstance(data, dict):
            raise ValueError("Pipeline definition must be a dict")

        return self._from_dict(data)

    def _from_dict(self, data: dict) -> PipelineDefinition:
        stages_raw = data.get("stages", [])
        stages = []
        for s in stages_raw:
            stages.append(
                StageDefinition(  # noqa: PERF401  -- legibilidad sobre micro-optimización
                    name=str(s.get("name", "")),
                    plugin=str(s.get("plugin", "")),
                    config=s.get("config", {}),
                    timeout=int(s.get("timeout", 30)),
                    optional=bool(s.get("optional", False)),
                )
            )
        return PipelineDefinition(
            name=str(data.get("name", "")),
            version=str(data.get("version", "")),
            description=str(data.get("description", "")),
            stages=stages,
        )

    def validate(self, pipeline: PipelineDefinition) -> list[str]:
        errors: list[str] = []
        if not pipeline.name:
            errors.append("Pipeline name is required")
        if not pipeline.stages:
            errors.append("At least one stage is required")
            return errors

        names: set[str] = set()
        for s in pipeline.stages:
            if not s.name:
                errors.append("Stage name is required")
            elif s.name in names:
                errors.append(f"Duplicate stage name: {s.name}")
            names.add(s.name)
            if not s.plugin:
                errors.append(f"Stage '{s.name}': plugin is required")
            else:
                meta = self._registry.get_manifest(s.plugin)
                if meta is None:
                    errors.append(f"Stage '{s.name}': plugin '{s.plugin}' not found in registry")

        if errors:
            log.warning("Pipeline validation errors: %s", errors)
        return errors
