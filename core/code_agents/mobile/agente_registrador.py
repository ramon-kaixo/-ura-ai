#!/usr/bin/env python3
"""
Módulo: core/code_agents/mobile/agente_registrador.py
Propósito: Registro SQLite de agentes móviles: historial de ejecuciones, versiones y metadatos.
Dependencias principales: sqlite3, json, datetime, pathlib
Reglas especiales: Usar context managers para todas las conexiones SQLite. Nunca dejar conexiones abiertas.
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path


class AgenteRegistrador:
    """Registra acciones de agentes móviles"""

    def __init__(self):
        self.nombre = "agente_registrador"
        self.box_actual = None
        self.db_path = Path("/Users/ramonesnaola/URA/ura_ia_1972/board.db")
        self._init_db()

    def asignar_box(self, box: str):
        """Asignar agente a un box específico"""
        self.box_actual = box

    def _init_db(self):
        """Inicializar base de datos de registro"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        c.execute(
            """
            CREATE TABLE IF NOT EXISTS log_agentes_moviles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agente TEXT NOT NULL,
                accion TEXT NOT NULL,
                box TEXT,
                detalles TEXT,
                timestamp TEXT NOT NULL
            )
        """
        )

        conn.commit()
        conn.close()

    def registrar(self, agente: str, accion: str, detalles: dict = None) -> int:
        """Registrar acción de un agente"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        c.execute(
            """
            INSERT INTO log_agentes_moviles (agente, accion, box, detalles, timestamp)
            VALUES (?, ?, ?, ?, ?)
        """,
            (
                agente,
                accion,
                self.box_actual,
                json.dumps(detalles) if detalles else None,
                datetime.now().isoformat(),
            ),
        )

        result = c.lastrowid
        conn.commit()
        conn.close()

        return result

    def obtener_historial(self, agente: str = None, limite: int = 50) -> list[dict]:
        """Obtener historial de registros"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        if agente:
            c.execute(
                """
                SELECT id, agente, accion, box, detalles, timestamp
                FROM log_agentes_moviles
                WHERE agente = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """,
                (agente, limite),
            )
        else:
            c.execute(
                """
                SELECT id, agente, accion, box, detalles, timestamp
                FROM log_agentes_moviles
                ORDER BY timestamp DESC
                LIMIT ?
            """,
                (limite,),
            )

        rows = c.fetchall()
        conn.close()

        return [
            {
                "id": r[0],
                "agente": r[1],
                "accion": r[2],
                "box": r[3],
                "detalles": json.loads(r[4]) if r[4] else None,
                "timestamp": r[5],
            }
            for r in rows
        ]


# Instancia global
agente_registrador = AgenteRegistrador()
