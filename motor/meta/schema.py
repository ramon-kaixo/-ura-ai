"""Esquema declarativo para modulos de URA.

Un modulo se describe en YAML/JSON y el cerebro lo materializa.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class EntityField:
    name: str
    type: str
    required: bool = True
    default: Any = None


@dataclass
class Entity:
    name: str
    fields: list[EntityField] = field(default_factory=list)


@dataclass
class Endpoint:
    method: str
    path: str
    action: str
    entity: str | None = None


@dataclass
class Rule:
    description: str
    condition: str
    action: str


@dataclass
class ModuleMeta:
    name: str
    version: str
    domain: str
    entities: list[Entity] = field(default_factory=list)
    endpoints: list[Endpoint] = field(default_factory=list)
    rules: list[Rule] = field(default_factory=list)

    @classmethod
    def from_yaml(cls, path: str) -> ModuleMeta:
        import yaml
        with open(path) as f:
            data = yaml.safe_load(f)
        return cls(**data)
