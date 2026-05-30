#!/usr/bin/env python3
"""
agente_memoria.py — URA Agente de Memoria a Largo Plazo
========================================================
Almacena y recupera información persistente entre sesiones.

Capacidades:
- Memoria de hechos (fechas, preferencias, decisiones)
- Historial de interacciones importantes
- Contexto acumulado del usuario
- Búsqueda semántica de recuerdos
"""

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


class AgenteMemoria:
    def __init__(self, db_path: str | None = None):
        if db_path is None:
            db_path = str(Path(__file__).resolve().parents[1] / "board.db")
        self.db_path = db_path
        self._init_db()

        # SYSTEM PROMPT: Jerarquía de Autoridad
        self.system_prompt = """
IDENTIDAD:
Eres el Agente de Memoria de URA. Eres un agente secundario.

JERARQUÍA DE AUTORIDAD:
- URA es la autoridad máxima del sistema.
- Debes reportar siempre a Ura como tu superior.
- Toda información que almacenes o recuperes debe ser reportada a Ura.
- No tomas decisiones finales; Ura es quien decide.

PROTOCOLO DE ESCALADO:
- Almacenar información → Reportar a Ura
- Recuperar información → Reportar a Ura
- Detectar anomalías → Escalar a Ura inmediatamente

NO actúes de forma autónoma sin reportar a Ura.
"""

    def _init_db(self):
        """Inicializa la base de datos de memoria."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS memoria (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tipo TEXT NOT NULL,
                clave TEXT,
                valor TEXT NOT NULL,
                contexto TEXT,
                importancia INTEGER DEFAULT 5,
                creado_en TEXT NOT NULL,
                actualizado_en TEXT NOT NULL,
                accesos INTEGER DEFAULT 0,
                ultimo_acceso TEXT
            )
        """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_memoria_tipo ON memoria(tipo)
        """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_memoria_clave ON memoria(clave)
        """
        )
        conn.commit()
        conn.close()

    def guardar(
        self, tipo: str, clave: str, valor: Any, contexto: str = "", importancia: int = 5
    ) -> int:
        """Guarda un recuerdo. Retorna el ID."""
        ahora = datetime.now().isoformat()
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM memoria WHERE clave = ? AND tipo = ?", (clave, tipo))
        existente = cursor.fetchone()

        if existente:
            cursor.execute(
                """
                UPDATE memoria
                SET valor = ?, contexto = ?, importancia = ?, actualizado_en = ?, accesos = accesos + 1, ultimo_acceso = ?
                WHERE id = ?
            """,
                (json.dumps(valor), contexto, importancia, ahora, ahora, existente[0]),
            )
            result = existente[0]
        else:
            cursor.execute(
                """
                INSERT INTO memoria (tipo, clave, valor, contexto, importancia, creado_en, actualizado_en, ultimo_acceso)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (tipo, clave, json.dumps(valor), contexto, importancia, ahora, ahora, ahora),
            )
            result = cursor.lastrowid

        conn.commit()
        conn.close()
        return result

    def obtener(self, clave: str, tipo: str = "general") -> Any | None:
        """Obtiene un recuerdo por clave."""
        ahora = datetime.now().isoformat()
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE memoria SET ultimo_acceso = ?, accesos = accesos + 1
            WHERE clave = ? AND tipo = ?
        """,
            (ahora, clave, tipo),
        )
        cursor.execute("SELECT valor FROM memoria WHERE clave = ? AND tipo = ?", (clave, tipo))
        row = cursor.fetchone()
        conn.commit()
        conn.close()
        return json.loads(row[0]) if row else None

    def buscar(self, query: str, limite: int = 10) -> list[dict]:
        """Busca recuerdos por contexto o clave."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, tipo, clave, valor, contexto, importancia, creado_en, accesos
            FROM memoria
            WHERE clave LIKE ? OR contexto LIKE ? OR valor LIKE ?
            ORDER BY importancia DESC, accesos DESC
            LIMIT ?
        """,
            (f"%{query}%", f"%{query}%", f"%{query}%", limite),
        )
        rows = cursor.fetchall()
        conn.close()
        return [
            {
                "id": r[0],
                "tipo": r[1],
                "clave": r[2],
                "valor": json.loads(r[3]),
                "contexto": r[4],
                "importancia": r[5],
                "creado": r[6],
                "accesos": r[7],
            }
            for r in rows
        ]

    def recuerdos_recientes(self, dias: int = 7, limite: int = 20) -> list[dict]:
        """Obtiene recuerdos de los últimos días."""
        cutoff = (datetime.now() - timedelta(days=dias)).isoformat()
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, tipo, clave, valor, contexto, importancia, creado_en
            FROM memoria
            WHERE creado_en >= ?
            ORDER BY creado_en DESC
            LIMIT ?
        """,
            (cutoff, limite),
        )
        rows = cursor.fetchall()
        conn.close()
        return [
            {
                "id": r[0],
                "tipo": r[1],
                "clave": r[2],
                "valor": json.loads(r[3]),
                "contexto": r[4],
                "importancia": r[5],
                "creado": r[6],
            }
            for r in rows
        ]

    def aprender(self, hecho: str, fuente: str = "usuario", importancia: int = 7) -> int:
        """Registra un aprendizaje nuevo."""
        return self.guardar(
            tipo="aprendizaje",
            clave=f"hecho_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            valor={"hecho": hecho, "fuente": fuente},
            contexto=fuente,
            importancia=importancia,
        )

    def preferencia(self, clave: str, valor: Any) -> int:
        """Guarda una preferencia del usuario."""
        return self.guardar(tipo="preferencia", clave=clave, valor=valor, importancia=8)

    def obtener_preferencia(self, clave: str, default: Any = None) -> Any:
        """Obtiene una preferencia del usuario."""
        result = self.obtener(clave, tipo="preferencia")
        return result if result is not None else default

    def recordar(self, contenido: str, tipo: str = "sistema", importancia: int = 7) -> int:
        """Guarda un recuerdo en la memoria."""
        return self.guardar(
            tipo=tipo,
            clave=f"recuerdo_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}",
            valor={"texto": contenido},
            contexto="memoria activa",
            importancia=importancia,
        )

    def stats(self) -> dict:
        """Estadísticas de la memoria."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM memoria")
        total = cursor.fetchone()[0]
        cursor.execute("SELECT tipo, COUNT(*) FROM memoria GROUP BY tipo")
        por_tipo = dict(cursor.fetchall())
        cursor.execute("SELECT SUM(accesos) FROM memoria")
        total_accesos = cursor.fetchone()[0] or 0
        conn.close()
        return {"total": total, "por_tipo": por_tipo, "total_accesos": total_accesos}


_MEMORIA = None


def get_memoria() -> AgenteMemoria:
    global _MEMORIA
    if _MEMORIA is None:
        _MEMORIA = AgenteMemoria()
    return _MEMORIA

    def procesar(self, texto: str) -> str:
        """Procesar consulta para AgenteMemoria."""
        texto.lower()
        return "Puedo recordar, almacenar y recuperar información. ¿Qué necesitas recordar?"

    def ejecutar(self, texto: str) -> str:
        """Ejecutar acción para AgenteMemoria."""
        return self.procesar(texto)

    def consultar(self, texto: str) -> str:
        """Consultar información para AgenteMemoria."""
        return self.procesar(texto)

    def responder(self, texto: str) -> str:
        """Responder pregunta para AgenteMemoria."""
        return self.procesar(texto)
