#!/usr/bin/env python3
"""
agente_conciencia.py — URA Conciencia del Sistema
================================================
URA es consciente de su entorno completo.

Responsabilidades:
1. Escanear aplicaciones instaladas
2. Detectar actualizaciones pendientes
3. Comparar con lista de "debería tener"
4. Proponer acciones automáticamente
5. Alertar si algo no funciona

No se queda callado. Si ve algo, actúa o pregunta.
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path


class AgenteConciencia:
    APPS_ESPERADAS = {
        "desarrollo": ["VS Code", "Cursor", "GitHub Desktop", "Postman", "DBeaver"],
        "productividad": ["LibreOffice", "Thunderbird"],
        "creatividad": ["GIMP", "Inkscape", "Figma"],
        "seguridad": ["Malwarebytes", "Little Snitch", "BlockBlock"],
        "utilidades": ["AppCleaner", "OnyX", "iTerm"],
        "red": ["Wireshark"],
        "datos": ["JupyterLab", "RStudio"],
        "bar": ["LibreOffice", "Thunderbird"],
    }

    def __init__(self, db_path: str | None = None):
        if db_path is None:
            db_path = str(Path(__file__).resolve().parents[1] / "board.db")
        self.db_path = db_path
        self.home = Path.home()
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS conciencia_apps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT UNIQUE NOT NULL,
                categoria TEXT,
                instalado INTEGER DEFAULT 0,
                version TEXT,
                fecha_check TEXT,
                prioridad INTEGER DEFAULT 5
            )
        """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS conciencia_alertas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tipo TEXT NOT NULL,
                mensaje TEXT NOT NULL,
                solucion TEXT,
                resuelta INTEGER DEFAULT 0,
                creada_en TEXT
            )
        """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS conciencia_informe (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tipo TEXT NOT NULL,
                datos TEXT,
                creado_en TEXT
            )
        """
        )

        conn.commit()
        conn.close()

    def escanear_aplicaciones(self) -> dict:
        """Escanea todas las aplicaciones instaladas."""
        apps_installed = {}

        for app in (self.home / "Applications").glob("*.app"):
            nombre = app.name.replace(".app", "")
            apps_installed[nombre] = str(app)

        for app in Path("/Applications").glob("*.app"):
            nombre = app.name.replace(".app", "")
            apps_installed[nombre] = str(app)

        for app in (self.home / "Library" / "Applications").glob("*.app"):
            nombre = app.name.replace(".app", "")
            if nombre not in apps_installed:
                apps_installed[nombre] = str(app)

        return apps_installed

    def escanear_descargas(self) -> list[dict]:
        """Escanea carpetas de descargas."""
        descargas = []
        folders = [
            self.home / "Downloads",
            self.home / "ura_system_sandbox" / "descargas",
        ]

        for folder in folders:
            if folder.exists():
                for f in folder.rglob("*"):
                    if f.suffix.lower() in [".dmg", ".pkg", ".zip"]:
                        size = f.stat().st_size / (1024 * 1024)
                        descargas.append(
                            {"nombre": f.name, "ruta": str(f), "size_mb": round(size, 1)}
                        )

        return descargas

    def verificar_estado(self) -> dict:
        """Verificación completa del estado del sistema."""
        ahora = datetime.now().isoformat()
        apps = self.escanear_aplicaciones()
        descargas = self.escanear_descargas()

        estado = {
            "timestamp": ahora,
            "apps_instaladas": len(apps),
            "descargas_pendientes": len(descargas),
            "apps_detectadas": sorted(apps.keys()),
            "descargas_detectadas": descargas[:20],
            "alertas": [],
        }

        categoria_flat = []
        for cats in self.APPS_ESPERADAS.values():
            categoria_flat.extend(cats)

        faltantes = []
        for app in categoria_flat:
            if app not in apps:
                faltantes.append(app)

        if faltantes:
            estado["alertas"].append(
                {
                    "tipo": "apps_faltantes",
                    "mensaje": f"Aplicaciones recomendadas no instaladas: {len(faltantes)}",
                    "apps": faltantes,
                }
            )

        if descargas:
            estado["alertas"].append(
                {
                    "tipo": "descargas_sin_instalar",
                    "mensaje": f"Hay {len(descargas)} archivos de instalación sin procesar",
                    "urgencia": "media",
                }
            )

        disk = self._check_disk()
        if disk["libre_gb"] < 20:
            estado["alertas"].append(
                {
                    "tipo": "disco_bajo",
                    "mensaje": f"Solo {disk['libre_gb']}GB libres",
                    "urgencia": "alta",
                }
            )

        return estado

    def _check_disk(self) -> dict:
        """Verifica espacio en disco."""
        try:
            import shutil

            total, usado, libre = shutil.disk_usage("/")
            return {
                "total_gb": round(total / (1024**3), 1),
                "usado_gb": round(usado / (1024**3), 1),
                "libre_gb": round(libre / (1024**3), 1),
            }
        except:
            return {"libre_gb": 0}

    def guardar_informe(self, tipo: str, datos: dict):
        """Guarda un informe de estado."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO conciencia_informe (tipo, datos, creado_en)
            VALUES (?, ?, ?)
        """,
            (tipo, json.dumps(datos), datetime.now().isoformat()),
        )
        conn.commit()
        conn.close()

    def crear_alerta(self, tipo: str, mensaje: str, solucion: str = "") -> int:
        """Crea una alerta para revisión."""
        ahora = datetime.now().isoformat()
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO conciencia_alertas (tipo, mensaje, solucion, creada_en)
            VALUES (?, ?, ?, ?)
        """,
            (tipo, mensaje, solucion, ahora),
        )
        result = cursor.lastrowid
        conn.commit()
        conn.close()
        return result

    def alertas_pendientes(self) -> list[dict]:
        """Alertas sin resolver."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, tipo, mensaje, solucion, creada_en
            FROM conciencia_alertas
            WHERE resuelta = 0
            ORDER BY creada_en DESC
            LIMIT 20
        """
        )
        rows = cursor.fetchall()
        conn.close()
        return [
            {"id": r[0], "tipo": r[1], "mensaje": r[2], "solucion": r[3], "creada": r[4]}
            for r in rows
        ]

    def resolver_alerta(self, alerta_id: int) -> bool:
        """Marca alerta como resuelta."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("UPDATE conciencia_alertas SET resuelta = 1 WHERE id = ?", (alerta_id,))
        conn.commit()
        result = cursor.rowcount > 0
        conn.close()
        return result

    def resumen(self) -> str:
        """Resumen legible del estado del sistema."""
        estado = self.verificar_estado()

        resumen = f"""
══════════════════════════════════════════════════
URA - CONCIENCIA DEL SISTEMA
══════════════════════════════════════════════════

📱 Aplicaciones instaladas: {estado["apps_instaladas"]}
📦 Descargas pendientes: {estado["descargas_pendientes"]}
💾 Espacio libre: {self._check_disk()["libre_gb"]} GB

"""
        if estado["alertas"]:
            resumen += "⚠️  ALERTAS:\n"
            for alerta in estado["alertas"]:
                resumen += f"   • {alerta['mensaje']}\n"

        resumen += """
══════════════════════════════════════════════════
"""
        return resumen

    def procesar(self, texto: str) -> str:
        """Procesar consulta para AgenteConciencia."""
        texto.lower()
        return "Soy URA, tengo autoconocimiento y memoria. ¿Qué necesitas saber sobre mí?"

    def ejecutar(self, texto: str) -> str:
        """Ejecutar acción para AgenteConciencia."""
        return self.procesar(texto)

    def consultar(self, texto: str) -> str:
        """Consultar información para AgenteConciencia."""
        return self.procesar(texto)

    def responder(self, texto: str) -> str:
        """Responder pregunta para AgenteConciencia."""
        return self.procesar(texto)

    def execute(self, *args, **kwargs) -> dict:
        """
        Método execute estándar para AgenteConciencia.

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


_CONCIENCIA = None


def get_conciencia() -> AgenteConciencia:
    global _CONCIENCIA
    if _CONCIENCIA is None:
        _CONCIENCIA = AgenteConciencia()
    return _CONCIENCIA
