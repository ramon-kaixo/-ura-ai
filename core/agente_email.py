#!/usr/bin/env python3
"""
agente_email.py — URA Agente de Correo y Documentos
===================================================
Gestión de correo electrónico y documentación.

Capacidades:
- Lectura de correos
- Clasificación automática
- Alertas importantes
- Gestión de adjuntos
- Resúmenes diarios

Requiere: IMAP/SMTP config o Gmail API
"""

import contextlib
import email
import imaplib
import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path

try:
    EMAIL_OK = True
except:
    EMAIL_OK = False

BASE_DIR = Path(
    os.environ.get("URA_BASE_DIR", str(Path(__file__).resolve().parents[1]))
).expanduser()


class AgenteEmail:
    def __init__(self, db_path: str | None = None):
        if db_path is None:
            db_path = str(Path(__file__).resolve().parents[1] / "board.db")
        self.db_path = db_path
        self.config = self._cargar_config()
        self._init_db()

    def _cargar_config(self) -> dict:
        """Carga configuración de correo."""
        config_path = BASE_DIR / "config" / "email.json"
        if config_path.exists():
            with open(config_path) as f:
                return json.load(f)
        return {"imap_server": "", "smtp_server": "", "email": "", "password": ""}

    def _guardar_config(self):
        """Guarda configuración de correo."""
        config_path = BASE_DIR / "config"
        config_path.mkdir(parents=True, exist_ok=True)
        with open(config_path / "email.json", "w") as f:
            json.dump(self.config, f, indent=2)

    def configurar(self, imap_server: str, smtp_server: str, email: str, password: str):
        """Configura cuenta de correo."""
        self.config = {
            "imap_server": imap_server,
            "smtp_server": smtp_server,
            "email": email,
            "password": password,
        }
        self._guardar_config()
        return True

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS email_mensajes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id TEXT UNIQUE,
                de TEXT,
                para TEXT,
                asunto TEXT,
                cuerpo TEXT,
                fecha TEXT,
                leido INTEGER DEFAULT 0,
                importante INTEGER DEFAULT 0,
                categoria TEXT,
                etiquetas TEXT,
                adjuntos TEXT,
                created_at TEXT
            )
        """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS email_reglas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                filtro TEXT NOT NULL,
                accion TEXT NOT NULL,
                categoria TEXT,
                activa INTEGER DEFAULT 1
            )
        """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS email_alertas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                palabras_clave TEXT NOT NULL,
                mensaje TEXT,
                activa INTEGER DEFAULT 1
            )
        """
        )

        conn.commit()
        conn.close()

    def conectar(self) -> bool:
        """Conecta al servidor IMAP."""
        if not self.config.get("imap_server"):
            return False
        try:
            self.mail = imaplib.IMAP4_SSL(self.config["imap_server"])
            self.mail.login(self.config["email"], self.config["password"])
            return True
        except Exception:
            return False

    def desconectar(self):
        """Desconecta del servidor."""
        with contextlib.suppress(BaseException):
            self.mail.logout()

    def sincronizar(self, carpeta: str = "INBOX", limite: int = 50) -> int:
        """Sincroniza correos desde el servidor."""
        if not self.conectar():
            return 0

        count = 0
        try:
            self.mail.select(carpeta)
            _, msgs = self.mail.search(None, "ALL")

            for num in msgs[0].split()[-limite:]:
                _, data = self.mail.fetch(num, "(RFC822)")
                msg = email.message_from_bytes(data[0][1])

                message_id = msg.get("Message-ID", "")
                de = msg.get("From", "")
                para = msg.get("To", "")
                asunto = msg.get("Subject", "")
                fecha = msg.get("Date", "")

                cuerpo = ""
                if msg.is_multipart():
                    for part in msg.walk():
                        if part.get_content_type() == "text/plain":
                            cuerpo = part.get_payload()
                            break
                else:
                    cuerpo = msg.get_payload()

                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO email_mensajes
                    (message_id, de, para, asunto, cuerpo, fecha, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                    (message_id, de, para, asunto, cuerpo, fecha, datetime.now().isoformat()),
                )
                if cursor.rowcount > 0:
                    count += 1
                conn.commit()
                conn.close()

        finally:
            self.desconectar()

        return count

    def buscar(self, query: str, limite: int = 20) -> list[dict]:
        """Busca correos."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, de, asunto, fecha, leido, importante, categoria
            FROM email_mensajes
            WHERE asunto LIKE ? OR cuerpo LIKE ? OR de LIKE ?
            ORDER BY fecha DESC
            LIMIT ?
        """,
            (f"%{query}%", f"%{query}%", f"%{query}%", limite),
        )
        rows = cursor.fetchall()
        conn.close()
        return [
            {
                "id": r[0],
                "de": r[1],
                "asunto": r[2],
                "fecha": r[3],
                "leido": bool(r[4]),
                "importante": bool(r[5]),
                "categoria": r[6],
            }
            for r in rows
        ]

    def obtener(self, mensaje_id: int) -> dict | None:
        """Obtiene un correo completo."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, de, para, asunto, cuerpo, fecha, leido, importante, categoria
            FROM email_mensajes WHERE id = ?
        """,
            (mensaje_id,),
        )
        row = cursor.fetchone()
        conn.close()
        if row:
            return {
                "id": row[0],
                "de": row[1],
                "para": row[2],
                "asunto": row[3],
                "cuerpo": row[4],
                "fecha": row[5],
                "leido": bool(row[6]),
                "importante": bool(row[7]),
                "categoria": row[8],
            }
        return None

    def marcar_importante(self, mensaje_id: int) -> bool:
        """Marca correo como importante."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("UPDATE email_mensajes SET importante = 1 WHERE id = ?", (mensaje_id,))
        conn.commit()
        result = cursor.rowcount > 0
        conn.close()
        return result

    def importantes(self) -> list[dict]:
        """Lista correos importantes."""
        return self.buscar("", limite=100)

    def resumen(self) -> dict:
        """Resumen de correos."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM email_mensajes WHERE leido = 0")
        sin_leer = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM email_mensajes WHERE importante = 1")
        importantes = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM email_mensajes")
        total = cursor.fetchone()[0]
        conn.close()
        return {"sin_leer": sin_leer, "importantes": importantes, "total": total}

    def procesar(self, texto: str) -> str:
        """Procesar consulta para AgenteEmail."""
        texto.lower()
        return "Puedo enviar correos, gestionar bandeja y buzones. ¿Qué email necesitas enviar?"

    def ejecutar(self, texto: str) -> str:
        """Ejecutar acción para AgenteEmail."""
        return self.procesar(texto)

    def consultar(self, texto: str) -> str:
        """Consultar información para AgenteEmail."""
        return self.procesar(texto)

    def responder(self, texto: str) -> str:
        """Responder pregunta para AgenteEmail."""
        return self.procesar(texto)


_EMAIL = None


def get_email() -> AgenteEmail:
    global _EMAIL
    if _EMAIL is None:
        _EMAIL = AgenteEmail()
    return _EMAIL
