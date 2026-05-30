#!/usr/bin/env python3
"""
Certification Utils - Paso 3A
──────────────────────────────
Utilidades para panel de certificación.
"""

import logging
import shutil
from datetime import datetime
from pathlib import Path
from PyQt5.QtWidgets import QMessageBox

logger = logging.getLogger(__name__)


def open_certification_panel(window):
    """Abrir panel de certificación con protocolo de 4 niveles."""
    try:
        # Ejecutar protocolo de certificación de 4 niveles
        from core.cloud_backup import get_cloud_backup

        # Ruta del proyecto
        project_path = Path(__file__).parent

        # Rutas de backup
        library_backup_path = Path.home() / "Library" / "URA_DNA_BACKUP"
        icloud_backup_path = (
            Path.home() / "Library/Mobile Documents/com~apple~CloudDocs/URA_DNA_BACKUP"
        )

        # Timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"URA_Certified_Backup_{timestamp}"

        QMessageBox.information(
            window,
            "🏭 Protocolo de Certificación",
            f"⚙️ Ejecutando protocolo de 4 niveles...\n\n"
            f"📁 Backup local: {library_backup_path / backup_name}\n"
            f"☁️ Backup iCloud: {icloud_backup_path / backup_name}\n\n"
            f"Este proceso puede tomar varios minutos.",
        )

        # 1. Copia local en la biblioteca
        logger.info(f"Creando backup local en {library_backup_path}")
        local_backup = library_backup_path / backup_name
        if local_backup.exists():
            shutil.rmtree(local_backup)
        shutil.copytree(project_path, local_backup)
        logger.info(f"Backup local completado: {len(list(local_backup.rglob('*')))} archivos")

        # 2. Copia automática a iCloud
        logger.info(f"Creando backup iCloud en {icloud_backup_path}")
        cloud_backup = get_cloud_backup()
        result = cloud_backup.perform_backup_with_verification(
            source_path=project_path, backup_name=backup_name
        )

        if result["success"]:
            sync_status = result["sync_status"]
            integrity_check = result["integrity_check"]

            # Determinar icono y color según estado de sincronización
            status_icon = sync_status["icon"]
            status_message = sync_status["message"]

            # Construir mensaje de confirmación
            confirmation_msg = (
                f"🎉 Protocolo de 4 niveles completado con éxito.\n\n"
                f"📦 Backup local: {local_backup}\n"
                f"   ✅ {len(list(local_backup.rglob('*')))} archivos\n\n"
                f"☁️ Backup iCloud: {result['backup_path']}\n"
                f"   ✅ Integridad: {integrity_check['message']}\n"
                f"   {status_icon} Estado iCloud: {status_message}\n\n"
            )

            if result["sync_id"]:
                confirmation_msg += f"🔑 Sync ID (Apple): {result['sync_id']}\n\n"

            confirmation_msg += "📊 Ambas copias han sido creadas. La copia de iCloud está siendo sincronizada con Apple."

            QMessageBox.information(
                window, f"{status_icon} Certificación Completada", confirmation_msg
            )
        else:
            # Backup local exitoso, pero iCloud falló
            QMessageBox.warning(
                window,
                "⚠️ Backup Parcial",
                f"✅ Backup local completado: {local_backup}\n\n"
                f"❌ Error backup iCloud: {result.get('error', 'Error desconocido')}\n\n"
                f"La copia local está disponible, pero la sincronización con iCloud falló.",
            )

    except Exception as e:
        QMessageBox.warning(window, "❌ Error", f"Error en certificación: {str(e)}")
