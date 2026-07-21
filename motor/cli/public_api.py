"""Fachada pública para scripts — punto de acceso único al motor.

POLÍTICA:
- Destinada EXCLUSIVAMENTE al flujo principal del producto.
- Los scripts NUEVOS del flujo principal solo importan de aquí.
- Scripts existentes del flujo principal migran gradualmente.
- Benchmarks, herramientas internas y utilidades de desarrollo
  pueden importar directamente APIs internas cuando necesiten
  capacidades no expuestas por la fachada.
- NO ampliar la fachada únicamente para cubrir scripts auxiliares.
- Cualquier nueva exportación debe estar justificada por una
  necesidad del producto, no por conveniencia de herramientas
  de desarrollo.

Uso:
    from motor.cli.public_api import UraConfig, QdrantClient, get_secret
"""

# Core
from motor.core.config import UraConfig
from motor.core.executor import SubprocessExecutor
from motor.core.qdrant_client import QdrantClient
from motor.core.secrets import get_secret, has_secret, list_available, require_secret
from motor.core.state import DegradedMode

# Events
from motor.events import EventBus
from motor.events.topics import SYSTEM_STARTED

# Intelligence — memory
from motor.intelligence.memory import Episode, EpisodeStore, EpisodeStoreConfig

# Intelligence — retrieval
from motor.intelligence.retrieval.hybrid import HybridRetriever
from motor.intelligence.retrieval.lexical import LexicalRetriever
from motor.intelligence.retrieval.vector import VectorRetriever

# Observability
from motor.observability import MetricsRegistry, format_prometheus
from motor.observability.health import HealthRegistry

__all__ = [
    "SYSTEM_STARTED",
    "DegradedMode",
    "Episode",
    "EpisodeStore",
    "EpisodeStoreConfig",
    "EventBus",
    "HealthRegistry",
    "HybridRetriever",
    "LexicalRetriever",
    "MetricsRegistry",
    "QdrantClient",
    "SubprocessExecutor",
    "UraConfig",
    "VectorRetriever",
    "format_prometheus",
    "get_secret",
    "has_secret",
    "list_available",
    "require_secret",
]
