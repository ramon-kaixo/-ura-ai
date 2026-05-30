#!/usr/bin/env python3
"""
URA - Install Handler
Maneja comandos de instalación en sandbox
"""

import logging
import re

logger = logging.getLogger(__name__)


def handle_sandbox_install(context, message: str):
    """
    Manejar comando de instalación en sandbox

    Args:
        context: Contexto de la ventana principal (self)
        message: Mensaje del usuario
    """
    try:
        from core.sandbox_installer import SandboxInstaller

        # Verificar permiso
        if context.PERMISSIONS_AVAILABLE and context.permission_manager:
            from core.automation_security import ActionType

            perm_check = context.permission_manager.can_execute(ActionType.INSTALL_SANDBOX)
            if not perm_check["allowed"]:
                context.chat_ura(f"⚠️ {perm_check['reason']}")
                context.hide_progress()
                return

        # Extraer nombre del paquete
        package_match = re.search(r"instala\s+(\S+)", message, re.IGNORECASE)
        if not package_match:
            context.chat_ura("❌ No detecté el nombre del paquete a instalar")
            context.hide_progress()
            return

        package_name = package_match.group(1)

        context.chat_ura(f"📦 Instalando {package_name} en sandbox...")

        # Crear instalador
        installer = SandboxInstaller()

        # Instalar en sandbox
        result = installer.install_package(package_name, auto_confirm=True)

        # Mostrar resultados
        for step in result["steps"]:
            context.chat_ura(step)

        if result["success"]:
            context.chat_ura(f"✅ {package_name} instalado en entorno aislado")
            context.chat_ura("📝 Registrado en URA_CHANGELOG.md")

            # Listar paquetes instalados
            packages = installer.get_installed_packages()
            if packages:
                context.chat_ura(f"📦 Paquetes en sandbox: {', '.join(packages[:5])}")
        else:
            context.chat_ura("❌ Error en instalación")
            for error in result["errors"]:
                context.chat_ura(f"Error: {error}")

        context.hide_progress()
    except Exception as e:
        logger.error(f"Error en instalación sandbox: {e}")
        context.chat_alert(f"❌ Error en instalación sandbox: {e}")
        context.hide_progress()
