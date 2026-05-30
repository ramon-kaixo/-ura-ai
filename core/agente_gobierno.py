#!/usr/bin/env python3
"""
agente_gobierno.py — URA Agente de Servicios Públicos
====================================================
Conexión con servicios del gobierno español.

Capacidades:
- Buzón electrónico @ciudadano.gob.es
- Cl@ve PIN/Firma
-Presenter declaraciones (IVA, IRPF, etc.)
- BOE (Boletín Oficial del Estado)
- Seguridad Social

REQUISITOS:
- Certificado digital o usuario Cl@ve
- Configuración específica por servicio
"""

import sqlite3
from datetime import datetime
from pathlib import Path

try:
    import requests

    REQUESTS_OK = True
except:
    REQUESTS_OK = False


class AgenteGobierno:
    SERVICIOS = {
        "aeat": {
            "nombre": "Agencia Tributaria",
            "url_base": "https://www.agenciatributaria.es",
            "modelos": ["303", "130", "131", "390", "180", "100", "390"],
        },
        "tgss": {
            "nombre": "Tesorería General Seguridad Social",
            "url_base": "https://sede.seg-social.gob.es",
            "modelos": ["TRC", "RNT", "RLC"],
        },
        "trabajo": {
            "nombre": "Ministerio de Trabajo",
            "url_base": "https://www.mites.gob.es",
            "servicios": ["contratos", "nóminas"],
        },
        "boe": {"nombre": "Boletín Oficial del Estado", "url_base": "https://www.boe.es"},
    }

    def __init__(self, db_path: str | None = None):
        if db_path is None:
            db_path = str(Path(__file__).resolve().parents[1] / "board.db")
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS gobierno_comunicaciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                origen TEXT NOT NULL,
                asunto TEXT,
                resumen TEXT,
                leido INTEGER DEFAULT 0,
                relevante INTEGER DEFAULT 0,
                fecha TEXT,
                created_at TEXT
            )
        """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS gobierno_declaraciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                modelo TEXT NOT NULL,
                periodo TEXT NOT NULL,
                estado TEXT DEFAULT 'pendiente',
                importe REAL,
                fecha_presentacion TEXT,
                justificante TEXT,
                created_at TEXT
            )
        """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS gobierno_notificaciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                organismo TEXT NOT NULL,
                tipo TEXT,
                mensaje TEXT,
                leida INTEGER DEFAULT 0,
                fecha TEXT,
                created_at TEXT
            )
        """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS gobierno_config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                servicio TEXT UNIQUE NOT NULL,
                configuracion TEXT,
                activa INTEGER DEFAULT 0,
                updated_at TEXT
            )
        """
        )

        conn.commit()
        conn.close()

    def registrar_declaracion(
        self, modelo: str, periodo: str, importe: float = None, estado: str = "pendiente"
    ) -> int:
        """Registra una declaración a presentar."""
        ahora = datetime.now().isoformat()
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO gobierno_declaraciones
            (modelo, periodo, estado, importe, created_at)
            VALUES (?, ?, ?, ?, ?)
        """,
            (modelo, periodo, estado, importe, ahora),
        )
        result = cursor.lastrowid
        conn.commit()
        conn.close()
        return result

    def declaraciones_pendientes(self) -> list[dict]:
        """Lista declaraciones pendientes."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, modelo, periodo, estado, importe, created_at
            FROM gobierno_declaraciones
            WHERE estado = 'pendiente'
            ORDER BY periodo DESC
        """
        )
        rows = cursor.fetchall()
        conn.close()
        return [
            {
                "id": r[0],
                "modelo": r[1],
                "periodo": r[2],
                "estado": r[3],
                "importe": r[4],
                "creada": r[5],
            }
            for r in rows
        ]

    def alertas_plazos(self) -> list[dict]:
        """Alertas de plazos próximos."""
        datetime.now()
        alertas = []

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, modelo, periodo FROM gobierno_declaraciones
            WHERE estado = 'pendiente'
        """
        )
        for row in cursor.fetchall():
            alertas.append(
                {
                    "tipo": "declaracion",
                    "modelo": row[1],
                    "periodo": row[2],
                    "mensaje": f"Modelo {row[1]} - Periodo {row[2]} pendiente",
                }
            )
        conn.close()

        alertas.extend(
            [
                {
                    "tipo": "recordatorio",
                    "modelo": "303",
                    "periodo": self._trimestre_actual(),
                    "mensaje": f"Modelo 303 (IVA {self._trimestre_actual()} trimestre) - Vence día 20",
                },
                {
                    "tipo": "recordatorio",
                    "modelo": "130",
                    "periodo": self._trimestre_actual(),
                    "mensaje": f"Modelo 130 (IRPF {self._trimestre_actual()} trimestre) - Vence día 20",
                },
            ]
        )

        return alertas

    def _trimestre_actual(self) -> str:
        mes = datetime.now().month
        return str((mes - 1) // 3 + 1)

    def notificar_comunicacion(
        self, organismo: str, tipo: str, mensaje: str, relevante: bool = False
    ) -> int:
        """Registra una comunicación del gobierno."""
        ahora = datetime.now().isoformat()
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO gobierno_notificaciones
            (organismo, tipo, mensaje, leida, fecha, created_at)
            VALUES (?, ?, ?, 0, ?, ?)
        """,
            (organismo, tipo, mensaje, ahora, ahora),
        )
        result = cursor.lastrowid
        conn.commit()
        conn.close()
        return result

    def comunicaciones_pendientes(self) -> list[dict]:
        """Comunicaciones pendientes de leer."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, organismo, tipo, mensaje, fecha
            FROM gobierno_notificaciones
            WHERE leida = 0
            ORDER BY fecha DESC
            LIMIT 20
        """
        )
        rows = cursor.fetchall()
        conn.close()
        return [
            {"id": r[0], "organismo": r[1], "tipo": r[2], "mensaje": r[3], "fecha": r[4]}
            for r in rows
        ]

    def marcar_leida(self, notificacion_id: int) -> bool:
        """Marca notificación como leída."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE gobierno_notificaciones SET leida = 1 WHERE id = ?", (notificacion_id,)
        )
        conn.commit()
        result = cursor.rowcount > 0
        conn.close()
        return result

    def resumen(self) -> dict:
        """Resumen del estado con el gobierno."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM gobierno_notificaciones WHERE leida = 0")
        comunicaciones = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM gobierno_declaraciones WHERE estado = 'pendiente'")
        declaraciones = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM gobierno_declaraciones WHERE estado = 'presentada'")
        presentadas = cursor.fetchone()[0]

        conn.close()
        return {
            "comunicaciones_pendientes": comunicaciones,
            "declaraciones_pendientes": declaraciones,
            "declaraciones_presentadas": presentadas,
        }

    def boe_buscar(self, query: str) -> list[dict]:
        """Busca en el BOE."""
        if not REQUESTS_OK:
            return [{"error": "requests no disponible"}]

        try:
            url = "https://www.boe.es/buscar/atom.php"
            params = {"q": query, "zone": "boe"}
            resp = requests.get(url, params=params, timeout=10)
            if resp.status_code == 200:
                return [{"resultado": "Búsqueda BOE disponible", "query": query}]
        except Exception as e:
            return [{"error": str(e)}]

        return [{"info": "Para BOE, usar web directamente"}]

    def procesar(self, texto: str) -> str:
        """Procesar consulta para AgenteGobierno."""
        texto.lower()
        return "Puedo gestionar trámites de gobierno y sede electrónica. ¿Qué trámite necesitas?"

    def ejecutar(self, texto: str) -> str:
        """Ejecutar acción para AgenteGobierno."""
        return self.procesar(texto)

    def consultar(self, texto: str) -> str:
        """Consultar información para AgenteGobierno."""
        return self.procesar(texto)

    def responder(self, texto: str) -> str:
        """Responder pregunta para AgenteGobierno."""
        return self.procesar(texto)

    def execute(self, *args, **kwargs) -> dict:
        """
        Método execute estándar para AgenteGobierno.

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


_GOBIERNO = None


def get_gobierno() -> AgenteGobierno:
    global _GOBIERNO
    if _GOBIERNO is None:
        _GOBIERNO = AgenteGobierno()
    return _GOBIERNO
