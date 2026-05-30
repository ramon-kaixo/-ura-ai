#!/usr/bin/env python3
"""
Módulo de Doble Verificación (2FA Sovereign)
Sistema de seguridad con Email + FaceID/TouchID
"""

import json
import os
import sqlite3
import subprocess
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(
    os.environ.get("URA_BASE_DIR", str(Path(__file__).resolve().parents[1]))
).expanduser()
DB_PATH = BASE_DIR / "board.db"
EMAIL_CONFIG = BASE_DIR / "config" / "email.json"


class DoubleLockSovereign:
    """Sistema de doble verificación - Seguridad máxima"""

    def __init__(self):
        self.db_path = DB_PATH
        self._init_db()
        self._cargar_config()

    def _init_db(self):
        """Inicializa tablas de seguridad"""
        conn = sqlite3.connect(self.db_path, timeout=30)
        c = conn.cursor()

        # Tabla de solicitudes de validación
        c.execute("""
            CREATE TABLE IF NOT EXISTS validaciones_2fa (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                accion TEXT NOT NULL,
                tipo_riesgo TEXT DEFAULT 'medio',
                descripcion TEXT,
                solicitante TEXT,
                fecha_solicitud TEXT,
                estado TEXT DEFAULT 'pendiente',
                token_validacion TEXT,
                validado_por TEXT,
                fecha_validacion TEXT,
                email_enviado BOOLEAN DEFAULT 0,
                biometrico_requerido BOOLEAN DEFAULT 0,
                biometrico_validado BOOLEAN DEFAULT 0
            )
        """)

        # Tabla de configuración de seguridad
        c.execute("""
            CREATE TABLE IF NOT EXISTS seguridad_config (
                id INTEGER PRIMARY KEY,
                modo_vault_activo BOOLEAN DEFAULT 0,
                vault_bloqueado BOOLEAN DEFAULT 1,
                ultimo_desbloqueo TEXT,
                nivel_seguridad TEXT DEFAULT 'alto',
                notificaciones_email BOOLEAN DEFAULT 1,
                biometrico_obligatorio BOOLEAN DEFAULT 1,
                email_admin TEXT DEFAULT 'barkaixo@gmail.com'
            )
        """)

        # Tabla de log de seguridad
        c.execute("""
            CREATE TABLE IF NOT EXISTS seguridad_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                evento TEXT NOT NULL,
                tipo TEXT,
                detalles TEXT,
                timestamp TEXT
            )
        """)

        # Inicializar config si no existe
        c.execute("SELECT COUNT(*) FROM seguridad_config")
        if c.fetchone()[0] == 0:
            c.execute("""INSERT INTO seguridad_config (id, modo_vault_activo, vault_bloqueado)
                VALUES (1, 1, 1)""")

        conn.commit()
        conn.close()

    def _cargar_config(self):
        """Carga configuración de seguridad"""
        conn = sqlite3.connect(self.db_path, timeout=30)
        c = conn.cursor()

        c.execute("SELECT * FROM seguridad_config WHERE id = 1")
        row = c.fetchone()

        self.config = {
            "modo_vault_activo": row[1],
            "vault_bloqueado": row[2],
            "ultimo_desbloqueo": row[3],
            "nivel_seguridad": row[4],
            "notificaciones_email": row[5],
            "biometrico_obligatorio": row[6],
            "email_admin": row[7],
        }

        conn.close()

    def solicitar_validacion(
        self, accion: str, descripcion: str, tipo_riesgo: str = "medio", solicitante: str = "URA"
    ) -> int:
        """Solicita validación para una acción"""
        conn = sqlite3.connect(self.db_path, timeout=30)
        c = conn.cursor()

        ahora = datetime.now().isoformat()
        token = f"VAL-{datetime.now().strftime('%Y%m%d%H%M%S')}-{hash(accion) % 100000}"

        # Determinar si requiere biométrico
        requiere_biometrico = tipo_riesgo == "critico"

        c.execute(
            """
            INSERT INTO validaciones_2fa
            (accion, tipo_riesgo, descripcion, solicitante, fecha_solicitud,
             estado, token_validacion, biometrico_requerido)
            VALUES (?, ?, ?, ?, ?, 'pendiente', ?, ?)
        """,
            (accion, tipo_riesgo, descripcion, solicitante, ahora, token, requiere_biometrico),
        )

        validacion_id = c.lastrowid

        # Registrar en log
        c.execute(
            """
            INSERT INTO seguridad_log (evento, tipo, detalles, timestamp)
            VALUES (?, ?, ?, ?)
        """,
            ("SOLICITUD_VALIDACION", tipo_riesgo, f"Acción: {accion}, Token: {token}", ahora),
        )

        conn.commit()
        conn.close()

        # Enviar email si es riesgo crítico
        if tipo_riesgo == "critico":
            self._enviar_alerta_critica(accion, descripcion, token)

        return validacion_id

    def _enviar_alerta_critica(self, accion: str, descripcion: str, token: str):
        """Envía alerta por email cuando hay acción de riesgo crítico"""
        # Aquí se configuraría el envío de email
        print(f"📧 ALERTA CRÍTICA: {accion}")
        print(f"   Token: {token}")
        print(f"   Descripción: {descripcion}")
        print("   Requiere FaceID para validar")

    def verificar_biometrico(self, validacion_id: int) -> bool:
        """Verifica identidad mediante FaceID/TouchID"""
        try:
            # Usar AppleScript para FaceID/TouchID
            script = """
            tell application "System Events"
                authenticate using biometric domain "com.ura.seguridad"
            end tell
            """

            result = subprocess.run(
                ["osascript", "-e", script], capture_output=True, text=True, timeout=10
            )

            if result.returncode == 0:
                ahora = datetime.now().isoformat()
                conn = sqlite3.connect(self.db_path, timeout=30)
                c = conn.cursor()

                c.execute(
                    """
                    UPDATE validaciones_2fa
                    SET biometrico_validado = 1, estado = 'aprobado',
                    validado_por = 'BIOMETRICO', fecha_validacion = ?
                    WHERE id = ?
                """,
                    (ahora, validacion_id),
                )

                c.execute(
                    """
                    INSERT INTO seguridad_log (evento, tipo, detalles, timestamp)
                    VALUES (?, ?, ?, ?)
                """,
                    (
                        "BIOMETRICO_APROBADO",
                        "critico",
                        f"Validación {validacion_id} aprobada por FaceID",
                        ahora,
                    ),
                )

                conn.commit()
                conn.close()

                return True

        except Exception as e:
            print(f"Error biométrico: {e}")

        return False

    def aprobar_validacion(self, validacion_id: int, validado_por: str = "admin") -> bool:
        """Aprueba manualmente una validación"""
        ahora = datetime.now().isoformat()

        conn = sqlite3.connect(self.db_path, timeout=30)
        c = conn.cursor()

        c.execute(
            """
            UPDATE validaciones_2fa
            SET estado = 'aprobado', validado_por = ?, fecha_validacion = ?
            WHERE id = ?
        """,
            (validado_por, ahora, validacion_id),
        )

        c.execute(
            """
            INSERT INTO seguridad_log (evento, tipo, detalles, timestamp)
            VALUES (?, ?, ?, ?)
        """,
            (
                "VALIDACION_APROBADA",
                "medio",
                f"Validación {validacion_id} aprobada por {validado_por}",
                ahora,
            ),
        )

        conn.commit()
        conn.close()

        return True

    def bloquear_vault(self):
        """Bloquea la bóveda de datos sensibles"""
        conn = sqlite3.connect(self.db_path, timeout=30)
        c = conn.cursor()

        ahora = datetime.now().isoformat()

        c.execute("UPDATE seguridad_config SET vault_bloqueado = 1 WHERE id = 1")

        c.execute(
            """
            INSERT INTO seguridad_log (evento, tipo, detalles, timestamp)
            VALUES (?, ?, ?, ?)
        """,
            ("VAULT_BLOQUEADO", "critico", "Bóveda bloqueada", ahora),
        )

        conn.commit()
        conn.close()

        self.config["vault_bloqueado"] = True
        return True

    def desbloquear_vault(self, validacion_id: int = None) -> bool:
        """Desbloquea la bóveda tras validación"""
        conn = sqlite3.connect(self.db_path, timeout=30)
        c = conn.cursor()

        ahora = datetime.now().isoformat()

        c.execute(
            "UPDATE seguridad_config SET vault_bloqueado = 0, ultimo_desbloqueo = ? WHERE id = 1",
            (ahora,),
        )

        c.execute(
            """
            INSERT INTO seguridad_log (evento, tipo, detalles, timestamp)
            VALUES (?, ?, ?, ?)
        """,
            (
                "VAULT_DESBLOQUEADO",
                "critico",
                f"Bóveda desbloqueada - Validación: {validacion_id}",
                ahora,
            ),
        )

        conn.commit()
        conn.close()

        self.config["vault_bloqueado"] = False
        return True

    def obtener_estado(self) -> dict:
        """Obtiene estado actual del sistema de seguridad"""
        conn = sqlite3.connect(self.db_path, timeout=30)
        c = conn.cursor()

        c.execute("SELECT * FROM seguridad_config WHERE id = 1")
        config = c.fetchone()

        c.execute("SELECT COUNT(*) FROM validaciones_2fa WHERE estado = 'pendiente'")
        pendientes = c.fetchone()[0]

        c.execute(
            "SELECT COUNT(*) FROM validaciones_2fa WHERE fecha_solicitud > datetime('now', '-24 hours')"
        )
        ultimas_24h = c.fetchone()[0]

        conn.close()

        return {
            "vault_activo": config[1],
            "vault_bloqueado": config[2],
            "ultimo_desbloqueo": config[3],
            "nivel_seguridad": config[4],
            "validaciones_pendientes": pendientes,
            "validaciones_24h": ultimas_24h,
        }

    def obtener_log(self, limite: int = 20) -> list:
        """Obtiene log de seguridad"""
        conn = sqlite3.connect(self.db_path, timeout=30)
        c = conn.cursor()

        c.execute(
            """
            SELECT evento, tipo, detalles, timestamp
            FROM seguridad_log
            ORDER BY id DESC LIMIT ?
        """,
            (limite,),
        )

        resultados = [
            {"evento": r[0], "tipo": r[1], "detalles": r[2], "timestamp": r[3]}
            for r in c.fetchall()
        ]

        conn.close()
        return resultados


_DOUBLELOCK = None


def get_double_lock() -> DoubleLockSovereign:
    global _DOUBLELOCK
    if _DOUBLELOCK is None:
        _DOUBLELOCK = DoubleLockSovereign()
    return _DOUBLELOCK


if __name__ == "__main__":
    dl = get_double_lock()
    estado = dl.obtener_estado()
    print("🔐 Double-Lock Sovereign - Estado:")
    print(json.dumps(estado, indent=2))
