from __future__ import annotations

import importlib
import importlib.util
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from motor.core.state import DegradedMode
from motor.plugin.base import PluginBase, PluginMeta, PluginResult
from motor.plugin.manifest import PluginManifest, find_manifest, parse_manifest

if TYPE_CHECKING:
    from motor.events.bus import EventBus
    from motor.events.hooks import HookManager

log = logging.getLogger("ura.registry.v2")

MOTOR_API_VERSION = "1.0.0"


@dataclass
class PluginEntryV2:
    manifest: PluginManifest | None
    path: Path
    manifest_path: Path | None = None
    legacy_meta: PluginMeta | None = None


class ManifestError(Exception):
    pass


class PluginRegistryV2:
    def __init__(
        self,
        eventbus: EventBus | None = None,
        hook_manager: HookManager | None = None,
    ) -> None:
        self._entries: dict[str, PluginEntryV2] = {}
        self._instances: dict[str, PluginBase] = {}
        self._dm = DegradedMode.instancia()
        self._bus = eventbus
        self._hooks = hook_manager

    @property
    def entries(self) -> dict[str, PluginEntryV2]:
        return dict(self._entries)

    @property
    def loaded(self) -> list[str]:
        return list(self._instances.keys())

    def count(self) -> int:
        return len(self._entries)

    # ── Descubrimiento ──────────────────────────────────────────────────────

    def discover(self, paths: list[str | Path]) -> int:
        count = 0
        for path in paths:
            p = Path(path)
            if p.is_dir():
                count += self._discover_dir(p)
            elif p.is_file() and p.suffix == ".py":
                count += self._discover_legacy(p)
            else:
                log.warning("[registry_v2] Ruta no válida: %s", path)
        log.info("[registry_v2] Descubrimiento: %d plugins en %s", count, paths)
        return count

    def _discover_dir(self, directory: Path) -> int:
        manifest_path = find_manifest(directory)
        if manifest_path is not None:
            manifest = parse_manifest(manifest_path)
            if manifest is not None:
                name = manifest.name
                if name in self._entries:
                    log.warning("[registry_v2] Nombre duplicado: %s (sobrescribe)", name)
                self._entries[name] = PluginEntryV2(
                    manifest=manifest,
                    path=directory,
                    manifest_path=manifest_path,
                )
                log.debug("[registry_v2] Descubierto plugin empaquetado: %s v%s", name, manifest.version)
                return 1
            log.warning("[registry_v2] Manifest inválido en %s", manifest_path)
            return 0

        count = 0
        for pyfile in sorted(directory.glob("*.py")):
            if pyfile.name.startswith("_"):
                continue
            count += self._discover_legacy(pyfile)

        for subdir in sorted(directory.iterdir()):
            if subdir.is_dir() and not subdir.name.startswith(("_", ".")):
                count += self._discover_dir(subdir)

        return count

    def _discover_legacy(self, pyfile: Path) -> int:
        meta = PluginMeta.from_file(pyfile)
        if meta is None:
            return 0
        if meta.name in self._entries:
            log.warning("[registry_v2] Nombre duplicado: %s (sobrescribe)", meta.name)
        self._entries[meta.name] = PluginEntryV2(
            manifest=None,
            path=pyfile,
            legacy_meta=meta,
        )
        log.debug("[registry_v2] Descubierto plugin legacy: %s", meta.name)
        return 1

    # ── Carga lazy ──────────────────────────────────────────────────────────

    def get(self, name: str) -> PluginBase | None:
        return self._load(name)

    def get_manifest(self, name: str) -> PluginManifest | PluginMeta | None:
        entry = self._entries.get(name)
        if entry is None:
            return None
        if entry.manifest is not None:
            return entry.manifest
        return entry.legacy_meta

    def _load(self, name: str) -> PluginBase | None:
        if name in self._instances:
            return self._instances[name]

        entry = self._entries.get(name)
        if entry is None:
            log.warning("[registry_v2] No encontrado: %s", name)
            return None

        if entry.manifest is not None:
            return self._load_v2(entry)

        return self._load_legacy(entry)

    def _load_legacy(self, entry: PluginEntryV2) -> PluginBase | None:
        log.debug("[registry_v2] Carga legacy: %s", entry.path)

        from motor.plugin.registry import PluginRegistry

        legacy = PluginRegistry()
        legacy._entries = {}
        legacy._dm = self._dm
        legacy.discover([str(entry.path)])
        legacy_name = entry.legacy_meta.name if entry.legacy_meta else ""
        plugin = legacy.get(legacy_name)
        if plugin is not None and entry.legacy_meta is not None:
            self._instances[entry.legacy_meta.name] = plugin
        return plugin

    def _load_v2(self, entry: PluginEntryV2) -> PluginBase | None:
        manifest = entry.manifest
        if manifest is None:
            log.warning("[registry_v2] %s: manifest nulo", entry.path)
            return None
        name = manifest.name
        api_version = manifest.api_version

        from motor.events.compat import check_api_compatibility

        if not check_api_compatibility(api_version, MOTOR_API_VERSION):
            log.warning(
                "[registry_v2] %s: API incompatible (plugin=%s, motor=%s)",
                name, api_version, MOTOR_API_VERSION,
            )
            self._dm.mark_degraded(f"plugin:{name}")
            return None

        dep_order = self._resolve_dependencies(name)
        for dep_name in dep_order:
            if dep_name != name and dep_name not in self._instances:
                dep_entry = self._entries.get(dep_name)
                if dep_entry is not None:
                    log.debug("[registry_v2] Cargando dependencia %s para %s", dep_name, name)
                    self._load(dep_name)

        init_py = entry.path / "__init__.py"
        if not init_py.exists():
            log.warning("[registry_v2] %s: falta __init__.py en %s", name, entry.path)
            self._dm.mark_degraded(f"plugin:{name}")
            return None

        try:
            module_name = f"_ura_v2_plugin_{name}"
            spec = importlib.util.spec_from_file_location(module_name, str(init_py))
            if spec is None or spec.loader is None:
                log.warning("[registry_v2] %s: spec inválido para %s", name, init_py)
                self._dm.mark_degraded(f"plugin:{name}")
                return None

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            instance = self._find_plugin_class(module, manifest)
            if instance is None:
                log.warning("[registry_v2] %s: sin subclase de PluginBase", name)
                self._dm.mark_degraded(f"plugin:{name}")
                return None

            instance.manifest = manifest

            if manifest.lifecycle.get("on_load", True):
                try:
                    instance.on_load()
                except Exception as exc:
                    log.warning("[registry_v2] %s on_load falló: %s", name, exc)

            self._instances[name] = instance
            self._dm.mark_healthy(f"plugin:{name}")
            log.info("[registry_v2] Cargado: %s v%s", name, manifest.version)

            if self._hooks is not None:
                self._hooks.register_plugin_hooks(name, instance)

            if self._bus is not None:
                from motor.events.event import PluginLoaded
                from motor.events.topics import PLUGIN_LOADED

                self._bus.publish(
                    PLUGIN_LOADED,
                    PluginLoaded(name=name, version=manifest.version),
                    source="registry_v2",
                )

            return instance

        except Exception as exc:
            log.warning("[registry_v2] Error cargando %s: %s", name, exc)
            self._dm.mark_degraded(f"plugin:{name}")
            return None

    def _find_plugin_class(self, module: object, manifest: PluginManifest) -> PluginBase | None:
        if manifest.entry_point:
            cls = getattr(module, manifest.entry_point, None)
            if cls is not None and isinstance(cls, type) and issubclass(cls, PluginBase) and cls is not PluginBase:
                try:
                    instance = cls()
                    assert isinstance(instance, PluginBase)
                    return instance
                except Exception as exc:
                    log.warning("[registry_v2] Error instanciando %s.%s: %s", manifest.name, manifest.entry_point, exc)
                    return None

        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if isinstance(attr, type) and issubclass(attr, PluginBase) and attr is not PluginBase:
                try:
                    return attr()
                except Exception as exc:
                    log.warning("[registry_v2] Error instanciando %s en %s: %s", attr_name, manifest.name, exc)
                    return None
        return None

    def unload(self, name: str) -> bool:
        if name not in self._instances:
            return False
        instance = self._instances[name]
        manifest = getattr(instance, "manifest", None)

        if self._hooks is not None:
            self._hooks.unregister_plugin_hooks(name)

        if manifest is not None and manifest.lifecycle.get("on_unload", True):
            try:
                instance.on_unload()
            except Exception as exc:
                log.warning("[registry_v2] %s on_unload falló: %s", name, exc)

        del self._instances[name]

        if self._bus is not None:
            from motor.events.event import PluginUnloaded
            from motor.events.topics import PLUGIN_UNLOADED

            self._bus.publish(
                PLUGIN_UNLOADED,
                PluginUnloaded(name=name),
                source="registry_v2",
            )

        log.info("[registry_v2] Descargado: %s", name)
        return True

    # ── Ejecución ───────────────────────────────────────────────────────────

    def run_phase(
        self,
        phase: str,
        context: dict[str, Any] | None = None,
    ) -> list[PluginResult]:
        context = context or {}
        results: list[PluginResult] = []

        phase_entries: list[tuple[str, PluginEntryV2]] = []
        for name, entry in self._entries.items():
            if entry.manifest is not None:
                if phase in entry.manifest.phases or "always" in entry.manifest.phases:
                    phase_entries.append((name, entry))
            elif entry.legacy_meta is not None:
                if entry.legacy_meta.phase in (phase, "always"):
                    phase_entries.append((name, entry))
            else:
                phase_entries.append((name, entry))

        for name, _ in phase_entries:
            start = time.monotonic()
            plugin = self._load(name)
            if plugin is None:
                elapsed = (time.monotonic() - start) * 1000
                results.append(
                    PluginResult(
                        ok=False,
                        plugin=name,
                        phase=phase,
                        error="Plugin load failed",
                        duration_ms=elapsed,
                    ),
                )
                continue

            try:
                data = plugin.execute(context)
                elapsed = (time.monotonic() - start) * 1000
                results.append(PluginResult(ok=True, plugin=name, phase=phase, data=data, duration_ms=elapsed))
            except Exception as exc:
                elapsed = (time.monotonic() - start) * 1000
                log.warning("[registry_v2] %s falló (%.0fms): %s", name, elapsed, exc)
                self._dm.mark_degraded(f"plugin:{name}")
                results.append(PluginResult(ok=False, plugin=name, phase=phase, error=str(exc), duration_ms=elapsed))

        return results

    def run_one(self, name: str, context: dict[str, Any] | None = None) -> PluginResult | None:
        entry = self._entries.get(name)
        if entry is None:
            return None
        if entry.manifest is not None:
            phase = entry.manifest.phases[0] if entry.manifest.phases else "always"
        elif entry.legacy_meta is not None:
            phase = entry.legacy_meta.phase
        else:
            phase = "always"
        results = self.run_phase(phase, context)
        for r in results:
            if r.plugin == name:
                return r
        return None

    # ── Resolución de dependencias ──────────────────────────────────────────

    def _resolve_dependencies(self, plugin_name: str) -> list[str]:
        manifest = self._entries[plugin_name].manifest
        if manifest is None:
            return [plugin_name]

        deps = manifest.dependencies.get("plugins", [])
        resolved: list[str] = []
        visited: set[str] = set()

        def _visit(name: str, path: list[str]) -> None:
            if name in path:
                cycle = " -> ".join([*path, name])
                msg = f"Dependencia circular: {cycle}"
                raise ManifestError(msg)
            if name in visited:
                return
            visited.add(name)

            entry = self._entries.get(name)
            if entry is not None and entry.manifest is not None:
                sub_deps = entry.manifest.dependencies.get("plugins", [])
                for dep in sub_deps:
                    dep_name = dep if isinstance(dep, str) else dep.get("name", "") if isinstance(dep, dict) else ""
                    if dep_name:
                        _visit(dep_name, [*path, name])

            resolved.append(name)

        for dep in deps:
            dep_name = dep if isinstance(dep, str) else dep.get("name", "") if isinstance(dep, dict) else ""
            if dep_name:
                _visit(dep_name, [plugin_name])

        if plugin_name not in visited:
            resolved.append(plugin_name)

        return resolved
