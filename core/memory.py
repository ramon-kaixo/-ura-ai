#!/usr/bin/env python3
"""
URA Memory Layer - Memoria persistente y contexto
"""

import sqlite3
import uuid
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import TypedDict


# ============================================================
# TIPOS DE MEMORIA
# ============================================================
class MemoryType(Enum):
    SHORT_TERM = "short_term"  # Contexto de conversación actual
    LONG_TERM = "long_term"  # Hechos importantes
    WORKING = "working"  # Memoria de trabajo activa
    EPISODIC = "episodic"  # Historial de interacciones


class MemoryEntry(TypedDict):
    id: str
    type: MemoryType
    key: str
    value: str
    agent: str
    trace_id: str
    created_at: str
    expires_at: str | None
    importance: int  # 1-10


# ============================================================
# MEMORY MANAGER
# ============================================================
class Memory:
    """Gestor de memoria persistente"""

    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = Path(__file__).parent.parent / "board.db"
        self.db_path = str(db_path)
        self._init_db()

    def _init_db(self):
        """Inicializar tablas de memoria"""
        conn = sqlite3.connect(self.db_path)

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS memory (
                id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                agent TEXT NOT NULL,
                trace_id TEXT,
                created_at TEXT NOT NULL,
                expires_at TEXT,
                importance INTEGER DEFAULT 5
            )
        """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_memory_type
            ON memory(type, created_at)
        """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_memory_key
            ON memory(key)
        """
        )

        conn.commit()
        conn.close()

    def store(
        self,
        memory_type: MemoryType,
        key: str,
        value: str,
        agent: str = "system",
        trace_id: str = None,
        importance: int = 5,
        ttl_seconds: int = None,
    ) -> str:
        """Almacenar en memoria"""
        entry_id = str(uuid.uuid4())
        now = datetime.now()

        expires_at = None
        if ttl_seconds:
            expires_at = (now + timedelta(seconds=ttl_seconds)).isoformat()

        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """
            INSERT INTO memory
            (id, type, key, value, agent, trace_id, created_at, expires_at, importance)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                entry_id,
                memory_type.value,
                key,
                value,
                agent,
                trace_id,
                now.isoformat(),
                expires_at,
                importance,
            ),
        )
        conn.commit()
        conn.close()

        return entry_id

    def retrieve(self, key: str, memory_type: MemoryType = None) -> dict | None:
        """Recuperar de memoria"""
        conn = sqlite3.connect(self.db_path)

        if memory_type:
            cursor = conn.execute(
                """
                SELECT id, type, key, value, agent, trace_id, created_at, importance
                FROM memory
                WHERE key = ? AND type = ? AND (expires_at IS NULL OR expires_at > ?)
                ORDER BY importance DESC, created_at DESC
                LIMIT 1
            """,
                (key, memory_type.value, datetime.now().isoformat()),
            )
        else:
            cursor = conn.execute(
                """
                SELECT id, type, key, value, agent, trace_id, created_at, importance
                FROM memory
                WHERE key = ? AND (expires_at IS NULL OR expires_at > ?)
                ORDER BY importance DESC, created_at DESC
                LIMIT 1
            """,
                (key, datetime.now().isoformat()),
            )

        row = cursor.fetchone()
        conn.close()

        if row:
            return {
                "id": row[0],
                "type": row[1],
                "key": row[2],
                "value": row[3],
                "agent": row[4],
                "trace_id": row[5],
                "created_at": row[6],
                "importance": row[7],
            }
        return None

    def get_context(self, agent: str = None, limit: int = 10) -> list:
        """Obtener contexto de conversación reciente"""
        conn = sqlite3.connect(self.db_path)

        if agent:
            cursor = conn.execute(
                """
                SELECT id, type, key, value, agent, created_at
                FROM memory
                WHERE type = ? AND agent = ?
                ORDER BY created_at DESC
                LIMIT ?
            """,
                (MemoryType.SHORT_TERM.value, agent, limit),
            )
        else:
            cursor = conn.execute(
                """
                SELECT id, type, key, value, agent, created_at
                FROM memory
                WHERE type = ?
                ORDER BY created_at DESC
                LIMIT ?
            """,
                (MemoryType.SHORT_TERM.value, limit),
            )

        results = []
        for row in cursor:
            results.append(
                {
                    "id": row[0],
                    "type": row[1],
                    "key": row[2],
                    "value": row[3],
                    "agent": row[4],
                    "created_at": row[5],
                }
            )

        conn.close()
        return results

    def get_important(self, limit: int = 20) -> list:
        """Obtener hechos importantes"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute(
            """
            SELECT id, type, key, value, agent, created_at, importance
            FROM memory
            WHERE importance >= 8
            ORDER BY importance DESC, created_at DESC
            LIMIT ?
        """,
            (limit,),
        )

        results = []
        for row in cursor:
            results.append(
                {
                    "id": row[0],
                    "type": row[1],
                    "key": row[2],
                    "value": row[3],
                    "agent": row[4],
                    "created_at": row[5],
                    "importance": row[6],
                }
            )

        conn.close()
        return results

    def cleanup(self):
        """Limpiar memoria expirada"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute(
            """
            DELETE FROM memory
            WHERE expires_at IS NOT NULL AND expires_at < ?
        """,
            (datetime.now().isoformat(),),
        )

        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        return deleted

    def store_conversation(
        self, agent: str, user_message: str, assistant_message: str, trace_id: str = None
    ):
        """Almacenar conversación"""
        # Mensaje usuario
        self.store(
            MemoryType.SHORT_TERM,
            key=f"user:{trace_id or uuid.uuid4()}",
            value=user_message,
            agent=agent,
            trace_id=trace_id,
            importance=5,
            ttl_seconds=3600,  # 1 hora
        )

        # Mensaje asistente
        self.store(
            MemoryType.SHORT_TERM,
            key=f"assistant:{trace_id or uuid.uuid4()}",
            value=assistant_message,
            agent=agent,
            trace_id=trace_id,
            importance=5,
            ttl_seconds=3600,
        )


# ============================================================
# EJEMPLO DE USO
# ============================================================
if __name__ == "__main__":
    print("=" * 40)
    print("URA Memory Layer - Test")
    print("=" * 40)

    memory = Memory()

    # Almacenar
    entry_id = memory.store(
        MemoryType.LONG_TERM, key="usuario_nombre", value="Ramón", agent="telegram", importance=9
    )
    print(f"✅ Almacenado: {entry_id}")

    # Recuperar
    result = memory.retrieve("usuario_nombre")
    print(f"📬 Recuperado: {result['value'] if result else 'None'}")

    # Contexto
    memory.store_conversation("telegram", "Hola", "Hola Ramón, ¿en qué puedo ayudarte?")
    contexto = memory.get_context("telegram", limit=5)
    print(f"📚 Contexto: {len(contexto)} entradas")

    # Importantes
    importantes = memory.get_important()
    print(f"⭐ Importantes: {len(importantes)} hechos")

    print("\n✅ Memory Layer OK")
