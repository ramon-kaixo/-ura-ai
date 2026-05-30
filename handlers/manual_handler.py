#!/usr/bin/env python3
"""
URA - Manual Handler
Maneja consultas de manuales
"""

import logging
import re

logger = logging.getLogger(__name__)


def handle_manual_query(context, message: str):
    """
    Manejar consulta de manuales

    Args:
        context: Contexto de la ventana principal (self)
        message: Mensaje del usuario
    """
    try:
        from core.manual_repository import ManualRepository

        # Extraer nombre del paquete
        package_match = re.search(
            r"(?:cómo se usa|manual de|guíame para usar|enseñame a usar)\s+(\w+)",
            message,
            re.IGNORECASE,
        )
        if not package_match:
            context.chat_ura("❌ No detecté el nombre del programa")
            context.hide_progress()
            return

        package_name = package_match.group(1)

        # Extraer tarea si existe
        task_match = re.search(r"para\s+(.+)", message, re.IGNORECASE)
        task = task_match.group(1) if task_match else None

        # Crear repositorio
        repo = ManualRepository()

        if task:
            # Crear guía paso a paso
            context.chat_ura(f"📖 Creando guía paso a paso para '{task}' en {package_name}...")
            steps = repo.create_step_by_step_guide(package_name, task)

            if steps and "error" not in steps[0]:
                for step in steps:
                    context.chat_ura(f"📍 Paso {step['step']}: {step['instruction']}")
            else:
                context.chat_ura(f"❌ {steps[0]['error']}")
        else:
            # Obtener instrucciones generales
            context.chat_ura(f"📖 Buscando manual de {package_name}...")
            instructions = repo.get_usage_instructions(package_name)
            context.chat_ura(f"📋 {instructions[:500]}...")

        context.hide_progress()
    except Exception as e:
        logger.error(f"Error en consulta de manual: {e}")
        context.chat_alert(f"❌ Error en consulta de manual: {e}")
        context.hide_progress()
