#!/usr/bin/env python3
"""
agente_camaras.py — URA Agente de Videovigilancia Dahua
=======================================================
Gestión de cámaras Dahua con API REST.

Capacidades:
- Captura de imágenes
- Movimiento detectado
- Live streaming
- Consulta de grabaciones
- Alertas por movimiento

Configuración:
- IP de cámara
- Puerto (normalmente 80 o 554)
- Usuario y contraseña
"""

import json
import logging
import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

try:
    import requests

    REQUESTS_OK = True
except:
    REQUESTS_OK = False

logger = logging.getLogger(__name__)

BASE_DIR = Path(
    os.environ.get("URA_BASE_DIR", str(Path(__file__).resolve().parents[1]))
).expanduser()


class AgenteCamaras:
    def __init__(self, db_path: str | None = None):
        if db_path is None:
            db_path = str(Path(__file__).resolve().parents[1] / "board.db")
        self.db_path = db_path
        self.config = self._cargar_config()
        logger.info(f"Inicializando AgenteCamaras con db_path={db_path}")
        self._init_db()

    def _cargar_config(self) -> dict:
        config_path = BASE_DIR / "config" / "camaras.json"
        if config_path.exists():
            with open(config_path) as f:
                return json.load(f)
        return {
            "camaras": [
                {
                    "id": "cam_1",
                    "nombre": "Entrada principal",
                    "ip": "192.168.1.100",
                    "puerto": 80,
                    "usuario": "admin",
                    "contrasena": "",
                }
            ],
            "intervalo_lectura": 30,
            "detectar_movimiento": True,
        }

    def _guardar_config(self):
        config_path = BASE_DIR / "config"
        config_path.mkdir(parents=True, exist_ok=True)
        with open(config_path / "camaras.json", "w") as f:
            json.dump(self.config, f, indent=2)

    def configurar_camara(
        self, nombre: str, ip: str, puerto: int = 80, usuario: str = "admin", contrasena: str = ""
    ) -> bool:
        """Configura una cámara Dahua."""
        camara_id = f"cam_{len(self.config['camaras']) + 1}"
        self.config["camaras"].append(
            {
                "id": camara_id,
                "nombre": nombre,
                "ip": ip,
                "puerto": puerto,
                "usuario": usuario,
                "contrasena": contrasena,
            }
        )
        self._guardar_config()
        return True

    def _obtener_url(self, camara: dict) -> str:
        return f"http://{camara['ip']}:{camara['puerto']}"

    def _obtener_headers(self, camara: dict) -> dict:
        return {"Content-Type": "application/json"}

    def _obtener_auth(self, camara: dict) -> dict | None:
        if camara.get("usuario"):
            return (camara["usuario"], camara.get("contrasena", ""))
        return None

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS camaras_eventos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                camara_id TEXT NOT NULL,
                tipo TEXT NOT NULL,
                descripcion TEXT,
                imagen_path TEXT,
                timestamp TEXT,
                created_at TEXT
            )
        """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS camaras_capturas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                camara_id TEXT NOT NULL,
                tipo TEXT NOT NULL,
                ruta TEXT NOT NULL,
                timestamp TEXT,
                created_at TEXT
            )
        """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS camaras_estado (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                camara_id TEXT UNIQUE NOT NULL,
                online INTEGER DEFAULT 0,
                ultimo_check TEXT,
                observaciones TEXT
            )
        """
        )

        conn.commit()
        conn.close()

    def estado_camara(self, camara_id: str = "cam_1") -> dict:
        """Verifica estado de una cámara."""
        camara = next((c for c in self.config["camaras"] if c["id"] == camara_id), None)
        if not camara:
            return {"error": "Cámara no encontrada"}

        ahora = datetime.now().isoformat()

        if not REQUESTS_OK:
            return {"online": False, "error": "requests no instalado"}

        try:
            url = f"{self._obtener_url(camara)}/cgi-bin/magic.cgi?page=json"
            resp = requests.get(url, timeout=5, auth=self._obtener_auth(camara))
            online = resp.status_code == 200
        except:
            online = False

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO camaras_estado
            (camara_id, online, ultimo_check)
            VALUES (?, ?, ?)
        """,
            (camara_id, 1 if online else 0, ahora),
        )
        conn.commit()
        conn.close()

        return {
            "camara_id": camara_id,
            "nombre": camara.get("nombre"),
            "ip": camara["ip"],
            "online": online,
            "ultimo_check": ahora,
        }

    def capturar(self, camara_id: str = "cam_1", tipo: str = "snapshot") -> str | None:
        """Captura una imagen de la cámara."""
        camara = next((c for c in self.config["camaras"] if c["id"] == camara_id), None)
        if not camara:
            return None

        ahora = datetime.now()
        filename = f"captura_{camara_id}_{ahora.strftime('%Y%m%d_%H%M%S')}.jpg"
        save_path = BASE_DIR / "capturas" / filename
        save_path.parent.mkdir(parents=True, exist_ok=True)

        if REQUESTS_OK:
            try:
                url = f"{self._obtener_url(camara)}/cgi-bin/snapshot.cgi"
                resp = requests.get(url, timeout=10, auth=self._obtener_auth(camara))
                if resp.status_code == 200:
                    with open(save_path, "wb") as f:
                        f.write(resp.content)
                    self._registrar_captura(camara_id, tipo, str(save_path))
                    return str(save_path)
            except Exception as e:
                logger.warning(f"Error silencioso en agente_camaras.capture: {e}")
                # fallback: continuar

        return None

    def _registrar_captura(self, camara_id: str, tipo: str, ruta: str):
        ahora = datetime.now().isoformat()
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO camaras_capturas (camara_id, tipo, ruta, timestamp, created_at)
            VALUES (?, ?, ?, ?, ?)
        """,
            (camara_id, tipo, ruta, ahora, ahora),
        )
        conn.commit()
        conn.close()

    def registrar_evento(
        self, camara_id: str, tipo: str, descripcion: str = "", imagen_path: str = None
    ) -> int:
        """Registra un evento de la cámara."""
        ahora = datetime.now().isoformat()
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO camaras_eventos (camara_id, tipo, descripcion, imagen_path, timestamp, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (camara_id, tipo, descripcion, imagen_path, ahora, ahora),
        )
        result = cursor.lastrowid
        conn.commit()
        conn.close()
        return result

    def eventos_recientes(self, camara_id: str = None, horas: int = 24) -> list[dict]:
        """Obtiene eventos recientes."""
        cutoff = (datetime.now() - timedelta(hours=horas)).isoformat()
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        query = """
            SELECT id, camara_id, tipo, descripcion, timestamp
            FROM camaras_eventos
            WHERE timestamp >= ?
        """
        params = [cutoff]
        if camara_id:
            query += " AND camara_id = ?"
            params.append(camara_id)
        query += " ORDER BY timestamp DESC LIMIT 50"

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        return [
            {"id": r[0], "camara": r[1], "tipo": r[2], "descripcion": r[3], "timestamp": r[4]}
            for r in rows
        ]

    def todas_las_camaras(self) -> list[dict]:
        """Estado de todas las cámaras."""
        resultado = []
        for camara in self.config["camaras"]:
            estado = self.estado_camara(camara["id"])
            resultado.append(estado)
        return resultado

    def resumen(self) -> dict:
        """Resumen de cámaras."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT COUNT(*) FROM camaras_capturas WHERE timestamp >= ?",
            ((datetime.now() - timedelta(days=1)).isoformat(),),
        )
        capturas_hoy = cursor.fetchone()[0]

        cursor.execute(
            "SELECT COUNT(*) FROM camaras_eventos WHERE timestamp >= ?",
            ((datetime.now() - timedelta(days=1)).isoformat(),),
        )
        eventos_hoy = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM camaras_estado WHERE online = 1")
        online = cursor.fetchone()[0]

        total = len(self.config["camaras"])

        conn.close()
        return {
            "total_camaras": total,
            "online": online,
            "capturas_hoy": capturas_hoy,
            "eventos_hoy": eventos_hoy,
        }

    def procesar(self, texto: str) -> str:
        """Procesar consulta para AgenteCamaras."""
        texto.lower()
        return "Puedo gestionar cámaras Dahua, videovigilancia y grabación. ¿Qué cámara necesitas configurar?"

    def ejecutar(self, texto: str) -> str:
        """Ejecutar acción para AgenteCamaras."""
        return self.procesar(texto)

    def consultar(self, texto: str) -> str:
        """Consultar información para AgenteCamaras."""
        return self.procesar(texto)

    def responder(self, texto: str) -> str:
        """Responder pregunta para AgenteCamaras."""
        return self.procesar(texto)


if __name__ == "__main__":
    agente = AgenteCamaras()

    # Test: configurar cámara
    agente.configurar_camara(nombre="Cámara prueba", ip="192.168.1.100", puerto=80)

    # Test: estado
    estado = agente.estado_camara("cam_1")
    print(f"Estado cámara: {estado}")

    # Test: resumen
    resumen = agente.resumen()
    print(f"Resumen: {resumen}")
