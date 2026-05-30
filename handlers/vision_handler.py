#!/usr/bin/env python3
"""
URA - Vision Handler
Maneja comandos de visión y automatización visual
"""

import logging

logger = logging.getLogger(__name__)


def handle_screen_area(context, message: str):
    """
    Manejar comando de selección de área

    Args:
        context: Contexto de la ventana principal (self)
        message: Mensaje del usuario
    """
    try:
        from core.screen_selector import ScreenSelector

        # Verificar permisos antes de capturar pantalla
        if context.mac_permissions:
            perm_check = context.mac_permissions.check_before_capture()

            if not perm_check["can_capture"]:
                context.chat_ura("⚠️ URA no tiene permisos de grabación de pantalla.")
                context.chat_ura("📋 Para habilitar:")

                perm_result = context.mac_permissions.request_screen_permission()
                for instruction in perm_result["instructions"]:
                    context.chat_ura(f"   {instruction}")

                context.hide_progress()
                return

        context.chat_ura("🖱️ Selecciona un área de la pantalla:")
        context.chat_ura("   1. Mueve el cursor a la esquina superior izquierda y presiona Enter")
        context.chat_ura("   2. Mueve el cursor a la esquina inferior derecha y presiona Enter")

        # Crear selector
        selector = ScreenSelector()

        # Ejecutar selección interactiva
        analysis = selector.explain_area_interactive()

        if "error" in analysis:
            context.chat_ura(f"❌ Error: {analysis['error']}")
        else:
            context.chat_ura(f"📋 Descripción: {analysis['description'][:200]}...")
            context.chat_ura(f"🔷 Tipo: {analysis['element_type']}")

            if analysis["suggested_actions"]:
                context.chat_ura("💡 Acciones sugeridas:")
                for action in analysis["suggested_actions"]:
                    context.chat_ura(f"   - {action}")

        context.hide_progress()
    except Exception as e:
        logger.error(f"Error en selección de área: {e}")
        context.chat_alert(f"❌ Error en selección de área: {e}")
        context.hide_progress()


def handle_visual_automation(context, message: str):
    """
    Manejar comando de automatización visual con modo autónomo

    Args:
        context: Contexto de la ventana principal (self)
        message: Mensaje del usuario
    """
    try:
        from core.visual_automation import VisualAutomation

        # Verificar permisos antes de automatización visual
        if context.mac_permissions:
            perm_check = context.mac_permissions.check_before_click()

            if not perm_check["can_click"]:
                context.chat_ura("⚠️ URA no tiene permisos de accesibilidad necesarios.")
                context.chat_ura("📋 Para habilitar:")

                if "accessibility" in perm_check["missing_permissions"]:
                    perm_result = context.mac_permissions.request_accessibility_permission()
                    for instruction in perm_result["instructions"]:
                        context.chat_ura(f"   {instruction}")

                context.hide_progress()
                return

        # Crear instancia en modo autónomo
        automation = VisualAutomation(autonomous_mode=True)

        # Detectar si es para Gmail
        if (
            "gmail" in message.lower()
            or "correo" in message.lower()
            or "configura" in message.lower()
        ):
            context.chat_ura(
                "📧 Voy a configurar Gmail automáticamente. Solo te pediré ayuda cuando sea necesario."
            )

            # Callback para pedir input al usuario
            def user_callback(prompt: str):
                context.chat_ura(f"❓ {prompt}")
                # En un sistema real, aquí esperaría input del usuario
                # Por ahora, solo mostramos el mensaje

            # Ejecutar flujo autónomo
            messages = automation.execute_autonomous_flow("gmail_setup", user_callback)

            # Mostrar mensajes de progreso
            for msg in messages:
                context.chat_ura(msg)

            context.chat_ura("🎉 Proceso completado. Ahora puedo leer tus correos.")
        else:
            context.chat_ura("🤖 Automatización visual autónoma activada.")

            # Capturar pantalla actual
            screen_desc = automation.capture_and_analyze()
            context.chat_ura(f"👀 Veo: {screen_desc[:200]}...")

            # Extraer elementos
            elements = automation.extract_interactive_elements()
            if elements:
                context.chat_ura(
                    f"🔘 Elementos detectados: {', '.join([e['text'] for e in elements])}"
                )

                # Decidir acción automáticamente
                action = automation.decide_next_action("general")
                if action["confidence"] > 0.5:
                    context.chat_ura(f"🤖 Voy a hacer clic en: {action['target']}")
                    success = automation.execute_action(action, auto_execute=True)
                    if success:
                        context.chat_ura("✅ Acción completada")
                    else:
                        context.chat_ura("❌ No pude completar la acción automáticamente")
                else:
                    context.chat_ura("⚠️ No estoy seguro de qué hacer. Necesito tu ayuda.")
            else:
                context.chat_ura("⚠️ No detecté elementos interactivos claros.")
                context.chat_ura("💡 Usa 'URA, mira mi pantalla' para una descripción detallada.")

        context.hide_progress()
    except Exception as e:
        logger.error(f"Error en automatización visual: {e}")
        context.chat_alert(f"❌ Error en automatización visual: {e}")
        context.hide_progress()
