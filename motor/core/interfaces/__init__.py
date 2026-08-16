"""Interfaces abstractas para inversión de dependencias core ↔ motor.

Contratos canónicos que viven en motor/ (capa inferior) y que core/ reexporta
como fachada. Permite que core dependa de abstracciones sin que motor tenga
que importar de core (rompe la dependencia circular).

Ver: docs/architecture/ADR-007-REGLA_NUCLEO.md
"""

from motor.core.interfaces.config import IConfigProvider  # noqa: F401
from motor.core.interfaces.executor import IExecutor, IProcessResult  # noqa: F401
from motor.core.interfaces.llm import ILLMClient  # noqa: F401
from motor.core.interfaces.repository import IVectorStore  # noqa: F401
from motor.core.interfaces.secrets import ISecretStore  # noqa: F401
