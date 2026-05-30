#!/usr/bin/env python3
"""
agente_backup.py — Gestiona y verifica backups
"""

import logging

logger = logging.getLogger(__name__)
import sqlite3
import subprocess
from datetime import datetime
from pathlib import Path

SISTEMA = Path(__file__).parent.parent
DB = SISTEMA / "board.db"
LOG = SISTEMA / "logs" / "backup.log"
LOG.parent.mkdir(exist_ok=True)

ULTIMO_BACKUP_FILE = SISTEMA / ".ultimo_backup"


def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG, "a") as f:
        f.write(f"[{ts}] {msg}\n")


def obtener_ultimo_backup():
    try:
        with open(ULTIMO_BACKUP_FILE) as f:
            return datetime.fromisoformat(f.read().strip())
    except:
        return None


def guardar_ultimo_backup():
    with open(ULTIMO_BACKUP_FILE, "w") as f:
        f.write(datetime.now().isoformat())


def verificar_backup_restic():
    try:
        result = subprocess.run(
            ["restic", "snapshots", "--latest", "1", "--json"],
            capture_output=True,
            text=True,
            cwd=str(SISTEMA),
            timeout=30,
        )
        if result.returncode == 0:
            import json

            snapshots = json.loads(result.stdout)
            if snapshots:
                ultimo = snapshots[0]
                tiempo = datetime.fromisoformat(ultimo["time"].replace("Z", "+00:00"))
                return tiempo
    except Exception as e:
        logger.warning(f"Error silencioso en agente_backup.parse_time: {e}")
        # fallback: devolver None
    return None


def verificar_backup_manual():
    backups_dir = SISTEMA / "backups"
    if not backups_dir.exists():
        return None

    archivos = list(backups_dir.glob("backup_*.tar.gz")) + list(backups_dir.glob("*.zip"))
    if archivos:
        mas_reciente = max(archivos, key=lambda p: p.stat().st_mtime)
        return datetime.fromtimestamp(mas_reciente.stat().st_mtime)
    return None


def estado_backup():
    ultimo = obtener_ultimo_backup()
    if not ultimo:
        return {
            "ultimo": None,
            "horas": None,
            "alerta": True,
            "mensaje": "No hay registro de último backup",
        }

    horas = (datetime.now() - ultimo).total_seconds() / 3600

    return {
        "ultimo": ultimo,
        "horas": horas,
        "alerta": horas > 24,
        "mensaje": f"Último backup hace {horas:.1f} horas",
    }


def hacer_backup_emergency():
    log("INICIANDO BACKUP DE EMERGENCIA")
    try:
        backup_dir = SISTEMA / "backups"
        backup_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        salida = backup_dir / f"emergency_{timestamp}.db"

        conn = sqlite3.connect(DB)
        # Usar backup en lugar de VACUUM INTO para evitar SQL inyectado
        destino = sqlite3.connect(str(salida))
        conn.backup(destino)
        destino.close()
        conn.close()

        guardar_ultimo_backup()
        log(f"BACKUP EMERGENCIA OK: {salida}")
        return True
    except Exception as e:
        log(f"ERROR BACKUP: {e}")
        return False


def generar_informe():
    estado = estado_backup()
    restic = verificar_backup_restic()

    alerta = ""
    if estado["alerta"]:
        alerta = "\n⚠️  ALERTA: Backup hace más de 24 horas"

    return f"""
╔══════════════════════════════════════════════════════╗
║           INFORME DE BACKUP — {datetime.now().strftime("%Y-%m-%d %H:%M")}
╠══════════════════════════════════════════════════════╣
║  Estado:        {estado["mensaje"]}
║  Restic:        {"OK" if restic else "No disponible"}
║  Archivo DB:    {DB.stat().st_size / (1024 * 1024):.1f} MB{alerta}
╚══════════════════════════════════════════════════════╝
"""


class AgenteBackup:
    """Agente para gestión de backups."""

    def __init__(self):
        """Inicializar agente."""
        self.nombre = "Agente Backup"

    def procesar(self, texto: str) -> str:
        """Procesar consulta para backup."""
        texto_lower = texto.lower()

        if "estado" in texto_lower or "status" in texto_lower:
            estado = estado_backup()
            return f"Estado del backup: {estado['mensaje']}"
        elif "informe" in texto_lower or "report" in texto_lower:
            return generar_informe()
        elif "hacer" in texto_lower or "crear" in texto_lower or "emergency" in texto_lower:
            resultado = hacer_backup_emergency()
            if resultado:
                return "Backup de emergencia creado exitosamente."
            else:
                return "Error al crear backup de emergencia."
        else:
            return generar_informe()

    def ejecutar(self, texto: str) -> str:
        """Ejecutar acción para backup."""
        return self.procesar(texto)

    def consultar(self, texto: str) -> str:
        """Consultar información para backup."""
        return self.procesar(texto)

    def responder(self, texto: str) -> str:
        """Responder pregunta para backup."""
        return self.procesar(texto)


if __name__ == "__main__":
    import sys

    if "--informe" in sys.argv or "--report" in sys.argv:
        print(generar_informe())
    elif "--emergency" in sys.argv:
        hacer_backup_emergency()
    elif "--verify" in sys.argv:
        print(estado_backup())
    else:
        estado = estado_backup()
        if estado["alerta"]:
            print("⚠️  " + estado["mensaje"])
        else:
            print("✅ " + estado["mensaje"])
