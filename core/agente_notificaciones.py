#!/usr/bin/env python3
"""
agente_notificaciones.py — URA Agente de Notificaciones y Alertas
================================================================
Sistema completo de notificaciones push y alertas.

Capacidades:
- Notificaciones del sistema (macOS)
- Alertas por nivel de severidad
- Cola de notificaciones pendientes
- Historial de alertas
- Configuración de umbrales

Niveles de severidad:
- INFO: Información general
- WARN: Advertencia
- ERROR: Error que requiere atención
- CRITICAL: Error crítico
"""

import sqlite3
from datetime import datetime, timedelta
from enum import IntEnum
from pathlib import Path


class Severidad(IntEnum):
    INFO = 1
    WARN = 2
    ERROR = 3
    CRITICAL = 4


class AgenteNotificaciones:
    def __init__(self, db_path: str | None = None):
        if db_path is None:
            db_path = str(Path(__file__).resolve().parents[1] / "board.db")
        self.db_path = db_path
        self._cola_pendientes: list[dict] = []
        self._init_db()

    def _init_db(self):
        """Inicializa la base de datos de notificaciones."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS notificaciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tipo TEXT NOT NULL,
                titulo TEXT NOT NULL,
                mensaje TEXT NOT NULL,
                severidad INTEGER DEFAULT 1,
                leida INTEGER DEFAULT 0,
                entregada INTEGER DEFAULT 0,
                creada_en TEXT NOT NULL,
                leida_en TEXT
            )
        """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS alertas_config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT UNIQUE NOT NULL,
                umbral REAL,
                duracion_minutos INTEGER,
                activa INTEGER DEFAULT 1
            )
        """
        )
        conn.commit()
        conn.close()

    def enviar(self, titulo: str, mensaje: str, severidad: int = 1, tipo: str = "sistema") -> int:
        """Envía una notificación. Retorna el ID."""
        ahora = datetime.now().isoformat()
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO notificaciones (tipo, titulo, mensaje, severidad, creada_en)
            VALUES (?, ?, ?, ?, ?)
        """,
            (tipo, titulo, mensaje, severidad, ahora),
        )
        result = cursor.lastrowid
        conn.commit()
        conn.close()

        self._cola_pendientes.append(
            {"id": result, "titulo": titulo, "mensaje": mensaje, "severidad": severidad}
        )
        return result

    def info(self, titulo: str, mensaje: str) -> int:
        """Notificación informativa."""
        return self.enviar(titulo, mensaje, Severidad.INFO)

    def warn(self, titulo: str, mensaje: str) -> int:
        """Notificación de advertencia."""
        return self.enviar(titulo, mensaje, Severidad.WARN)

    def error(self, titulo: str, mensaje: str) -> int:
        """Notificación de error."""
        return self.enviar(titulo, mensaje, Severidad.ERROR)

    def critical(self, titulo: str, mensaje: str) -> int:
        """Notificación crítica."""
        return self.enviar(titulo, mensaje, Severidad.CRITICAL)

    def obtener_pendientes(self, no_leidas: bool = True, limite: int = 20) -> list[dict]:
        """Obtiene notificaciones pendientes."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        query = """
            SELECT id, tipo, titulo, mensaje, severidad, leida, creada_en
            FROM notificaciones
        """
        if no_leidas:
            query += " WHERE leida = 0"
        query += " ORDER BY severidad DESC, creada_en DESC LIMIT ?"
        cursor.execute(query, (limite,))
        rows = cursor.fetchall()
        conn.close()
        return [
            {
                "id": r[0],
                "tipo": r[1],
                "titulo": r[2],
                "mensaje": r[3],
                "severidad": r[4],
                "leida": bool(r[5]),
                "creada": r[6],
            }
            for r in rows
        ]

    def marcar_leida(self, notificacion_id: int) -> bool:
        """Marca una notificación como leída."""
        ahora = datetime.now().isoformat()
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE notificaciones SET leida = 1, leida_en = ?
            WHERE id = ?
        """,
            (ahora, notificacion_id),
        )
        conn.commit()
        result = cursor.rowcount > 0
        conn.close()
        return result

    def marcar_todas_leidas(self) -> int:
        """Marca todas las notificaciones como leídas."""
        ahora = datetime.now().isoformat()
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE notificaciones SET leida = 1, leida_en = ? WHERE leida = 0", (ahora,)
        )
        conn.commit()
        result = cursor.rowcount
        conn.close()
        return result

    def contar_pendientes(self, min_severidad: int = 1) -> int:
        """Cuenta notificaciones pendientes."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT COUNT(*) FROM notificaciones
            WHERE leida = 0 AND severidad >= ?
        """,
            (min_severidad,),
        )
        result = cursor.fetchone()[0]
        conn.close()
        return result

    def historial(self, dias: int = 7, limite: int = 50) -> list[dict]:
        """Obtiene historial de notificaciones."""
        cutoff = (datetime.now() - timedelta(days=dias)).isoformat()
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, tipo, titulo, mensaje, severidad, leida, creada_en, leida_en
            FROM notificaciones
            WHERE creada_en >= ?
            ORDER BY creada_en DESC
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
                "titulo": r[2],
                "mensaje": r[3],
                "severidad": r[4],
                "leida": bool(r[5]),
                "creada": r[6],
                "leida_en": r[7],
            }
            for r in rows
        ]

    def limpiar(self, dias: int = 30) -> int:
        """Elimina notificaciones antiguas."""
        cutoff = (datetime.now() - timedelta(days=dias)).isoformat()
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM notificaciones WHERE leida = 1 AND leida_en < ?", (cutoff,))
        conn.commit()
        result = cursor.rowcount
        conn.close()
        return result

    def stats(self) -> dict:
        """Estadísticas de notificaciones."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM notificaciones WHERE leida = 0")
        pendientes = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM notificaciones WHERE leida = 1")
        leidas = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM notificaciones WHERE severidad >= 3")
        errores = cursor.fetchone()[0]
        cursor.execute(
            """
            SELECT COUNT(*) FROM notificaciones
            WHERE leida = 0 AND created_at > ?
        """,
            ((datetime.now() - timedelta(hours=24)).isoformat(),),
        )
        ultimas_24h = cursor.fetchone()[0]
        conn.close()
        return {
            "pendientes": pendientes,
            "leidas": leidas,
            "errores": errores,
            "ultimas_24h": ultimas_24h,
        }

    def procesar(self, texto: str) -> str:
        """Procesar consulta para AgenteNotificaciones."""
        texto.lower()
        return "Puedo enviar alertas, avisos y notificaciones push. ¿Qué notificación necesitas?"

    def ejecutar(self, texto: str) -> str:
        """Ejecutar acción para AgenteNotificaciones."""
        return self.procesar(texto)

    def consultar(self, texto: str) -> str:
        """Consultar información para AgenteNotificaciones."""
        return self.procesar(texto)

    def responder(self, texto: str) -> str:
        """Responder pregunta para AgenteNotificaciones."""
        return self.procesar(texto)

    def execute(self, *args, **kwargs) -> dict:
        """
        Método execute estándar para AgenteNotificaciones.

        Args:
            *args: Argumentos posicionales
            **kwargs: Argumentos clave

        Returns:
            Dict con {"success": bool, "response": str, "error": str}
        """
        try:
            texto = args[0] if args else kwargs.get("texto", "")
            if not texto:
                return {"success": False, "response": "", "error": "No se proporcionó texto"}

            response = self.procesar(texto)
            return {"success": True, "response": response, "error": ""}
        except Exception as e:
            return {"success": False, "response": "", "error": str(e)}


_NOTIFICACIONES = None


def get_notificaciones() -> AgenteNotificaciones:
    global _NOTIFICACIONES
    if _NOTIFICACIONES is None:
        _NOTIFICACIONES = AgenteNotificaciones()
    return _NOTIFICACIONES
