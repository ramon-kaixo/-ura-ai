#!/usr/bin/env python3
"""
Motor de Autorización Dual (DAM)
Sistema completo de validación: ALFA (email) + OMEGA (biometría)
"""

import hashlib
import json
import os
import sqlite3
import sys
import threading
from datetime import datetime
from pathlib import Path

# Importar LocalAuthentication para autenticación biométrica real en macOS
if sys.platform == "darwin":
    try:
        import LocalAuthentication

        LOCAL_AUTH_AVAILABLE = True
    except ImportError:
        LOCAL_AUTH_AVAILABLE = False
else:
    LOCAL_AUTH_AVAILABLE = False

sys.path.append(str(Path(__file__).parent))

from notificador_dam import get_notificador

BASE_DIR = Path(
    os.environ.get("URA_BASE_DIR", str(Path(__file__).resolve().parents[1]))
).expanduser()
DB_PATH = BASE_DIR / "board.db"


class MotorAutorizacionDual:
    """DAM - Discrimina entre validación simple y crítica"""

    def __init__(self):
        self.db_path = DB_PATH
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path, timeout=30)
        c = conn.cursor()

        # Tabla principal de autorizaciones
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS autorizaciones_dam (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token TEXT UNIQUE,
                accion TEXT NOT NULL,
                nivel TEXT DEFAULT 'ALFA',
                descripcion TEXT,
                justificacion TEXT,
                solicitante TEXT,
                fecha_solicitud TEXT,
                estado TEXT DEFAULT 'pendiente',
                email_enviado BOOLEAN DEFAULT 0,
                biometrico_requerido BOOLEAN DEFAULT 0,
                biometrico_validado BOOLEAN DEFAULT 0,
                validado_por TEXT,
                fecha_validacion TEXT,
                ip_origen TEXT,
                dispositivo TEXT,
                tiempo_expiracion_minutos INTEGER DEFAULT 30
            )
        """
        )

        # Tabla de eventos de seguridad
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS eventos_seguridad_dam (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                evento TEXT NOT NULL,
                nivel TEXT,
                detalles TEXT,
                resultado TEXT,
                timestamp TEXT
            )
        """
        )

        # Configuración del DAM
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS dam_config (
                id INTEGER PRIMARY KEY,
                nivel_default TEXT DEFAULT 'ALFA',
                tiempo_expiracion INTEGER DEFAULT 30,
                biometria_obligatoria_omega BOOLEAN DEFAULT 1,
                email_notificaciones TEXT DEFAULT 'barkaixo@gmail.com',
                historial_dias INTEGER DEFAULT 90
            )
        """
        )

        # Inicializar config
        c.execute("SELECT COUNT(*) FROM dam_config")
        if c.fetchone()[0] == 0:
            c.execute("INSERT INTO dam_config (id) VALUES (1)")

        conn.commit()
        conn.close()

    def _generar_token(self, accion: str) -> str:
        """Genera token único para la autorización"""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        hash_val = hashlib.md5(f"{accion}{timestamp}".encode(), usedforsecurity=False).hexdigest()[
            :8
        ]
        return f"DAM-{timestamp}-{hash_val}"

    def _es_accion_critica(self, accion: str) -> bool:
        """Determina si la acción es nivel OMEGA (crítica)"""
        acciones_criticas = [
            "BANCO",
            "PAGO",
            "TRANSFERENCIA",
            "DNI",
            "PASSWORDS",
            "CLAVES",
            "DATOS_SENSIBLES",
            "SALIDA_DATOS",
            "FACTURA_PAGO",
            "CONTRASEÑA",
            "TARJETA",
            "CUENTA_BANCO",
            "CREDI",
            "HIPOTECA",
            "MONEY",
            "BIT2ME",
            "BINANCE",
            "KRAKEN",
            "COINBASE",
            "ACCESS_BANCO",
            "ACCESS_BAULA",
            "ACCESS_DINERO",
        ]

        return any(palabra in accion.upper() for palabra in acciones_criticas)

    # ─── Análisis de riesgo ────────────────────────────────────────────
    _PERMISOS_MAP = {
        "DESCARGA_APP": "escritura en /Applications, acceso a red, ejecución de código",
        "PAGO_FACTURA": "acceso a datos bancarios, transferencia de fondos, conexión externa",
        "ACCESS_BANCO": "autenticación bancaria, acceso a cuenta, posible transferencia",
        "MODIFICAR_SCRIPT": "escritura en sistema de archivos, posible ejecución de código",
        "ELIMINAR": "borrado permanente de datos, sin posibilidad de recuperación",
        "INSTALAR": "modificación del sistema, permisos de administrador",
        "TRANSFERENCIA": "movimiento de fondos, acceso a cuentas externas",
        "DATOS_SENSIBLES": "lectura de datos privados, posible exfiltración",
        "BACKUP": "lectura completa del sistema, escritura en destino externo",
        "CONFIGURAR": "modificación de configuración del sistema o agentes",
    }
    _RIESGO_REGLAS = [
        # (keywords_en_accion_o_desc, nivel, motivo)
        (
            [
                "BANCO",
                "PAGO",
                "TRANSFERENCIA",
                "CREDI",
                "FACTURA_PAGO",
                "BIT2ME",
                "BINANCE",
                "COINBASE",
                "KRAKEN",
                "DINERO",
            ],
            "ALTO",
            "Operación financiera o acceso a banca — impacto económico directo",
        ),
        (
            [
                "PASSWORDS",
                "CLAVES",
                "CONTRASEÑA",
                "TARJETA",
                "DNI",
                "DATOS_SENSIBLES",
                "ACCESO_BAULA",
            ],
            "ALTO",
            "Acceso a credenciales o datos personales sensibles",
        ),
        (
            ["ELIMINAR", "BORRAR", "DELETE", "PURGE", "DROP"],
            "ALTO",
            "Operación destructiva irreversible",
        ),
        (
            ["INSTALAR", "DESCARGA_APP", "INSTALL", "EJECUTAR", "EXEC", "SUBPROCESS"],
            "MEDIO",
            "Instalación o ejecución de código externo",
        ),
        (
            ["MODIFICAR", "CONFIGURAR", "ALTER", "UPDATE_CONFIG"],
            "MEDIO",
            "Modificación de configuración del sistema",
        ),
        (
            ["BACKUP", "EXPORT", "SALIDA_DATOS"],
            "MEDIO",
            "Exportación o copia de datos fuera del sistema",
        ),
        (
            ["LEER", "READ", "VIEW", "CONSULTAR", "BUSCAR"],
            "BAJO",
            "Operación de solo lectura sin modificación",
        ),
    ]

    def _analizar_riesgo(self, accion: str, descripcion: str, archivo: str) -> tuple:
        """Devuelve (nivel: str, resumen: str, permisos: str) basado en reglas + policia_v2."""
        texto = f"{accion} {descripcion} {archivo}".upper()

        nivel = "BAJO"
        motivo = "Operación estándar sin riesgos identificados"
        for keywords, niv, razon in self._RIESGO_REGLAS:
            if any(k in texto for k in keywords):
                nivel = niv
                motivo = razon
                break

        # Permisos según tipo de acción
        permisos = "sin permisos especiales"
        for clave, perm in self._PERMISOS_MAP.items():
            if clave in texto:
                permisos = perm
                break

        # Intentar análisis con agente_policia_v2 si está disponible
        analizado_por = "motor_dam (reglas)"
        try:
            from agente_policia_v2 import validar_comando

            ok, razon_policia = validar_comando(f"{accion}: {descripcion}", archivo or accion)
            if ok:
                # Policia aprueba → no subir más allá de lo que ya tenemos
                motivo = f"Policia_v2: {razon_policia[:120] if razon_policia else 'sin objeciones'}"
            else:
                # Policia rechaza → escalar a ALTO mínimo
                nivel = "ALTO"
                motivo = f"Policia_v2: {razon_policia[:120] if razon_policia else 'bloqueado'}"
            analizado_por = "policia_v2"
        except Exception:
            pass  # Sin policia: quedan las reglas

        icono = {"ALTO": "🔴", "MEDIO": "🟡", "BAJO": "🟢"}.get(nivel, "⚪")
        resumen = f"{icono} {nivel} — {motivo}"
        return nivel, resumen, permisos, analizado_por

    def solicitar_autorizacion(
        self,
        accion: str,
        descripcion: str,
        justificacion: str = "",
        solicitante: str = "URA",
        ip_origen: str = "",
        dispositivo: str = "Mac Mini M4",
        archivo_objetivo: str = "",
        origen_proceso: str = "",
        nivel: str = None,
    ) -> dict:
        """Procesa solicitud, analiza riesgo y determina nivel de seguridad."""

        ahora = datetime.now().isoformat()

        es_critica = self._es_accion_critica(accion)
        if nivel is None:
            nivel = "OMEGA" if es_critica else "ALFA"

        token = self._generar_token(accion)

        # Análisis de riesgo automático
        riesgo_nivel, riesgo_analisis, permisos_req, analizado_por = self._analizar_riesgo(
            accion, descripcion, archivo_objetivo
        )

        conn = sqlite3.connect(self.db_path, timeout=30)
        c = conn.cursor()
        c.execute(
            """
            INSERT INTO autorizaciones_dam
            (token, accion, nivel, descripcion, justificacion, solicitante,
             fecha_solicitud, estado, biometrico_requerido, ip_origen, dispositivo,
             archivo_objetivo, origen_proceso, permisos_requeridos,
             riesgo_nivel, riesgo_analisis, analizado_por)
            VALUES (?,?,?,?,?,?,?,'pendiente',?,?,?,?,?,?,?,?,?)
        """,
            (
                token,
                accion,
                nivel,
                descripcion,
                justificacion,
                solicitante,
                ahora,
                es_critica,
                ip_origen,
                dispositivo,
                archivo_objetivo,
                origen_proceso,
                permisos_req,
                riesgo_nivel,
                riesgo_analisis,
                analizado_por,
            ),
        )

        autorizacion_id = c.lastrowid
        c.execute(
            """
            INSERT INTO eventos_seguridad_dam
            (evento, nivel, detalles, resultado, timestamp)
            VALUES (?,?,?,?,?)
        """,
            (
                "SOLICITUD_AUTORIZACION",
                nivel,
                f"{accion} | riesgo={riesgo_nivel} | token={token}",
                "PENDIENTE",
                ahora,
            ),
        )
        conn.commit()
        conn.close()

        if es_critica:
            self._enviar_alerta_omega(accion, descripcion, token)

        return {
            "id": autorizacion_id,
            "token": token,
            "nivel": nivel,
            "estado": "pendiente",
            "requiere_biometrico": es_critica,
            "riesgo_nivel": riesgo_nivel,
            "riesgo_analisis": riesgo_analisis,
            "mensaje": self._mensaje_segun_nivel(nivel),
        }

    def _mensaje_segun_nivel(self, nivel: str) -> str:
        if nivel == "ALFA":
            return "📱 Notificación enviada al móvil. Click en 'Autorizar' para aprobar."
        else:
            return "🔒 ACCESO CRÍTICO - Notificación enviada al móvil. Requiere FaceID."

    def _enviar_alerta_omega(self, accion: str, descripcion: str, token: str):
        """Envía alerta de seguridad para acciones críticas al móvil"""

        notificador = get_notificador()

        # Enviar al móvil via Pushover
        resultado = notificador.enviar_validacion_movil(
            token=token, accion=accion, nivel="OMEGA", descripcion=descripcion
        )

        if resultado.get("success"):
            print(
                f"""
╔══════════════════════════════════════════════════════════════════╗
║  ⚠️  ALERTA DE SEGURIDAD - NIVEL OMEGA                           ║
╠══════════════════════════════════════════════════════════════════╣
║  ACCIÓN: {accion[:50]:<50}          ║
║  DESCRIPCIÓN: {descripcion[:48]:<48}          ║
║  TOKEN: {token:<60}    ║
║  ─────────────────────────────────────────────────────────────   ║
║  📱 Notificación enviada al móvil (Pushover)                     ║
║  🔒 Se requiere FaceID/TouchID para validar                      ║
╚══════════════════════════════════════════════════════════════════╝
            """
            )
        else:
            print(f"Error enviando notificación: {resultado.get('error')}")

    def validar_alfa(self, token: str, validado_por: str = "email") -> dict:
        """Valida autorización de nivel ALFA (email)"""
        ahora = datetime.now().isoformat()

        conn = sqlite3.connect(self.db_path, timeout=30)
        c = conn.cursor()

        # Verificar token y nivel
        c.execute(
            """
            SELECT id, token, accion, nivel, estado
            FROM autorizaciones_dam
            WHERE token = ? AND nivel = 'ALFA' AND estado = 'pendiente'
        """,
            (token,),
        )

        row = c.fetchone()

        if not row:
            conn.close()
            return {"error": "Token inválido o no encontrado"}

        # Aprobar
        c.execute(
            """
            UPDATE autorizaciones_dam
            SET estado = 'aprobado', validado_por = ?, fecha_validacion = ?
            WHERE token = ?
        """,
            (validado_por, ahora, token),
        )

        # Registrar evento
        c.execute(
            """
            INSERT INTO eventos_seguridad_dam
            (evento, nivel, detalles, resultado, timestamp)
            VALUES (?, ?, ?, ?, ?)
        """,
            ("AUTORIZACION_ALFA", "ALFA", f"Token: {token}", "APROBADO", ahora),
        )

        conn.commit()
        conn.close()

        return {
            "estado": "aprobado",
            "nivel": "ALFA",
            "mensaje": "✅ Autorizado - La acción se ejecutará",
        }

    def validar_omega(self, token: str) -> dict:
        """Valida autorización de nivel OMEGA (biometría)"""
        ahora = datetime.now().isoformat()

        # Usar autenticación biométrica real
        auth_result = autenticar(motivo="URA requiere verificación para acción crítica")

        if auth_result.get("ok"):
            conn = sqlite3.connect(self.db_path, timeout=30)
            c = conn.cursor()

            c.execute(
                """
                UPDATE autorizaciones_dam
                SET estado = 'aprobado', biometrico_validado = 1,
                    validado_por = 'BIOMETRIA', fecha_validacion = ?
                WHERE token = ?
            """,
                (ahora, token),
            )

            c.execute(
                """
                INSERT INTO eventos_seguridad_dam
                (evento, nivel, detalles, resultado, timestamp)
                VALUES (?, ?, ?, ?, ?)
            """,
                ("AUTORIZACION_OMEGA", "OMEGA", f"Token: {token}", "APROBADO_BIOMETRIA", ahora),
            )

            conn.commit()
            conn.close()

            return {
                "estado": "aprobado",
                "nivel": "OMEGA",
                "validado_por": "BIOMETRIA",
                "mensaje": "✅身份验证成功 - Acceso concedido",
            }
        else:
            # Registrar evento de denegación
            conn = sqlite3.connect(self.db_path, timeout=30)
            c = conn.cursor()
            c.execute(
                """
                INSERT INTO eventos_seguridad_dam
                (evento, nivel, detalles, resultado, timestamp)
                VALUES (?, ?, ?, ?, ?)
            """,
                (
                    "AUTORIZACION_OMEGA",
                    "OMEGA",
                    f"Token: {token} | Error: {auth_result.get('error')}",
                    "DENEGADO",
                    ahora,
                ),
            )
            conn.commit()
            conn.close()

            return {
                "estado": "denegado",
                "nivel": "OMEGA",
                "error": auth_result.get("error"),
                "mensaje": f"❌ 生物识别失败 - {auth_result.get('error', 'Error desconocido')}",
            }

    def obtener_pendientes(self) -> list:
        """Obtiene autorizaciones pendientes con contexto completo."""
        conn = sqlite3.connect(self.db_path, timeout=30)
        c = conn.cursor()
        c.execute(
            """
            SELECT id, token, accion, nivel, descripcion, fecha_solicitud,
                   biometrico_requerido, justificacion, solicitante,
                   archivo_objetivo, origen_proceso, permisos_requeridos,
                   riesgo_nivel, riesgo_analisis, analizado_por
            FROM autorizaciones_dam
            WHERE estado = 'pendiente'
              AND (pausado_hasta IS NULL OR pausado_hasta <= datetime('now','localtime'))
            ORDER BY fecha_solicitud DESC
        """
        )
        resultados = [
            {
                "id": r[0],
                "token": r[1],
                "accion": r[2],
                "nivel": r[3],
                "descripcion": r[4],
                "fecha": r[5],
                "requiere_biometrico": r[6],
                "justificacion": r[7] or "",
                "solicitante": r[8] or "URA",
                "archivo_objetivo": r[9] or "",
                "origen_proceso": r[10] or "",
                "permisos_requeridos": r[11] or "",
                "riesgo_nivel": r[12] or "DESCONOCIDO",
                "riesgo_analisis": r[13] or "",
                "analizado_por": r[14] or "",
            }
            for r in c.fetchall()
        ]
        conn.close()
        return resultados

    def obtener_eventos(self, limite: int = 20) -> list:
        """Obtiene eventos de seguridad"""
        conn = sqlite3.connect(self.db_path, timeout=30)
        c = conn.cursor()

        c.execute(
            """
            SELECT evento, nivel, detalles, resultado, timestamp
            FROM eventos_seguridad_dam
            ORDER BY id DESC LIMIT ?
        """,
            (limite,),
        )

        resultados = [
            {"evento": r[0], "nivel": r[1], "detalles": r[2], "resultado": r[3], "timestamp": r[4]}
            for r in c.fetchall()
        ]

        conn.close()
        return resultados

    def pausar(self, token: str, horas: int = 24) -> dict:
        """Pausa una autorización pendiente por N horas (no notifica hasta que expire)."""
        from datetime import timedelta

        hasta = (datetime.now() + timedelta(hours=horas)).isoformat()
        conn = sqlite3.connect(self.db_path, timeout=30)
        c = conn.cursor()
        c.execute(
            "UPDATE autorizaciones_dam SET pausado_hasta=? WHERE token=? AND estado='pendiente'",
            (hasta, token),
        )
        afectadas = c.rowcount
        c.execute(
            """
            INSERT INTO eventos_seguridad_dam (evento, nivel, detalles, resultado, timestamp)
            VALUES ('PAUSA', 'INFO', ?, 'PAUSADO', ?)
        """,
            (f"Token: {token} | hasta: {hasta[:19]}", datetime.now().isoformat()),
        )
        conn.commit()
        conn.close()
        if afectadas:
            return {"estado": "pausado", "hasta": hasta[:19], "mensaje": f"⏸ Pausado {horas}h"}
        return {"error": "Token no encontrado o no pendiente"}

    def denegar(self, token: str, motivo: str = "Denegado por el usuario") -> dict:
        """Deniega una autorización pendiente (cualquier nivel)."""
        ahora = datetime.now().isoformat()
        conn = sqlite3.connect(self.db_path, timeout=30)
        c = conn.cursor()
        c.execute(
            """
            UPDATE autorizaciones_dam
            SET estado = 'denegado', validado_por = ?, fecha_validacion = ?
            WHERE token = ? AND estado = 'pendiente'
        """,
            (motivo[:100], ahora, token),
        )
        afectadas = c.rowcount
        c.execute(
            """
            INSERT INTO eventos_seguridad_dam
            (evento, nivel, detalles, resultado, timestamp)
            VALUES ('DENEGACION', 'INFO', ?, 'DENEGADO', ?)
        """,
            (f"Token: {token} | {motivo[:80]}", ahora),
        )
        conn.commit()
        conn.close()
        if afectadas:
            return {"estado": "denegado", "mensaje": "❌ Autorización denegada"}
        return {"error": "Token no encontrado o ya procesado"}

    def obtener_estado(self) -> dict:
        """Obtiene estado del DAM"""
        conn = sqlite3.connect(self.db_path, timeout=30)
        c = conn.cursor()

        c.execute("SELECT COUNT(*) FROM autorizaciones_dam WHERE estado = 'pendiente'")
        pendientes = c.fetchone()[0]

        c.execute(
            "SELECT COUNT(*) FROM autorizaciones_dam WHERE nivel = 'OMEGA' AND estado = 'aprobado'"
        )
        omega_aprobadas = c.fetchone()[0]

        c.execute(
            "SELECT COUNT(*) FROM autorizaciones_dam WHERE nivel = 'ALFA' AND estado = 'aprobado'"
        )
        alfa_aprobadas = c.fetchone()[0]

        conn.close()

        return {
            "pendientes": pendientes,
            "omega_aprobadas": omega_aprobadas,
            "alfa_aprobadas": alfa_aprobadas,
            "sistema": "ACTIVO",
        }


def autenticar(motivo="URA requiere verificación") -> dict:
    """
    Autenticación biométrica real usando LocalAuthentication de macOS

    Args:
        motivo: Razón mostrada en el prompt de TouchID/FaceID

    Returns:
        Dict con {"ok": bool, "error": str|None}
    """
    if sys.platform != "darwin":
        return {"ok": False, "error": "Solo macOS"}

    if not LOCAL_AUTH_AVAILABLE:
        return {"ok": False, "error": "pyobjc-framework-LocalAuthentication no disponible"}

    try:
        context = LocalAuthentication.LAContext.alloc().init()
        error = None

        # Intentar primero con biometría (TouchID/FaceID)
        puede, error = context.canEvaluatePolicy_error_(
            LocalAuthentication.LAPolicyDeviceOwnerAuthenticationWithBiometrics, None
        )

        if puede:
            policy = LocalAuthentication.LAPolicyDeviceOwnerAuthenticationWithBiometrics
        else:
            # Fallback a contraseña del sistema si biometría no disponible
            puede, error = context.canEvaluatePolicy_error_(
                LocalAuthentication.LAPolicyDeviceOwnerAuthentication, None
            )
            if puede:
                policy = LocalAuthentication.LAPolicyDeviceOwnerAuthentication
            else:
                return {"ok": False, "error": f"Autenticación no disponible: {error}"}

        # Usar threading.Event para bloquear hasta respuesta del callback
        evento = threading.Event()
        resultado = {"ok": False, "error": None}

        def callback(ok, err):
            resultado.update({"ok": ok, "error": str(err) if err else None})
            evento.set()

        context.evaluatePolicy_localizedReason_reply_(policy, motivo, callback)

        # Esperar hasta 30 segundos para respuesta del usuario
        evento.wait(timeout=30)

        if not evento.is_set():
            return {"ok": False, "error": "Timeout — sin respuesta biométrica en 30s"}

        return resultado

    except Exception as e:
        return {"ok": False, "error": f"Error en autenticación: {str(e)}"}


# Instancia global
_DAM = None


def get_dam() -> MotorAutorizacionDual:
    global _DAM
    if _DAM is None:
        _DAM = MotorAutorizacionDual()
    return _DAM


if __name__ == "__main__":
    dam = get_dam()
    print("🔐 MOTOR DE AUTORIZACIÓN DUAL (DAM) - Activo")
    print(json.dumps(dam.obtener_estado(), indent=2))
