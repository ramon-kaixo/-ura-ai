#!/usr/bin/env python3
"""
URA - Windsurf Handler
Maneja comandos de Windsurf
"""

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)


def handle_windsurf_command(context, message: str):
    """
    Manejar comando de Windsurf

    Args:
        context: Contexto de la ventana principal (self)
        message: Mensaje del usuario
    """
    try:
        from core.windsurf_binomio import WindsurfBinomio

        # Crear binomio con ollama_connector
        binomio = WindsurfBinomio(ollama_connector=context.ollama_connector)

        # Detectar tipo de comando
        if "abre Windsurf" in message.lower():
            result = binomio.open_windsurf()
            if result["success"]:
                context.chat_ura(f"✅ {result['message']}")
            else:
                context.chat_ura(f"❌ {result.get('error', 'Error desconocido')}")

        elif "dile a Windsurf que" in message.lower():
            # Extraer prompt
            prompt_match = re.search(r"dile\s+a\s+Windsurf\s+que\s+(.+)", message, re.IGNORECASE)
            if prompt_match:
                prompt = prompt_match.group(1)
                context.chat_ura(f"💬 Enviando a Windsurf: '{prompt}'...")
                result = binomio.send_prompt_to_windsurf(prompt)

                if result["success"]:
                    context.chat_ura(f"✅ {result['message']}")
                    if result.get("generated_code"):
                        context.chat_ura(
                            f"📝 Código generado:\n{result['generated_code'][:500]}..."
                        )
                else:
                    context.chat_ura(f"❌ {result.get('error', 'Error desconocido')}")

        elif "ejecuta el código que generó Windsurf" in message.lower():
            context.chat_ura(
                "⚠️ Para ejecutar código generado, usa el flujo completo: 'URA, necesito un script que haga X'"
            )
            context.chat_ura("💡 El flujo completo genera y ejecuta automáticamente.")

        elif (
            "necesito un script que" in message.lower() or "genera un script que" in message.lower()
        ):
            # Flujo completo
            context.chat_ura("🚀 Iniciando flujo completo URA-Windsurf...")
            result = binomio.complete_flow(message)

            for step in result["steps"]:
                context.chat_ura(step)

            if result["success"]:
                context.chat_ura(f"✅ {result['message']}")
                if result.get("output"):
                    context.chat_ura(f"📋 Resultado:\n{result['output']}")
            else:
                context.chat_ura(f"❌ {result.get('error', 'Error desconocido')}")

        elif "cómo se hace" in message.lower() and "en Windsurf" in message.lower():
            # Extraer tema
            topic_match = re.search(r"cómo\s+se\s+hace\s+(\w+)", message, re.IGNORECASE)
            topic_match.group(1) if topic_match else None

            # Leer manual
            manual_path = Path.home() / "Documents" / "URA_Manuales" / "Windsurf" / "manual.txt"
            if manual_path.exists():
                with open(manual_path) as f:
                    help_text = f.read()
                context.chat_ura(f"📖 {help_text[:500]}...")
            else:
                context.chat_ura("⚠️ Manual no encontrado en ~/Documents/URA_Manuales/Windsurf/")

        else:
            context.chat_ura(
                "⚠️ No reconocí el comando. Prueba: 'URA, necesito un script que haga X'"
            )

        context.hide_progress()
    except Exception as e:
        logger.error(f"Error en comando de Windsurf: {e}")
        context.chat_alert(f"❌ Error en comando de Windsurf: {e}")
        context.hide_progress()
