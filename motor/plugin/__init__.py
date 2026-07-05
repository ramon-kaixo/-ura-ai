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
from motor.plugin.registry import PluginRegistry

__all__ = [
    "PluginBase",
    "PluginEntry",
    "PluginMeta",
    "PluginRegistry",
    "PluginResult",
]
