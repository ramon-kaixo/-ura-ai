"""Plugin system — carga dinámica de plugins via importlib.

Registro dinámico con:
- Descubrimiento por AST (sin importar)
- Carga lazy (solo cuando se necesita)
- Aislamiento de fallos (un plugin caído no afecta al resto)
- Integración con DegradedMode para visibilidad operativa

Uso:
    registry = PluginRegistry()
    registry.discover(["scripts/pro/plugins"])
    results = registry.run_phase("pre", {"dry_run": True})
"""

from motor.plugin.base import PluginBase, PluginEntry, PluginMeta, PluginResult
from motor.plugin.manifest import ManifestError, PluginManifest, find_manifest, parse_manifest
from motor.plugin.registry import PluginRegistry
from motor.plugin.registry_v2 import PluginEntryV2, PluginRegistryV2

__all__ = [
    "ManifestError",
    "PluginBase",
    "PluginEntry",
    "PluginEntryV2",
    "PluginManifest",
    "PluginMeta",
    "PluginRegistry",
    "PluginRegistryV2",
    "PluginResult",
    "find_manifest",
    "parse_manifest",
]
