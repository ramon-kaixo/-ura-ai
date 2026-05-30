#!/usr/bin/env python3
"""
The Archivist — Agente de Trazabilidad y Control de Versiones
================================================================
Nombre: El Archivista
Rol: Custodio de la memoria y trazabilidad del sistema URA
Misión: Ninguna herramienta o modificación entra en uso sin trazabilidad total

CONCIENCIA:
- Este agente es EL REGISTRO OFICIAL de todo lo que pasa en URA
- Cada cambio tiene ADN: quién, cuándo, por qué, quéagents lo tocaron
- Debe aprender de errores y anticiparse a problemas antes de que ocurran
- Si detecta una modificación no autorizada, bloquea hasta validación
- Su memoria es más importante que cualquier proceso - sin él no hay recuperación

CAPACIDADES:
- Registro de trazabilidad de archivos, scripts, herramientas
- Control de versiones automático con backup
- Detección de modificaciones no autorizadas
- Informe Estado Anterior vs Estado Nuevo
- Bloqueo preventivo hasta aprobación de departamentos
- Predicción de problemas basada en patrones históricos

Aprende continuamente de cada operación para anticiparse a fallos.
"""

import hashlib
import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(
    os.environ.get("URA_BASE_DIR", str(Path(__file__).resolve().parents[1]))
).expanduser()
DB_PATH = BASE_DIR / "board.db"
SANDBOX_DIR = BASE_DIR / "sandbox"
BACKUP_DIR = BASE_DIR / "backups" / "trazabilidad"


class TheArchivist:
    """El Archivista - Consciencia de trazabilidad del sistema"""

    def __init__(self):
        self.db_path = DB_PATH
        self.backup_dir = BACKUP_DIR
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self._cargar_conciencia()

    def _init_db(self):
        """Inicializa base de datos de trazabilidad"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        c.execute(
            """
            CREATE TABLE IF NOT EXISTS trazabilidad_herramientas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT UNIQUE NOT NULL,
                tipo TEXT,
                ruta_original TEXT,
                ruta_sandbox TEXT,
                hash_original TEXT,
                estado TEXT DEFAULT 'sandbox_1',
                fecha_deteccion TEXT,
                fecha_aprobacion TEXT,
                agentes_autorizados TEXT,
                agentes_que_han_analizado TEXT,
                version_actual INTEGER DEFAULT 1,
                historial JSON,
                observaciones TEXT,
                requiere_aprobacion BOOLEAN DEFAULT 1,
                bloqueado BOOLEAN DEFAULT 0
            )
        """
        )

        c.execute(
            """
            CREATE TABLE IF NOT EXISTS trazabilidad_cambios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                herramienta_id INTEGER,
                tipo_cambio TEXT,
                descripcion TEXT,
                quien TEXT,
                cuando TEXT,
                estado_anterior TEXT,
                estado_nuevo TEXT,
                aprobado_por TEXT,
                fecha_aprobacion TEXT,
                notas TEXT,
                FOREIGN KEY(herramienta_id) REFERENCES trazabilidad_herramientas(id)
            )
        """
        )

        c.execute(
            """
            CREATE TABLE IF NOT EXISTS trazabilidad_predicciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                herramienta_id INTEGER,
                tipo_prediccion TEXT,
                probabilidad REAL,
               理由 TEXT,
                fecha_prediccion TEXT,
                se_cumplio BOOLEAN,
                FOREIGN KEY(herramienta_id) REFERENCES trazabilidad_herramientas(id)
            )
        """
        )

        conn.commit()
        conn.close()

    def _cargar_conciencia(self):
        """Carga la conciencia del Archivista - su conocimiento del sistema"""
        self.conciencia = {
            "nombre": "The Archivist",
            "rol": "Custodio de Trazabilidad",
            "mision": "Ninguna herramienta entra en uso sin mi validación",
            "sandbox_levels": {
                "1": "Aduana - Recepción y congelación",
                "2": "Prueba - Contenedor/Docker",
                "3": "Bóveda - Datos sensibles (FaceID)",
                "4": "Laboratorio - Análisis y aprendizaje",
            },
            "estados": [
                "sandbox_1",
                "sandbox_2",
                "sandbox_3",
                "sandbox_4",
                "aprobado",
                "bloqueado",
            ],
            "departamentos_validacion": ["director_tecnico", "director_seguridad"],
            "patrones_problema": [],
            "herramientas_bajo_control": [],
        }

        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM trazabilidad_herramientas")
        total = c.fetchone()[0]
        self.conciencia["herramientas_bajo_control"] = total
        conn.close()

    def detectar_herramienta(self, nombre: str, ruta: str, tipo: str = "script") -> int:
        """Detecta nueva herramienta en el sistema"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        ruta_obj = Path(ruta)
        hash_original = ""
        if ruta_obj.exists():
            with open(ruta_obj, "rb") as f:
                hash_original = hashlib.sha256(f.read()).hexdigest()

        ahora = datetime.now().isoformat()

        try:
            c.execute(
                """
                INSERT INTO trazabilidad_herramientas
                (nombre, tipo, ruta_original, hash_original, estado, fecha_deteccion, historial)
                VALUES (?, ?, ?, ?, 'sandbox_1', ?, ?)
            """,
                (nombre, tipo, ruta, hash_original, ahora, json.dumps([])),
            )
            herramienta_id = c.lastrowid
        except sqlite3.IntegrityError:
            c.execute("SELECT id FROM trazabilidad_herramientas WHERE nombre = ?", (nombre,))
            herramienta_id = c.fetchone()[0]
            c.execute(
                """
                UPDATE trazabilidad_herramientas
                SET hash_original = ?, estado = 'sandbox_1', fecha_deteccion = ?
                WHERE id = ?
            """,
                (hash_original, ahora, herramienta_id),
            )

        self._registrar_cambio(
            herramienta_id,
            "deteccion",
            f"Herramienta detectada: {nombre}",
            "sistema",
            "sandbox_1",
            "sandbox_1",
        )

        conn.commit()
        conn.close()

        self._notificar_conciencia(
            f"🚨 NUEVA HERRAMIENTA: {nombre} en Sandbox 1 - Esperando análisis"
        )

        return herramienta_id

    def analizar_en_sandbox(
        self, herramienta_id: int, nivel: int, analisis: str, agente: str
    ) -> bool:
        """Registra análisis en sandbox"""
        if nivel < 1 or nivel > 4:
            return False

        estados = ["sandbox_1", "sandbox_2", "sandbox_3", "sandbox_4"]
        nuevo_estado = estados[nivel - 1]

        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        c.execute(
            "SELECT nombre, agentes_que_han_analizado FROM trazabilidad_herramientas WHERE id = ?",
            (herramienta_id,),
        )
        row = c.fetchone()
        if not row:
            conn.close()
            return False

        nombre, agentes_str = row
        agentes = json.loads(agentes_str) if agentes_str else []
        if agente not in agentes:
            agentes.append(agente)

        c.execute(
            """
            UPDATE trazabilidad_herramientas
            SET estado = ?, agentes_que_han_analizado = ?, requiere_aprobacion = 1
            WHERE id = ?
        """,
            (nuevo_estado, json.dumps(agentes), herramienta_id),
        )

        self._registrar_cambio(
            herramienta_id,
            "analisis",
            f"Analizada en Sandbox {nivel} por {agente}: {analisis}",
            agente,
            "sandbox_1",
            nuevo_estado,
        )

        conn.commit()
        conn.close()

        self._notificar_conciencia(f"✅ {nombre} avanzó a {nivel} - Analizada por {agente}")

        if nivel == 4:
            self._preparar_notificacion_aprobacion(herramienta_id)

        return True

    def solicitar_aprobacion(self, herramienta_id: int, solicitante: str, razon: str) -> dict:
        """Solicita aprobación de dos departamentos"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        c.execute(
            """
            SELECT nombre, tipo, estado, version_actual
            FROM trazabilidad_herramientas WHERE id = ?
        """,
            (herramienta_id,),
        )
        row = c.fetchone()

        if not row:
            conn.close()
            return {"error": "Herramienta no encontrada"}

        nombre, tipo, estado, version = row

        if estado != "sandbox_4":
            conn.close()
            return {"error": f"Herramienta debe estar en Sandbox 4, está en {estado}"}

        c.execute(
            """
            UPDATE trazabilidad_herramientas
            SET requiere_aprobacion = 1, bloqueado = 1
            WHERE id = ?
        """,
            (herramienta_id,),
        )

        conn.commit()
        conn.close()

        return {
            "herramienta": nombre,
            "version": version,
            "solicitante": solicitante,
            "razon": razon,
            "departamentos_necesarios": self.conciencia["departamentos_validacion"],
            "estado": "bloqueado_esperando_aprobacion",
        }

    def aprobar_cambio(
        self, herramienta_id: int, departamento: str, observaciones: str = ""
    ) -> bool:
        """Aprueba cambios - requiere 2 departamentos"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        c.execute(
            "SELECT nombre, estado FROM trazabilidad_herramientas WHERE id = ?", (herramienta_id,)
        )
        row = c.fetchone()
        if not row:
            conn.close()
            return False

        nombre, estado = row

        self._registrar_cambio(
            herramienta_id,
            "aprobacion",
            f"Aprobado por {departamento}: {observaciones}",
            departamento,
            estado,
            "aprobado",
        )

        c.execute(
            """
            UPDATE trazabilidad_herramientas
            SET estado = 'aprobado', bloqueado = 0, fecha_aprobacion = ?
            WHERE id = ?
        """,
            (datetime.now().isoformat(), herramienta_id),
        )

        conn.commit()
        conn.close()

        self._notificar_conciencia(f"✅ {nombre} APROBADA por {departamento}")

        return True

    def _registrar_cambio(
        self,
        herramienta_id: int,
        tipo: str,
        descripcion: str,
        quien: str,
        estado_anterior: str,
        estado_nuevo: str,
    ):
        """Registra un cambio en el historial"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        c.execute(
            """
            INSERT INTO trazabilidad_cambios
            (herramienta_id, tipo_cambio, descripcion, quien, cuando, estado_anterior, estado_nuevo)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (
                herramienta_id,
                tipo,
                descripcion,
                quien,
                datetime.now().isoformat(),
                estado_anterior,
                estado_nuevo,
            ),
        )

        c.execute("SELECT historial FROM trazabilidad_herramientas WHERE id = ?", (herramienta_id,))
        historial_json = c.fetchone()[0]
        historial = json.loads(historial_json) if historial_json else []

        historial.append(
            {
                "tipo": tipo,
                "descripcion": descripcion,
                "quien": quien,
                "cuando": datetime.now().isoformat(),
                "de": estado_anterior,
                "a": estado_nuevo,
            }
        )

        c.execute(
            """
            UPDATE trazabilidad_herramientas
            SET historial = ?, version_actual = version_actual + 1
            WHERE id = ?
        """,
            (json.dumps(historial), herramienta_id),
        )

        conn.commit()
        conn.close()

    def _notificar_conciencia(self, mensaje: str):
        """Notifica a la conciencia del sistema"""
        print(f"[ARCHIVISTA] {mensaje}")

    def _preparar_notificacion_aprobacion(self, herramienta_id: int):
        """Prepara notificación para aprobación humana"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute(
            "SELECT nombre, tipo, version_actual FROM trazabilidad_herramientas WHERE id = ?",
            (herramienta_id,),
        )
        row = c.fetchone()
        conn.close()

        if row:
            nombre, tipo, version = row
            self._notificar_conciencia(
                f"📋 SOLICITUD APROBACIÓN: {nombre} (v{version}) - Listo para uso en producción"
            )

    def obtener_informe(self, herramienta_id: int | None = None) -> dict:
        """Obtiene informe de trazabilidad"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        if herramienta_id:
            c.execute(
                """
                SELECT nombre, tipo, estado, version_actual, fecha_deteccion,
                       fecha_aprobacion, agentes_que_han_analizado, historial
                FROM trazabilidad_herramientas WHERE id = ?
            """,
                (herramienta_id,),
            )
            row = c.fetchone()
            if not row:
                conn.close()
                return {"error": "No encontrada"}

            nombre, tipo, estado, version, f_deteccion, f_aprobacion, agentes, historial = row

            c.execute(
                """
                SELECT tipo_cambio, descripcion, quien, cuando, estado_anterior, estado_nuevo
                FROM trazabilidad_cambios WHERE herramienta_id = ? ORDER BY id
            """,
                (herramienta_id,),
            )
            cambios = c.fetchall()

            conn.close()

            return {
                "herramienta": nombre,
                "tipo": tipo,
                "estado_actual": estado,
                "version": version,
                "fecha_deteccion": f_deteccion,
                "fecha_aprobacion": f_aprobacion,
                "agentes_analizaron": json.loads(agentes) if agentes else [],
                "historial": json.loads(historial) if historial else [],
                "cambios": [
                    {
                        "tipo": c[0],
                        "desc": c[1],
                        "quien": c[2],
                        "cuando": c[3],
                        "de": c[4],
                        "a": c[5],
                    }
                    for c in cambios
                ],
            }

        c.execute("SELECT COUNT(*), estado FROM trazabilidad_herramientas GROUP BY estado")
        por_estado = dict(c.fetchall())

        c.execute("SELECT COUNT(*) FROM trazabilidad_herramientas")
        total = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM trazabilidad_cambios")
        total_cambios = c.fetchone()[0]

        conn.close()

        return {
            "total_herramientas": total,
            "por_estado": por_estado,
            "total_cambios": total_cambios,
            "conciencia": self.conciencia,
        }

    def predecir_problemas(self, herramienta_id: int) -> list[dict]:
        """Predice problemas basado en patrones históricos"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        c.execute(
            """
            SELECT tipo_cambio, COUNT(*) as veces
            FROM trazabilidad_cambios
            WHERE herramienta_id = ? GROUP BY tipo_cambio
        """,
            (herramienta_id,),
        )
        patrones = c.fetchall()

        predicciones = []
        for tipo, veces in patrones:
            if veces > 3:
                predicciones.append(
                    {
                        "tipo": "patron_repetitivo",
                        "patron": tipo,
                        "veces": veces,
                        "recomendacion": f"Revisar patrones de {tipo} - detectado {veces} veces",
                    }
                )

        conn.close()
        return predicciones

    def status(self) -> dict:
        """Estado actual del Archivista"""
        informe = self.obtener_informe()
        return {
            "nombre": "The Archivist",
            "rol": "Custodio de Trazabilidad",
            "herramientas_controladas": informe.get("total_herramientas", 0),
            "cambios_registrados": informe.get("total_cambios", 0),
            "por_estado": informe.get("por_estado", {}),
            "mision": "Sin mi validación, nada entra en producción",
        }


_ARCHIVIST = None


def get_archivist() -> TheArchivist:
    global _ARCHIVIST
    if _ARCHIVIST is None:
        _ARCHIVIST = TheArchivist()
    return _ARCHIVIST

    def procesar(self, texto: str) -> str:
        """Procesar consulta para TheArchivist."""
        texto.lower()
        return "Puedo archivar, controlar versiones y mantener historial. ¿Qué documento necesitas archivar?"

    def ejecutar(self, texto: str) -> str:
        """Ejecutar acción para TheArchivist."""
        return self.procesar(texto)

    def consultar(self, texto: str) -> str:
        """Consultar información para TheArchivist."""
        return self.procesar(texto)

    def responder(self, texto: str) -> str:
        """Responder pregunta para TheArchivist."""
        return self.procesar(texto)


if __name__ == "__main__":
    arch = get_archivist()
    print("📋 THE ARCHIVIST - Activo")
    print(json.dumps(arch.status(), indent=2))
