"""Interfaces abstractas para inversión de dependencias core ↔ motor.

Contratos en core/ que motor implementa. Permite que core dependa de
abstracciones en lugar de implementaciones concretas del motor.
"""

from core.interfaces.config import IConfigProvider  # noqa: F401
from core.interfaces.executor import IExecutor, IProcessResult  # noqa: F401
from core.interfaces.llm import ILLMClient  # noqa: F401
from core.interfaces.repository import IVectorStore  # noqa: F401
from core.interfaces.secrets import ISecretStore  # noqa: F401
