#!/usr/bin/env python3
"""
agente_juridico.py — URA Asistente Jurídico y Fiscal
=====================================================
Asistente para temas legales y fiscales del bar.

Capacidades:
- Recordatorio de obligaciones fiscales
- Sugerencias de deducciones
- Alertas de plazos
- Resúmenes de normativa
- Preparación de declaraciones

NOTA: Esto es orientación general, NO sustituye a un abogado/contable.
"""

import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)


class AgenteJuridico:
    IMPUESTOS_TRIMESTRALES = {
        "1": {"nombre": "IVA", "meses": [1, 2, 3], "vencimiento": "20/04"},
        "2": {"nombre": "IVA", "meses": [4, 5, 6], "vencimiento": "20/07"},
        "3": {"nombre": "IVA", "meses": [7, 8, 9], "vencimiento": "20/10"},
        "4": {"nombre": "IVA", "meses": [10, 11, 12], "vencimiento": "30/01"},
    }

    MODELOS_FISCALES = {
        "130": {"nombre": "IRPF estimaciones directas", "trimestral": True},
        "131": {"nombre": "IRPF estimaciones objetiva", "trimestral": True},
        "303": {"nombre": "IVA", "trimestral": True},
        "390": {"nombre": "IVA resumen anual", "trimestral": False, "vencimiento": "30/01"},
        "180": {
            "nombre": "Resumen anual retenciones alquileres",
            "trimestral": False,
            "vencimiento": "30/01",
        },
    }

    def __init__(self, db_path: str | None = None):
        if db_path is None:
            db_path = str(Path(__file__).resolve().parents[1] / "board.db")
        self.db_path = db_path
        logger.info(f"Inicializando AgenteJuridico con db_path={db_path}")
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS juridico_obligaciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tipo TEXT NOT NULL,
                modelo TEXT,
                descripcion TEXT,
                fecha_limite TEXT,
                estado TEXT DEFAULT 'pendiente',
                presentada INTEGER DEFAULT 0,
                created_at TEXT
            )
        """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS juridico_recordatorios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                titulo TEXT NOT NULL,
                descripcion TEXT,
                tipo TEXT,
                fecha TEXT,
                repetitivo INTEGER DEFAULT 0,
                frecuencia TEXT,
                activa INTEGER DEFAULT 1,
                created_at TEXT
            )
        """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS juridico_consultas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pregunta TEXT NOT NULL,
                respuesta TEXT,
                fuente TEXT,
                creada_en TEXT
            )
        """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS juridico_documentos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tipo TEXT NOT NULL,
                nombre TEXT NOT NULL,
                descripcion TEXT,
                archivo_path TEXT,
                fecha_caducidad TEXT,
                created_at TEXT
            )
        """
        )

        conn.commit()
        conn.close()

    def alertas_fiscales(self) -> list[dict]:
        """Alertas de obligaciones fiscales próximas."""
        ahora = datetime.now()
        alertas = []

        mes_actual = ahora.month
        trimestre_actual = str((mes_actual - 1) // 3 + 1)

        for modelo, info in self.MODELOS_FISCALES.items():
            if info.get("trimestral"):
                if trimestre_actual in self.IMPUESTOS_TRIMESTRALES:
                    datos = self.IMPUESTOS_TRIMESTRALES[trimestre_actual]
                    if mes_actual in datos["meses"]:
                        alertas.append(
                            {
                                "tipo": "fiscal",
                                "modelo": modelo,
                                "nombre": info["nombre"],
                                "trimestre": trimestre_actual,
                                "urgencia": "alta",
                                "mensaje": f"Modelo {modelo} - {info['nombre']} - Vence: {datos['vencimiento']}",
                            }
                        )

        cursor.execute("SELECT COUNT(*) FROM juridico_obligaciones WHERE estado = 'pendiente'")
        pendientes = cursor.fetchone()[0]
        if pendientes > 0:
            alertas.append(
                {
                    "tipo": "recordatorio",
                    "urgencia": "media",
                    "mensaje": f"Tienes {pendientes} obligaciones pendientes",
                }
            )

        return alertas

    def crear_obligacion(self, tipo: str, modelo: str, descripcion: str, fecha_limite: str) -> int:
        """Crea una obligación fiscal."""
        ahora = datetime.now().isoformat()
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO juridico_obligaciones
            (tipo, modelo, descripcion, fecha_limite, created_at)
            VALUES (?, ?, ?, ?, ?)
        """,
            (tipo, modelo, descripcion, fecha_limite, ahora),
        )
        result = cursor.lastrowid
        conn.commit()
        conn.close()
        return result

    def registrar_documento(
        self,
        tipo: str,
        nombre: str,
        descripcion: str = "",
        archivo_path: str = None,
        fecha_caducidad: str = None,
    ) -> int:
        """Registra un documento legal."""
        ahora = datetime.now().isoformat()
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO juridico_documentos
            (tipo, nombre, descripcion, archivo_path, fecha_caducidad, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (tipo, nombre, descripcion, archivo_path, fecha_caducidad, ahora),
        )
        result = cursor.lastrowid
        conn.commit()
        conn.close()
        return result

    def documentos_pendientes(self) -> list[dict]:
        """Documentos que caducan pronto."""
        ahora = datetime.now()
        en_30_dias = ahora + timedelta(days=30)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, tipo, nombre, fecha_caducidad
            FROM juridico_documentos
            WHERE fecha_caducidad IS NOT NULL
            AND fecha_caducidad <= ?
            ORDER BY fecha_caducidad ASC
        """,
            (en_30_dias.isoformat(),),
        )
        rows = cursor.fetchall()
        conn.close()
        return [{"id": r[0], "tipo": r[1], "nombre": r[2], "caducidad": r[3]} for r in rows]

    def deducciones_sugeridas(self) -> list[str]:
        """Sugerencias de deducciones fiscales para bares."""
        return [
            "Gastos de representación (hasta 10% de ingresos)",
            "Mantenimiento de equipos de climatización",
            "Seguros de responsabilidad civil",
            "Gastos de formación (cursos de camarero, bartendering)",
            "Renovación de licencias y permisos",
            "Inversiones en eficiencia energética",
            "Software de gestión y aplicaciones",
            "Gastos de limpieza y desinfectantes",
        ]

    def recordatorio_importante(self, titulo: str, descripcion: str, tipo: str = "general") -> int:
        """Crea un recordatorio."""
        ahora = datetime.now().isoformat()
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO juridico_recordatorios
            (titulo, descripcion, tipo, created_at)
            VALUES (?, ?, ?, ?)
        """,
            (titulo, descripcion, tipo, ahora),
        )
        result = cursor.lastrowid
        conn.commit()
        conn.close()
        return result

    def consultar(self, pregunta: str) -> dict:
        """Guarda una consulta para revisar con abogado."""
        ahora = datetime.now().isoformat()
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO juridico_consultas (pregunta, creada_en)
            VALUES (?, ?)
        """,
            (pregunta, ahora),
        )
        result = cursor.lastrowid
        conn.commit()
        conn.close()
        return {
            "id": result,
            "pregunta": pregunta,
            "nota": "Consulta guardada. Un abogado la revisará.",
        }

    def resumen_mensual(self) -> dict:
        """Resumen de obligaciones del mes."""
        ahora = datetime.now()
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT COUNT(*) FROM juridico_obligaciones
            WHERE estado = 'pendiente'
        """
        )
        pendientes = cursor.fetchone()[0]

        cursor.execute(
            """
            SELECT COUNT(*) FROM juridico_documentos
            WHERE fecha_caducidad <= ?
        """,
            ((ahora + timedelta(days=30)).isoformat(),),
        )
        caducan = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM juridico_consultas")
        consultas = cursor.fetchone()[0]

        conn.close()
        return {
            "obligaciones_pendientes": pendientes,
            "documentos_caducan_30dias": caducan,
            "consultas_pendientes": consultas,
            "mes": ahora.strftime("%B %Y"),
        }

    def procesar(self, texto: str) -> str:
        """Procesar consulta para AgenteJuridico."""
        texto.lower()
        return (
            "Puedo dar asesoría legal, consultar leyes y normativas. ¿Qué consulta jurídica tienes?"
        )

    def ejecutar(self, texto: str) -> str:
        """Ejecutar acción para AgenteJuridico."""
        return self.procesar(texto)

    def consultar(self, texto: str) -> str:
        """Consultar información para AgenteJuridico."""
        return self.procesar(texto)

    def responder(self, texto: str) -> str:
        """Responder pregunta para AgenteJuridico."""
        return self.procesar(texto)


if __name__ == "__main__":
    agente = AgenteJuridico()

    # Test: crear obligación
    obligacion_id = agente.crear_obligacion(
        tipo="fiscal", modelo="303", descripcion="IVA trimestre 1", fecha_limite="2024-04-20"
    )
    print(f"Obligación creada: {obligacion_id}")

    # Test: alertas
    alertas = agente.alertas_fiscales()
    print(f"Alertas: {len(alertas)}")
