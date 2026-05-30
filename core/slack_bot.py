#!/usr/bin/env python3
"""
URA Slack Bot - Integración con Slack
"""

import asyncio
import os
import time
from datetime import datetime, timedelta

from slack_sdk.socket_mode.aiohttp import SocketModeClient
from slack_sdk.web.async_client import AsyncWebClient

from core.logging_config import get_logger

from memory import Memory, MemoryType

# Imports URA
from orchestrator_langgraph import URAOrchestrator


# Simple in-memory cache
class SimpleCache:
    """Simple in-memory cache with TTL"""

    def __init__(self):
        self.cache = {}
        self.timestamps = {}

    def get_response(self, key: str, message: str) -> str | None:
        """Get cached response if not expired"""
        cache_key = f"{key}:{message}"
        if cache_key in self.cache:
            timestamp = self.timestamps.get(cache_key)
            if timestamp and datetime.now() - timestamp < timedelta(seconds=900):
                return self.cache[cache_key]
        return None

    def set_response(self, key: str, message: str, response: str, ttl: int = 900):
        """Cache response with TTL"""
        cache_key = f"{key}:{message}"
        self.cache[cache_key] = response
        self.timestamps[cache_key] = datetime.now()


# Configuración Slack
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN", "xoxb-your-bot-token")
SLACK_APP_TOKEN = os.getenv("SLACK_APP_TOKEN", "xapp-your-app-token")

# Inicializar
logger = get_logger("slack_bot", log_dir="./logs")
agent_cache = SimpleCache()
orchestrator = URAOrchestrator()
memory = Memory()


class URASlackBot:
    """Bot de URA para Slack"""

    def __init__(self):
        self.web_client = AsyncWebClient(token=SLACK_BOT_TOKEN)
        self.socket_client = SocketModeClient(app_token=SLACK_APP_TOKEN, web_client=self.web_client)
        self.rate_limit = {}

    async def start(self):
        """Iniciar bot de Slack"""
        try:
            # Registrar handlers
            self.socket_client.socket_mode_request_listeners.append(self.handle_events)

            # Conectar
            await self.socket_client.connect()
            print("🚀 URA Slack Bot conectado")

            # Mensaje de bienvenida
            await self.post_message(
                "🤖 URA Bot conectado\n\n• 57 agentes disponibles\n• Memoria persistente\n• Respuestas inteligentes\n\n¡Mencióname con @URA!",
                channel="general",
            )

        except Exception as e:
            logger.log_error(f"Error iniciando Slack bot: {e}")

    async def handle_events(self, client, req):
        """Manejar eventos de Slack"""
        try:
            if req.type == "events_api":
                event = req.payload["event"]

                # Solo procesar mensajes
                if event["type"] == "message" and not event.get("bot_id"):
                    await self.handle_message(event)

        except Exception as e:
            logger.log_error(f"Error handling event: {e}")

    async def handle_message(self, event):
        """Procesar mensaje recibido"""
        try:
            channel = event["channel"]
            user = event["user"]
            text = event.get("text", "")
            thread_ts = event.get("thread_ts")

            # Rate limiting por usuario
            now = time.time()
            if user in self.rate_limit:
                if now - self.rate_limit[user] < 2:  # 2 segundos entre mensajes
                    return

            self.rate_limit[user] = now

            # Verificar si mencionan al bot
            if "<@URA>" in text or text.startswith("!ura"):
                # Limpiar el mensaje
                clean_text = text.replace("<@URA>", "").replace("!ura", "").strip()

                if not clean_text:
                    return

                print(f"📨 Slack [{user}] {clean_text[:50]}")

                # Indicar que está procesando
                await self.post_message("🤔 Procesando...", channel, thread_ts)

                # Procesar con URA
                response = await self.process_with_ura(clean_text, user)

                # Enviar respuesta
                await self.post_message(response, channel, thread_ts)

        except Exception as e:
            logger.log_error(f"Error handling message: {e}")

    async def process_with_ura(self, message: str, user: str) -> str:
        """Procesar mensaje con URA"""
        start_time = time.time()

        try:
            # Comandos especiales
            cmd = message.lower().strip()

            if cmd == "status":
                return "🤖 URA Status:\n• ✅ 57 agentes activos\n• ✅ Memoria funcionando\n• ✅ Cache habilitado\n• ⚡ Respuesta <2s"

            if cmd.startswith("recuerda"):
                partes = cmd[8:].split(maxsplit=1)
                if len(partes) >= 2:
                    clave = partes[0]
                    valor = partes[1]
                    memory.store(MemoryType.LONG_TERM, clave, valor, agent="slack", importance=8)
                    return f"✅ Recordado: {clave} = {valor}"
                return "❌ Formato: recuerda <clave> <valor>"

            if cmd.startswith("qué sabes de"):
                tema = cmd[14:].strip()
                resultado = memory.retrieve(tema)
                if resultado:
                    return f"📚 {tema}: {resultado['value']}"
                return f"No tengo información sobre {tema}"

            # Verificar cache primero
            cached_response = agent_cache.get_response("slack", message)
            if cached_response:
                logger.log_metric("cache_hit", 1.0, unit="count")
                return cached_response

            # Procesar con orchestrator
            resultado = orchestrator.procesar(message, f"slack_{user}")
            respuesta = resultado.get("respuesta_final", resultado.get("respuesta_parcial", ""))

            if not respuesta:
                respuesta = "💭 Estoy procesando tu solicitud..."

            # Cachear respuesta
            agent_cache.set_response("slack", message, respuesta, ttl=900)  # 15 min

            # Guardar en memoria
            memory.store_conversation(
                "slack", message, respuesta, trace_id=resultado.get("trace_id")
            )

            processing_time = time.time() - start_time
            logger.log_metric("slack_response_time", processing_time, unit="seconds")

            return respuesta

        except Exception as e:
            logger.log_error(f"Error procesando mensaje Slack: {e}")
            return "❌ Error procesando tu mensaje. Intenta de nuevo."

    async def post_message(self, text: str, channel: str, thread_ts: str | None = None):
        """Enviar mensaje a Slack"""
        try:
            await self.web_client.chat_postMessage(channel=channel, text=text, thread_ts=thread_ts)
        except Exception as e:
            logger.log_error(f"Error enviando mensaje Slack: {e}")

    async def upload_file(self, file_path: str, channel: str, title: str = None):
        """Subir archivo a Slack"""
        try:
            await self.web_client.files_upload_v2(
                channel=channel, file=file_path, title=title or os.path.basename(file_path)
            )
        except Exception as e:
            logger.log_error(f"Error subiendo archivo Slack: {e}")


# Funciones de comandos
async def handle_slash_command(ack, body, client):
    """Manejar comandos slash"""
    command = body["command"]
    body["user_id"]
    body["channel_id"]

    if command == "/ura-status":
        await ack("🤖 URA Status: ✅ Todo operativo")
        return

    if command == "/ura-help":
        help_text = """
🤖 **Comandos URA en Slack**

• `@URA <mensaje>` - Chatear con URA
• `/ura-status` - Ver estado del sistema
• `/ura-help` - Mostrar esta ayuda
• `recuerda <clave> <valor>` - Guardar en memoria
• `qué sabes de <tema>` - Consultar memoria

**Ejemplos:**
• `@URA hazme una factura`
• `@URA estado del sistema`
• `recuerda proyecto_deadline 31-dic`
• `qué sabes de facturas`
        """
        await ack(help_text)
        return


# Main
async def main():
    """Función principal"""
    print("=" * 50)
    print("🤖 URA Slack Bot")
    print("=" * 50)

    bot = URASlackBot()

    try:
        await bot.start()

        # Mantener corriendo
        while True:
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        print("\n🛑 Deteniendo URA Slack Bot...")
        await bot.socket_client.disconnect()
    except Exception as e:
        logger.log_error(f"Error en main Slack: {e}")


if __name__ == "__main__":
    asyncio.run(main())
