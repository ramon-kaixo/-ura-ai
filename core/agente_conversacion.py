#!/usr/bin/env python3
"""
agente_conversacion.py — URA Agente de Conversaciones Proactivas
================================================================
URA inicia conversaciones contigo proactivamente.

Capacidades:
- Mensajes programados según contexto
- Resúmenes periódicos
- Alertas proactivas
- Recordatorios inteligentes
- Aprendizaje de preferencias de comunicación

Tipos de conversación:
- resumen: Resumen periódico
- alerta: Alerta sobre algo importante
- recordatorio: Recordatorio de tarea
- saludo: Saludo contextual
- consejo: Sugerencia basada en patrones
"""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path


class AgenteConversacion:
    TIPOS = ["resumen", "alerta", "recordatorio", "saludo", "consejo", "info"]

    def __init__(self, db_path: str | None = None):
        if db_path is None:
            db_path = str(Path(__file__).resolve().parents[1] / "board.db")
        self.db_path = db_path
        self._ultima_conversacion: datetime | None = None
        self._cola_mensajes: list[dict] = []
        self._init_db()

    def _init_db(self):
        """Inicializa la base de datos de conversaciones."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS conversaciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tipo TEXT NOT NULL,
                titulo TEXT,
                mensaje TEXT NOT NULL,
                iniciado_por TEXT DEFAULT 'ura',
                entregado INTEGER DEFAULT 0,
                interactuado INTEGER DEFAULT 0,
                creado_en TEXT NOT NULL,
                entregado_en TEXT
            )
        """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS plantillas_conversacion (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT UNIQUE NOT NULL,
                tipo TEXT NOT NULL,
                plantilla TEXT NOT NULL,
                activa INTEGER DEFAULT 1,
                prioridad INTEGER DEFAULT 5
            )
        """
        )
        conn.commit()

        cursor.execute("SELECT COUNT(*) FROM plantillas_conversacion")
        if cursor.fetchone()[0] == 0:
            self._crear_plantillas_default(cursor)

        conn.close()

    def _crear_plantillas_default(self, cursor):
        """Crea plantillas de conversación por defecto."""
        plantillas = [
            (
                "saludo_manana",
                "saludo",
                "Buenos días! Soy URA, tu asistente de automatización. ¿En qué puedo ayudarte hoy?",
            ),
            (
                "saludo_tarde",
                "saludo",
                "Buenas tardes! Tengo algunas tareas pendientes que podrían necesitar atención.",
            ),
            (
                "resumen_diario",
                "resumen",
                "Resumen del día: {tareas_completadas} tareas completadas, {tareas_pendientes} pendientes.",
            ),
            (
                "alerta_tarea_antigua",
                "alerta",
                "Hay una tarea sin actualizar desde hace {dias} días: {tarea_nombre}",
            ),
            (
                "consejo_eficiencia",
                "consejo",
                "Consejo: Puedo automatizar tareas repetitivas. ¿Quieres que revise las últimas 10 tareas?",
            ),
            (
                "info_estado",
                "info",
                "Estado del sistema: Ollama {ollama_status}, {tareas_activas} tareas activas.",
            ),
        ]
        cursor.executemany(
            """
            INSERT INTO plantillas_conversacion (nombre, tipo, plantilla, prioridad)
            VALUES (?, ?, ?, ?)
        """,
            [(p[0], p[1], p[2], i) for i, p in enumerate(plantillas, 1)],
        )

    def iniciar(self, tipo: str, mensaje: str, titulo: str = "") -> int:
        """Inicia una conversación. Retorna el ID."""
        ahora = datetime.now().isoformat()
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO conversaciones (tipo, titulo, mensaje, creado_en)
            VALUES (?, ?, ?, ?)
        """,
            (tipo, titulo or tipo, mensaje, ahora),
        )
        result = cursor.lastrowid
        conn.commit()
        conn.close()

        self._cola_mensajes.append(
            {"id": result, "tipo": tipo, "titulo": titulo, "mensaje": mensaje}
        )
        self._ultima_conversacion = datetime.now()
        return result

    def saludo(self) -> int:
        """Genera un saludo contextual."""
        ahora = datetime.now()
        hora = ahora.hour
        if hora < 12:
            tipo = "saludo_manana"
            mensaje = (
                "Buenos días! Soy URA, tu asistente de automatización. ¿En qué puedo ayudarte hoy?"
            )
        elif hora < 18:
            tipo = "saludo_tarde"
            mensaje = (
                "Buenas tardes! Tengo algunas tareas pendientes que podrían necesitar atención."
            )
        else:
            tipo = "saludo_noche"
            mensaje = "Buenas noches! El sistema está funcionando correctamente. ¿Necesitas algo antes de descansar?"
        return self.iniciar("saludo", mensaje, tipo)

    def resumen_periodico(self) -> int:
        """Genera un resumen del estado actual."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT COUNT(*) FROM tasks WHERE estado = 'hecho' AND fecha_fin >= ?",
            ((datetime.now() - timedelta(days=1)).isoformat(),),
        )
        completadas = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM tasks WHERE estado = 'pendiente'")
        pendientes = cursor.fetchone()[0]

        cursor.execute(
            "SELECT titulo FROM tasks WHERE estado = 'pendiente' ORDER BY fecha_creacion LIMIT 3"
        )
        tareas_urgentes = [r[0] for r in cursor.fetchall()]

        conn.close()

        mensaje = "Resumen:\n"
        mensaje += f"- {completadas} tareas completadas hoy\n"
        mensaje += f"- {pendientes} tareas pendientes\n"
        if tareas_urgentes:
            mensaje += f"- Urgentes: {', '.join(tareas_urgentes[:3])}"

        return self.iniciar("resumen", mensaje, "Resumen periódico")

    def alerta_tarea(self, tarea_nombre: str, dias: int) -> int:
        """Alerta sobre una tarea antigua."""
        mensaje = f"Hay una tarea sin actualizar desde hace {dias} días: {tarea_nombre}"
        return self.iniciar("alerta", mensaje, f"Tarea antigua: {tarea_nombre}")

    def consejo(self) -> int:
        """Ofrece un consejo basado en patrones."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT tipo, COUNT(*) FROM tasks
            WHERE fecha_creacion >= ?
            GROUP BY tipo
            LIMIT 1
            """,
            ((datetime.now() - timedelta(days=7)).isoformat(),),
        )
        row = cursor.fetchone()
        tipo_comun = row[0] if row else "general"

        cursor.execute("SELECT COUNT(*) FROM tasks WHERE estado = 'pendiente' AND reintentos > 2")
        tareas_fallidas = cursor.fetchone()[0]

        conn.close()

        if nombre.startswith("agente_"):
            self._registro[nombre]["estado"] = "activo"
            mensaje = f"He notado que {tareas_fallidas} tareas han fallado m\u00faltiples veces. \u00bfTe parece que las revise?"
        else:
            mensaje = f"Esta semana has trabajado principalmente en tareas de tipo '{tipo_comun}'. \u00bfTe parece que automatice algo?"

    def obtener_pendientes(self) -> list[dict]:
        """Obtiene mensajes pendientes de entrega."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, tipo, titulo, mensaje, creado_en
            FROM conversaciones
            WHERE entregado = 0
            ORDER BY creado_en DESC
            LIMIT 10
        """
        )
        rows = cursor.fetchall()
        conn.close()
        return [
            {"id": r[0], "tipo": r[1], "titulo": r[2], "mensaje": r[3], "creado": r[4]}
            for r in rows
        ]

    def marcar_entregado(self, conversacion_id: int) -> bool:
        """Marca un mensaje como entregado."""
        ahora = datetime.now().isoformat()
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE conversaciones SET entregado = 1, entregado_en = ?
            WHERE id = ?
        """,
            (ahora, conversacion_id),
        )
        conn.commit()
        result = cursor.rowcount > 0
        conn.close()
        return result

    def marcar_interaccion(self, conversacion_id: int) -> bool:
        """Marca que el usuario interactuó con el mensaje."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE conversaciones SET interactuado = 1 WHERE id = ?", (conversacion_id,)
        )
        conn.commit()
        result = cursor.rowcount > 0
        conn.close()
        return result

    def historial(self, dias: int = 7, limite: int = 20) -> list[dict]:
        """Obtiene historial de conversaciones."""
        cutoff = (datetime.now() - timedelta(days=dias)).isoformat()
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, tipo, titulo, mensaje, interactuado, creado_en
            FROM conversaciones
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
                "titulo": r[2],
                "mensaje": r[3],
                "interactuado": bool(r[4]),
                "creado": r[5],
            }
            for r in rows
        ]

    def stats(self) -> dict:
        """Estadísticas de conversaciones."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM conversaciones")
        total = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM conversaciones WHERE entregado = 0")
        pendientes = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM conversaciones WHERE interactuado = 1")
        interactuadas = cursor.fetchone()[0]
        conn.close()
        return {
            "total": total,
            "pendientes": pendientes,
            "interactuadas": interactuadas,
            "tasa_respuesta": round(interactuadas / total * 100, 1) if total > 0 else 0,
        }

    def procesar(self, texto: str) -> str:
        """Procesar consulta para AgenteConversacion."""
        texto.lower()
        return "Hola, soy URA. ¿En qué puedo ayudarte hoy?"

    def ejecutar(self, texto: str) -> str:
        """Ejecutar acción para AgenteConversacion."""
        return self.procesar(texto)

    def consultar(self, texto: str) -> str:
        """Consultar información para AgenteConversacion."""
        return self.procesar(texto)

    def responder(self, texto: str) -> str:
        """Responder pregunta para AgenteConversacion."""
        return self.procesar(texto)

    def execute(self, *args, **kwargs) -> dict:
        """
        Método execute estándar para AgenteConversacion.

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


_CONVERSACION = None


def get_conversacion() -> AgenteConversacion:
    global _CONVERSACION
    if _CONVERSACION is None:
        _CONVERSACION = AgenteConversacion()
    return _CONVERSACION
