"""Memory — paquete de memoria semántica.

ExecutionLedger (raw events)
        ↓
LedgerIngester → SQLite (índices, migraciones)
        ↓
SemanticQueries (goal, plugin, date, decision)
"""

from scripts.pro.autonomy.memory.semantic_memory import SemanticMemory

__all__ = ["SemanticMemory"]
