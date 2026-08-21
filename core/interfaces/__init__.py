"""Interfaces abstractas para inversión de dependencias core ↔ motor.

FACHADA (ADR-007): los contratos canónicos viven en motor/core/interfaces/.
Este paquete reexporta para preservar compatibilidad con `from core.interfaces
import ...`. No añadir definiciones nuevas aquí; hacerlo en motor/core/interfaces/.
"""

from motor.core.interfaces.config import IConfigProvider
from motor.core.interfaces.executor import IExecutor, IProcessResult
from motor.core.interfaces.llm import ILLMClient
from motor.core.interfaces.repository import IVectorStore
from motor.core.interfaces.secrets import ISecretStore

__all__ = [
    "IConfigProvider",
    "IExecutor",
    "ILLMClient",
    "IProcessResult",
    "ISecretStore",
    "IVectorStore",
]
