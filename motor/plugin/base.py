from __future__ import annotations

import ast
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path


@dataclass
class PluginMeta:
    """Metadatos declarativos de un plugin.

    Se declaran como variable __plugin__ a nivel de módulo en cada archivo
    de plugin:

        __plugin__ = {"name": "mi_plugin", "phase": "pre", "timeout": 30}
    """

    name: str
    phase: str = "always"
    blocking: bool = False
    timeout: int = 30
    description: str = ""

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> PluginMeta:
        return cls(
            name=str(d.get("name", "unknown")),
            phase=str(d.get("phase", "always")),
            blocking=bool(d.get("blocking", False)),
            timeout=int(d.get("timeout", 30)),
            description=str(d.get("description", "")),
        )

    @classmethod
    def from_source(cls, source: str) -> PluginMeta | None:
        """Extrae __plugin__ del source vía AST (sin importar el módulo)."""
        try:
            tree = ast.parse(source)
            for node in ast.iter_child_nodes(tree):
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name) and target.id == "__plugin__":
                            if isinstance(node.value, ast.Dict):
                                d = _ast_dict_to_dict(node.value)
                                return cls.from_dict(d)
                            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, dict):
                                return cls.from_dict(node.value.value)
        except SyntaxError:
            pass
        return None

    @classmethod
    def from_file(cls, path: Path) -> PluginMeta | None:
        """Lee __plugin__ del archivo sin importarlo."""
        try:
            source = path.read_text(encoding="utf-8")
            meta = cls.from_source(source)
            if meta is None:
                meta = PluginMeta(name=path.stem)
            return meta
        except Exception:
            return PluginMeta(name=path.stem)


def _ast_dict_to_dict(d: ast.Dict) -> dict[str, Any]:
    """Convierte un AST Dict literal a dict Python."""
    result: dict[str, Any] = {}
    for key_node, value_node in zip(d.keys, d.values, strict=False):
        if isinstance(key_node, (ast.Constant, ast.Str)):
            key = key_node.value if isinstance(key_node, ast.Constant) else key_node.s
            if not isinstance(key, str):
                continue
        else:
            continue
        if isinstance(value_node, ast.Constant):
            result[key] = value_node.value
        elif isinstance(value_node, ast.Str):
            result[key] = value_node.s
        elif isinstance(value_node, ast.List):
            result[key] = [elm.value for elm in value_node.elts if isinstance(elm, ast.Constant)]
        elif isinstance(value_node, ast.Dict):
            result[key] = _ast_dict_to_dict(value_node)
        elif isinstance(value_node, ast.Name):
            result[key] = value_node.id
        elif isinstance(value_node, ast.UnaryOp) and isinstance(value_node.op, ast.Not):
            # Handle `not True` → False
            if isinstance(value_node.operand, ast.Constant):
                result[key] = not value_node.operand.value
        elif isinstance(value_node, ast.Expression):
            result[key] = ast.literal_eval(value_node)
    return result


@dataclass
class PluginEntry:
    """Entrada en el registro: metadatos + path al archivo."""

    meta: PluginMeta
    path: Path


@dataclass
class PluginResult:
    """Resultado de la ejecución de un plugin."""

    ok: bool
    plugin: str
    phase: str
    data: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    duration_ms: float = 0.0


class PluginBase(ABC):
    """Clase base abstracta para todos los plugins.

    Cada plugin debe:
    1. Heredar de PluginBase
    2. Declarar __plugin__ a nivel de módulo con metadatos
    3. Implementar execute(context) -> dict
    """

    def __init__(self) -> None:
        self.meta = PluginMeta(name=self.__class__.__name__)

    @abstractmethod
    def execute(self, context: dict[str, Any] | None = None) -> dict[str, Any]:
        """Ejecuta la lógica del plugin. Retorna un dict con resultados."""

    def rollback(self, context: dict[str, Any] | None = None) -> None:  # noqa: B027  -- intencionadamente no abstracta, opcional
        """Llamado cuando un pipeline revierte tras una etapa fallida.
        Opcional — sobrescribir para limpiar recursos.
        """

    def __repr__(self) -> str:
        return f"<Plugin {self.meta.name}>"
