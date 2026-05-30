#!/usr/bin/env python3
"""
URA - App Handler
Maneja comandos de aplicaciones
"""

import logging
import re

logger = logging.getLogger(__name__)


def handle_app_command(context, message: str):
    """
    Manejar comando de aplicaciones

    Args:
        context: Contexto de la ventana principal (self)
        message: Mensaje del usuario
    """
    try:
        from core.mac_apps_integration import MacAppsIntegration
        from core.app_automation import AppAutomation

        # Crear integración
        apps_integration = MacAppsIntegration()
        AppAutomation()

        # Detectar tipo de comando
        if "abre" in message.lower():
            # Abrir app
            app_match = re.search(r"abre\s+(\w+)", message, re.IGNORECASE)
            if app_match:
                app_name = app_match.group(1)
                context.chat_ura(f"🚀 Abriendo {app_name}...")
                result = apps_integration.open_app(app_name)

                if result["success"]:
                    context.chat_ura(f"✅ {app_name} abierto")
                else:
                    context.chat_ura(f"❌ {result.get('error', 'Error desconocido')}")

        elif "dame permiso para" in message.lower():
            # Otorgar permiso
            app_match = re.search(r"dame\s+permiso\s+para\s+(\w+)", message, re.IGNORECASE)
            if app_match:
                app_name = app_match.group(1)
                context.chat_ura(f"🔓 Otorgando permiso para {app_name}...")
                result = apps_integration.grant_permission(app_name)

                if result["success"]:
                    context.chat_ura(f"✅ Permiso otorgado para {app_name}")
                    context.chat_ura(f"📋 Alcance: {', '.join(result.get('scope', []))}")
                else:
                    context.chat_ura(f"❌ {result.get('error', 'Error desconocido')}")

        elif "busca en" in message.lower():
            # Buscar en app
            app_match = re.search(r"busca\s+en\s+(\w+)\s+(.+)", message, re.IGNORECASE)
            if app_match:
                app_name = app_match.group(1)
                query = app_match.group(2)
                context.chat_ura(f"🔍 Buscando '{query}' en {app_name}...")
                result = apps_integration.search_in_app(app_name, query)

                if result["success"]:
                    context.chat_ura(f"✅ {result.get('message', 'Búsqueda completada')}")
                else:
                    context.chat_ura(f"❌ {result.get('error', 'Error desconocido')}")

        elif "copia de" in message.lower() and "a" in message.lower():
            # Copiar entre apps
            match = re.search(r"copia\s+de\s+(\w+)\s+a\s+(\w+)", message, re.IGNORECASE)
            if match:
                source_app = match.group(1)
                target_app = match.group(2)
                context.chat_ura(f"📋 Copiando de {source_app} a {target_app}...")
                result = apps_integration.copy_between_apps(source_app, target_app)

                if result["success"]:
                    context.chat_ura(f"✅ {result.get('message', 'Copia completada')}")
                else:
                    context.chat_ura(f"❌ {result.get('error', 'Error desconocido')}")

        else:
            context.chat_ura(
                "⚠️ No reconocí el comando. Prueba: 'abre [app]', 'dame permiso para [app]', 'busca en [app] [algo]'"
            )

        context.hide_progress()
    except Exception as e:
        logger.error(f"Error en comando de apps: {e}")
        context.chat_alert(f"❌ Error en comando de apps: {e}")
        context.hide_progress()
