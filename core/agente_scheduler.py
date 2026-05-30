#!/usr/bin/env python3
"""
agente_scheduler.py — URA Agente de Tareas Programadas
======================================================
Permite programar tareas para ejecutarse en horarios específicos.

Capacidades:
- Programar tareas únicas o recurrentes
- Soporte para expresiones cron simples
- Notificaciones antes de ejecutar
- Historial de ejecuciones

Ejemplos de uso:
    scheduler = get_scheduler()
    scheduler.programar("diario", "08:00", "Resumen del día", "resumen:diario")
    scheduler.programar("semanal", "lunes 09:00", "Reunión de equipo", "reunion:equipo")
"""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path


class AgenteScheduler:
    DIAS_SEMANA = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]

    def __init__(self, db_path: str | None = None):
        if db_path is None:
            db_path = str(Path(__file__).resolve().parents[1] / "board.db")
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Inicializa la base de datos del scheduler."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS tareas_programadas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                comando TEXT,
                tipo_tarea TEXT NOT NULL,
                frecuencia TEXT NOT NULL,
                hora TEXT NOT NULL,
                dia_semana TEXT,
                activa INTEGER DEFAULT 1,
                ultima_ejecucion TEXT,
                proxima_ejecucion TEXT,
                created_at TEXT NOT NULL
            )
        """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS scheduler_historial (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tarea_id INTEGER,
                ejecutada_en TEXT NOT NULL,
                resultado TEXT,
                FOREIGN KEY (tarea_id) REFERENCES tareas_programadas(id)
            )
        """
        )
        conn.commit()
        conn.close()

    def programar(
        self,
        frecuencia: str,
        hora: str,
        nombre: str,
        comando: str = "",
        dia_semana: str | None = None,
    ) -> int:
        """
        Programa una tarea.
        frecuencia: 'unica', 'diaria', 'semanal', 'mensual'
        hora: 'HH:MM' formato 24h
        dia_semana: 'lunes' a 'domingo' (solo para semanal)
        """
        ahora = datetime.now()
        proxima = self._calcular_proxima_ejecucion(frecuencia, hora, dia_semana)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO tareas_programadas
            (nombre, comando, tipo_tarea, frecuencia, hora, dia_semana, activa, proxima_ejecucion, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)
        """,
            (
                nombre,
                comando,
                frecuencia,
                frecuencia,
                hora,
                dia_semana,
                proxima.isoformat(),
                ahora.isoformat(),
            ),
        )
        result = cursor.lastrowid
        conn.commit()
        conn.close()
        return result

    def _calcular_proxima_ejecucion(
        self, frecuencia: str, hora: str, dia_semana: str | None = None
    ) -> datetime:
        """Calcula la próxima fecha de ejecución."""
        ahora = datetime.now()
        h, m = map(int, hora.split(":"))
        proxima = ahora.replace(hour=h, minute=m, second=0, microsecond=0)

        if frecuencia == "unica":
            return proxima
        elif frecuencia == "diaria":
            if proxima <= ahora:
                proxima += timedelta(days=1)
            return proxima
        elif frecuencia == "semanal":
            if dia_semana:
                dia_idx = self.DIAS_SEMANA.index(dia_semana.lower())
                dias_hasta = (dia_idx - proxima.weekday()) % 7
                if dias_hasta == 0 and proxima <= ahora:
                    dias_hasta = 7
                proxima += timedelta(days=dias_hasta)
            elif proxima <= ahora:
                proxima += timedelta(days=1)
            return proxima
        elif frecuencia == "mensual":
            if proxima <= ahora:
                if proxima.month == 12:
                    proxima = proxima.replace(year=proxima.year + 1, month=1)
                else:
                    proxima = proxima.replace(month=proxima.month + 1)
            return proxima
        return proxima + timedelta(days=1)

    def tareas_pendientes(self) -> list[dict]:
        """Retorna las tareas que deben ejecutarse ahora."""
        ahora = datetime.now()
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, nombre, comando, frecuencia, hora, dia_semana, ultima_ejecucion
            FROM tareas_programadas
            WHERE activa = 1 AND proxima_ejecucion <= ?
        """,
            (ahora.isoformat(),),
        )
        rows = cursor.fetchall()
        conn.close()
        return [
            {
                "id": r[0],
                "nombre": r[1],
                "comando": r[2],
                "frecuencia": r[3],
                "hora": r[4],
                "dia_semana": r[5],
                "ultima_ejecucion": r[6],
            }
            for r in rows
        ]

    def ejecutar_tarea(self, tarea_id: int) -> bool:
        """Marca una tarea como ejecutada y calcula la siguiente."""
        ahora = datetime.now()
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT frecuencia, hora, dia_semana FROM tareas_programadas WHERE id = ?", (tarea_id,)
        )
        row = cursor.fetchone()
        if not row:
            conn.close()
            return False

        frecuencia, hora, dia_semana = row
        proxima = self._calcular_proxima_ejecucion(frecuencia, hora, dia_semana)

        cursor.execute(
            """
            UPDATE tareas_programadas
            SET ultima_ejecucion = ?, proxima_ejecucion = ?
            WHERE id = ?
        """,
            (ahora.isoformat(), proxima.isoformat(), tarea_id),
        )

        cursor.execute(
            """
            INSERT INTO scheduler_historial (tarea_id, ejecutada_en)
            VALUES (?, ?)
        """,
            (tarea_id, ahora.isoformat()),
        )

        conn.commit()
        conn.close()
        return True

    def cancelar(self, tarea_id: int) -> bool:
        """Desactiva una tarea programada."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("UPDATE tareas_programadas SET activa = 0 WHERE id = ?", (tarea_id,))
        conn.commit()
        result = cursor.rowcount > 0
        conn.close()
        return result

    def listar(self, solo_activas: bool = True) -> list[dict]:
        """Lista todas las tareas programadas."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        query = "SELECT id, nombre, comando, frecuencia, hora, dia_semana, activa, proxima_ejecucion FROM tareas_programadas"
        if solo_activas:
            query += " WHERE activa = 1"
        cursor.execute(query)
        rows = cursor.fetchall()
        conn.close()
        return [
            {
                "id": r[0],
                "nombre": r[1],
                "comando": r[2],
                "frecuencia": r[3],
                "hora": r[4],
                "dia_semana": r[5],
                "activa": bool(r[6]),
                "proxima": r[7],
            }
            for r in rows
        ]

    def proximas_ejecuciones(self, limite: int = 10) -> list[dict]:
        """Muestra las próximas ejecuciones programadas."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, nombre, frecuencia, hora, dia_semana, proxima_ejecucion
            FROM tareas_programadas
            WHERE activa = 1
            ORDER BY proxima_ejecucion ASC
            LIMIT ?
        """,
            (limite,),
        )
        rows = cursor.fetchall()
        conn.close()
        return [
            {
                "id": r[0],
                "nombre": r[1],
                "frecuencia": r[2],
                "hora": r[3],
                "dia_semana": r[4],
                "proxima": r[5],
            }
            for r in rows
        ]


_SCHEDULER = None


def get_scheduler() -> AgenteScheduler:
    global _SCHEDULER
    if _SCHEDULER is None:
        _SCHEDULER = AgenteScheduler()
    return _SCHEDULER

    def procesar(self, texto: str) -> str:
        """Procesar consulta para AgenteScheduler."""
        texto.lower()
        return (
            "Puedo programar tareas, cron, recordatorios y agendas. ¿Qué tarea quieres programar?"
        )

    def ejecutar(self, texto: str) -> str:
        """Ejecutar acción para AgenteScheduler."""
        return self.procesar(texto)

    def consultar(self, texto: str) -> str:
        """Consultar información para AgenteScheduler."""
        return self.procesar(texto)

    def responder(self, texto: str) -> str:
        """Responder pregunta para AgenteScheduler."""
        return self.procesar(texto)

    def execute(self, *args, **kwargs) -> dict:
        """
        Método execute estándar para AgenteScheduler.

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
