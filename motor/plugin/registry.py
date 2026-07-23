"""PluginRegistry — descubre y ejecuta plugins via importlib.

Registro dinámico con carga lazy, aislamiento de fallos e integración
con DegradedMode.

Principios:
- El escaneo (discover) solo lee metadatos vía AST — no importa módulos
- La importación real ocurre solo cuando se necesita (lazy load)
- Un plugin que falla al cargar no impide cargar ni ejecutar el resto
- Los fallos se registran en DegradedMode para visibilidad operativa

Uso:
    registry = PluginRegistry()
    registry.discover(["scripts/pro/plugins"])
    results = registry.run_phase("pre", {"dry_run": True})
"""

from __future__ import annotations

import importlib
import importlib.util
import logging
import time
from pathlib import Path
from typing import Any

from motor.core.state import DegradedMode
from motor.plugin.base import PluginBase, PluginEntry, PluginMeta, PluginResult

log = logging.getLogger("ura.plugin")


class PluginRegistry:
    """Registro dinámico de plugins con carga lazy."""

    def __init__(self) -> None:
        self._entries: dict[str, PluginEntry] = {}
        self._instances: dict[str, PluginBase] = {}
        self._dm = DegradedMode.instancia()

    @property
    def entries(self) -> dict[str, PluginEntry]:
        """Metadatos de todos los plugins descubiertos (sin carga)."""
        return dict(self._entries)

    @property
    def loaded(self) -> list[str]:
        """Nombres de plugins que ya fueron cargados en memoria."""
        return list(self._instances.keys())

    # ── Descubrimiento (solo metadatos, sin importar) ──────────────────────

    def discover(self, paths: list[str | Path]) -> int:
        """Escanea rutas en busca de plugins.

        Lee solo metadatos vía AST (__plugin__ en cada .py).
        No importa ningún módulo — la carga es lazy.
        Retorna número de plugins descubiertos.
        """
        count = 0
        for path in paths:
            p = Path(path)
            if p.is_dir():
                count += self._discover_dir(p)
            elif p.is_file() and p.suffix == ".py":
                count += self._discover_file(p)
            else:
                log.warning("[plugin] Ruta no válida: %s", path)
        log.info("[plugin] Descubrimiento: %d plugins en %s", count, paths)
        return count

    def _discover_dir(self, directory: Path) -> int:
        count = 0
        for pyfile in sorted(directory.glob("*.py")):
            if pyfile.name.startswith("_"):
                continue
            meta = PluginMeta.from_file(pyfile)
            if meta is None:
                continue
            if meta.name in self._entries:
                log.warning("[plugin] Nombre duplicado: %s (sobrescribe)", meta.name)
            self._entries[meta.name] = PluginEntry(meta=meta, path=pyfile)
            count += 1
            log.debug("[plugin] Descubierto: %s (%s) desde %s", meta.name, meta.phase, pyfile.name)
        return count

    def _discover_file(self, pyfile: Path) -> int:
        meta = PluginMeta.from_file(pyfile)
        if meta is None:
            return 0
        if meta.name in self._entries:
            log.warning("[plugin] Nombre duplicado: %s (sobrescribe)", meta.name)
        self._entries[meta.name] = PluginEntry(meta=meta, path=pyfile)
        log.debug("[plugin] Descubierto: %s (%s) desde %s", meta.name, meta.phase, pyfile.name)
        return 1

    # ── Carga lazy ─────────────────────────────────────────────────────────

    def _load(self, name: str) -> PluginBase | None:
        """Importa e instancia un plugin por nombre.

        La instancia se cachea tras la primera carga exitosa.
        Si falla la carga, se registra en DegradedMode.
        """
        if name in self._instances:
            return self._instances[name]

        entry = self._entries.get(name)
        if entry is None:
            log.warning("[plugin] No encontrado: %s", name)
            return None

        try:
            module_name = f"_ura_plugin_{entry.path.stem}"
            spec = importlib.util.spec_from_file_location(module_name, entry.path)
            if spec is None or spec.loader is None:
                log.warning("[plugin] Spec inválido para %s", entry.path)
                self._dm.mark_degraded(f"plugin:{name}")
                return None

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            instance: PluginBase | None = None
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if isinstance(attr, type) and issubclass(attr, PluginBase) and attr is not PluginBase:
                    try:
                        instance = attr()
                        break
                    except Exception as exc:
                        log.warning("[plugin] Error instanciando %s: %s", name, exc)

            if instance is None:
                log.warning("[plugin] Sin subclase de PluginBase en %s", entry.path)
                self._dm.mark_degraded(f"plugin:{name}")
                return None

            self._instances[name] = instance
            self._dm.mark_healthy(f"plugin:{name}")
            log.info("[plugin] Cargado: %s", name)
            return instance

        except Exception as exc:
            log.warning("[plugin] Error cargando %s desde %s: %s", name, entry.path, exc)
            self._dm.mark_degraded(f"plugin:{name}")
            return None

    def get(self, name: str) -> PluginBase | None:
        """Retorna un plugin por nombre (carga lazy si es necesario)."""
        return self._load(name)

    def get_meta(self, name: str) -> PluginMeta | None:
        """Retorna metadatos sin cargar el plugin."""
        entry = self._entries.get(name)
        return entry.meta if entry else None

    # ── Ejecución ──────────────────────────────────────────────────────────

    def run_phase(
        self,
        phase: str,
        context: dict[str, Any] | None = None,
    ) -> list[PluginResult]:
        """Ejecuta todos los plugins de una fase.

        Cada plugin se carga bajo demanda (lazy).
        Si un plugin falla al cargarse o ejecutarse, los demás continúan.
        Los fallos se registran en DegradedMode.

        Retorna lista de PluginResult, uno por plugin de la fase.
        """
        context = context or {}
        results: list[PluginResult] = []

        phase_entries = [e for e in self._entries.values() if e.meta.phase in (phase, "always")]

        for entry in phase_entries:
            start = time.monotonic()
            name = entry.meta.name

            plugin = self._load(name)
            if plugin is None:
                elapsed = (time.monotonic() - start) * 1000
                log.warning("[plugin] %s no pudo cargarse — omitido", name)
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
                results.append(
                    PluginResult(
                        ok=True,
                        plugin=name,
                        phase=phase,
                        data=data,
                        duration_ms=elapsed,
                    ),
                )
                log.info("[plugin] %s ejecutado (%.0fms)", name, elapsed)
            except Exception as exc:
                elapsed = (time.monotonic() - start) * 1000
                log.warning("[plugin] %s falló (%.0fms): %s", name, elapsed, exc)
                self._dm.mark_degraded(f"plugin:{name}")
                results.append(
                    PluginResult(
                        ok=False,
                        plugin=name,
                        phase=phase,
                        error=str(exc),
                        duration_ms=elapsed,
                    ),
                )

        return results

    def run_one(
        self,
        name: str,
        context: dict[str, Any] | None = None,
    ) -> PluginResult | None:
        """Ejecuta un plugin específico por nombre (carga lazy)."""
        entry = self._entries.get(name)
        if entry is None:
            log.warning("[plugin] No encontrado: %s", name)
            return None
        results = self.run_phase(entry.meta.phase, context)
        for r in results:
            if r.plugin == name:
                return r
        return None

    def count(self) -> int:
        return len(self._entries)
