"""Interfaces abstractas para inversión de dependencias core ↔ motor.

FACHADA (ADR-007): los contratos canónicos viven en motor/core/interfaces/.
Este paquete reexporta para preservar compatibilidad con `from core.interfaces
import ...`. No añadir definiciones nuevas aquí; hacerlo en motor/core/interfaces/.
"""

from motor.core.interfaces.config import IConfigProvider  # noqa: F401
from motor.core.interfaces.executor import IExecutor, IProcessResult  # noqa: F401
from motor.core.interfaces.llm import ILLMClient  # noqa: F401
from motor.core.interfaces.repository import IVectorStore  # noqa: F401
from motor.core.interfaces.secrets import ISecretStore  # noqa: F401
