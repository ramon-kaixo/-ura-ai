from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path  # noqa: TC003  -- usado en runtime en find_manifest/parse_manifest
from typing import Any

log = logging.getLogger("ura.manifest")


class ManifestError(Exception):
    pass


@dataclass
class PluginManifest:
    api_version: str = "1.0.0"
    name: str = ""
    version: str = "0.1.0"
    description: str = ""
    author: dict[str, Any] = field(default_factory=dict)
    entry_point: str = ""
    dependencies: dict[str, Any] = field(default_factory=lambda: {"plugins": [], "python": []})
    lifecycle: dict[str, Any] = field(default_factory=lambda: {"on_load": True, "on_unload": True})
    hooks: list[str] = field(default_factory=list)
    phases: list[str] = field(default_factory=lambda: ["always"])
    tags: list[str] = field(default_factory=list)


MANIFEST_SCHEMA = frozenset(
    {
        "api_version",
        "name",
        "version",
        "description",
        "author",
        "entry_point",
        "dependencies",
        "lifecycle",
        "hooks",
        "phases",
        "tags",
    },
)

REQUIRED_FIELDS = frozenset({"name"})


def parse_manifest(path: Path) -> PluginManifest | None:
    if not path.exists():
        return None

    source = path.read_text(encoding="utf-8")

    if path.suffix in (".yaml", ".yml"):
        return _parse_yaml(source, path)
    if path.suffix == ".json":
        return _parse_json(source, path)
    log.warning("Formato de manifest no soportado: %s", path.suffix)
    return None


def _parse_yaml(source: str, path: Path) -> PluginManifest | None:
    try:
        import yaml  # type: ignore[import-untyped]

        data = yaml.safe_load(source)
    except ImportError:
        log.warning("PyYAML no disponible — no se puede leer %s", path)
        return None
    except Exception as exc:
        log.warning("Error parseando YAML %s: %s", path, exc)
        return None
    if not isinstance(data, dict):
        log.warning("Manifest YAML debe ser un dict: %s", path)
        return None
    return _build_manifest(data, path)


def _parse_json(source: str, path: Path) -> PluginManifest | None:
    import json

    try:
        data = json.loads(source)
    except Exception as exc:
        log.warning("Error parseando JSON %s: %s", path, exc)
        return None
    if not isinstance(data, dict):
        log.warning("Manifest JSON debe ser un dict: %s", path)
        return None
    return _build_manifest(data, path)


def _build_manifest(data: dict[str, Any], path: Path) -> PluginManifest:
    name = data.get("name", "")
    if not name:
        log.warning("Manifest sin 'name': %s — se usa nombre del archivo", path)
        name = path.parent.stem

    unknown = set(data.keys()) - MANIFEST_SCHEMA
    if unknown:
        log.debug("Campos desconocidos en manifest %s: %s", path, sorted(unknown))

    deps_raw = data.get("dependencies", {})
    dependencies = {
        "plugins": deps_raw.get("plugins", []) if isinstance(deps_raw, dict) else [],
        "python": deps_raw.get("python", []) if isinstance(deps_raw, dict) else [],
    }

    lifecycle = data.get("lifecycle", {})
    if not isinstance(lifecycle, dict):
        lifecycle = {}

    return PluginManifest(
        api_version=str(data.get("api_version", "1.0.0")),
        name=str(name),
        version=str(data.get("version", "0.1.0")),
        description=str(data.get("description", "")),
        author=data.get("author", {}),
        entry_point=str(data.get("entry_point", "")),
        dependencies=dependencies,
        lifecycle={
            "on_load": bool(lifecycle.get("on_load", True)),
            "on_unload": bool(lifecycle.get("on_unload", True)),
            "on_config_change": bool(lifecycle.get("on_config_change", False)),
        },
        hooks=list(data.get("hooks", [])),
        phases=list(data.get("phases", ["always"])),
        tags=list(data.get("tags", [])),
    )


def find_manifest(directory: Path) -> Path | None:
    for name in ("plugin.yaml", "plugin.yml", "plugin.json"):
        candidate = directory / name
        if candidate.exists():
            return candidate
    return None
