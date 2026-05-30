#!/usr/bin/env python3
"""
core/telegram_reader.py - Lector de Telegram (Solo Lectura)
Lee mensajes no leídos de Telegram con sesión persistente
"""

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# Rutas de configuración
SESSION_PATH = Path(__file__).parent.parent / "data" / "telegram_session"

# Crear directorio
SESSION_PATH.mkdir(parents=True, exist_ok=True)


@dataclass
class TelegramMessage:
    """Información de un mensaje de Telegram"""

    id: int
    from_name: str
    from_id: int
    chat_name: str
    chat_id: int
    text: str
    date: str
    is_unread: bool
    is_group: bool


class TelegramReader:
    """Lector de Telegram (Solo Lectura)"""

    def __init__(
        self, api_id: int | None = None, api_hash: str | None = None, phone: str | None = None
    ):
        self.api_id = api_id
        self.api_hash = api_hash
        self.phone = phone
        self.session_file = SESSION_PATH / "telegram_session"
        self.client = None

    async def connect(self) -> bool:
        """
        Conectar a Telegram con sesión persistente

        Returns:
            True si conexión exitosa
        """
        try:
            from telethon import TelegramClient

            # Si no se proporcionan credenciales, intentar cargar desde config
            if not self.api_id or not self.api_hash or not self.phone:
                config_file = Path(__file__).parent.parent / "config" / "telegram_config.json"
                if config_file.exists():
                    import json

                    with open(config_file) as f:
                        config = json.load(f)
                    self.api_id = config.get("api_id")
                    self.api_hash = config.get("api_hash")
                    self.phone = config.get("phone")
                else:
                    logger.error("❌ No existe config/telegram_config.json")
                    logger.info(
                        '💡 Crea el archivo con: {"api_id": 12345, "api_hash": "abc...", "phone": "+346..."}'
                    )
                    return False

            logger.info(f"Conectando a Telegram como {self.phone}...")

            # Crear cliente con sesión persistente
            self.client = TelegramClient(str(self.session_file), self.api_id, self.api_hash)

            # Conectar
            await self.client.connect()

            # Verificar si está autorizado
            if not await self.client.is_user_authorized():
                logger.info("⚠️ No autorizado - iniciando sesión...")

                print("\n" + "=" * 60)
                print("📱 AUTENTICACIÓN TELEGRAM")
                print("=" * 60)
                print(f"📲 Enviando código a: {self.phone}")
                print("=" * 60)

                # Enviar código
                await self.client.send_code_request(self.phone)

                print("\n📱 Introduce el código que recibiste en Telegram:")
                code = input("👉 Código: ")

                try:
                    await self.client.sign_in(self.phone, code)
                    logger.info("✅ Sesión iniciada correctamente")
                except Exception as e:
                    logger.error(f"❌ Error iniciando sesión: {e}")
                    return False
            else:
                logger.info("✅ Sesión ya autorizada (persistente)")

            return True

        except ImportError as e:
            logger.error(f"❌ Faltan dependencias para Telegram: {e}")
            logger.info("💡 Instala: pip install telethon")
            return False
        except Exception as e:
            logger.error(f"❌ Error conectando a Telegram: {e}")
            return False

    async def obtener_mensajes_no_leidos(self, max_chats: int = 20) -> list[TelegramMessage]:
        """
        Obtener mensajes no leídos de Telegram

        Args:
            max_chats: Número máximo de chats a obtener

        Returns:
            Lista de mensajes no leídos
        """
        try:
            if not self.client:
                logger.error("❌ No hay conexión a Telegram")
                return []

            logger.info("🔍 Buscando mensajes no leídos...")

            messages = []

            # Obtener diálogos
            async for dialog in self.client.iter_dialogs():
                if dialog.unread_count > 0:
                    # Obtener mensajes no leídos de este chat
                    async for message in self.client.iter_messages(
                        dialog.id, limit=min(dialog.unread_count, 10), reverse=True
                    ):
                        if message.out:
                            continue  # Ignorar mensajes enviados por mí

                        # Determinar nombre del remitente
                        if message.from_id:
                            sender = await message.get_sender()
                            from_name = getattr(sender, "first_name", "Desconocido")
                            from_id = getattr(sender, "id", 0)
                        else:
                            from_name = "Desconocido"
                            from_id = 0

                        # Determinar nombre del chat
                        chat_name = dialog.name
                        chat_id = dialog.id
                        is_group = dialog.is_group or dialog.is_channel

                        # Crear objeto TelegramMessage
                        msg = TelegramMessage(
                            id=message.id,
                            from_name=from_name,
                            from_id=from_id,
                            chat_name=chat_name,
                            chat_id=chat_id,
                            text=message.text or "[Media/Archivo]",
                            date=message.date.strftime("%Y-%m-%d %H:%M:%S"),
                            is_unread=True,
                            is_group=is_group,
                        )

                        messages.append(msg)

                        if len(messages) >= max_chats:
                            break

                if len(messages) >= max_chats:
                    break

            logger.info(f"📊 {len(messages)} mensajes no leídos encontrados")
            return messages

        except Exception as e:
            logger.error(f"❌ Error obteniendo mensajes: {e}")
            return []

    async def close(self):
        """Cerrar conexión a Telegram"""
        try:
            if self.client:
                await self.client.disconnect()
                logger.info("✅ Conexión a Telegram cerrada")
        except Exception as e:
            logger.error(f"❌ Error cerrando conexión: {e}")


async def obtener_mensajes_telegram(
    api_id: int | None = None,
    api_hash: str | None = None,
    phone: str | None = None,
    max_chats: int = 20,
) -> list[TelegramMessage]:
    """
    Función principal para obtener mensajes de Telegram

    Args:
        api_id: API ID de Telegram
        api_hash: API Hash de Telegram
        phone: Número de teléfono
        max_chats: Número máximo de chats a obtener

    Returns:
        Lista de mensajes no leídos
    """
    reader = TelegramReader(api_id=api_id, api_hash=api_hash, phone=phone)

    try:
        # Conectar
        if not await reader.connect():
            logger.error("❌ No se pudo conectar a Telegram")
            return []

        # Obtener mensajes
        messages = await reader.obtener_mensajes_no_leidos(max_chats=max_chats)

        return messages

    finally:
        # Cerrar conexión
        await reader.close()


def mostrar_mensajes_telegram_en_consola(messages: list[TelegramMessage]):
    """
    Mostrar mensajes de Telegram en consola de URA

    Args:
        messages: Lista de mensajes a mostrar
    """
    if not messages:
        print("📭 No hay mensajes no leídos en Telegram")
        return

    print("\n" + "=" * 60)
    print("💬 MENSAJES NO LEÍDOS DE TELEGRAM")
    print("=" * 60)

    for i, msg in enumerate(messages, 1):
        chat_type = "👥 Grupo" if msg.is_group else "👤 Chat"
        print(f"\n📩 Mensaje {i}")
        print(f"   {chat_type}: {msg.chat_name}")
        print(f"   👤 De: {msg.from_name}")
        print(f"   💬 Texto: {msg.text[:100]}...")
        print(f"   ⏰ Fecha: {msg.date}")

    print("\n" + "=" * 60)
    print(f"Total: {len(messages)} mensajes no leídos")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    # Prueba del lector de Telegram
    async def main():
        print("🔐 Iniciando lector de Telegram...")
        print("⚠️ Modo SOLO LECTURA\n")

        # Cargar credenciales desde config
        config_file = Path(__file__).parent.parent / "config" / "telegram_config.json"
        if config_file.exists():
            import json

            with open(config_file) as f:
                config = json.load(f)

            messages = await obtener_mensajes_telegram(
                api_id=config.get("api_id"),
                api_hash=config.get("api_hash"),
                phone=config.get("phone"),
                max_chats=10,
            )

            mostrar_mensajes_telegram_en_consola(messages)
        else:
            print("❌ No existe config/telegram_config.json")
            print(
                '💡 Crea el archivo con: {"api_id": 12345, "api_hash": "abc...", "phone": "+346..."}'
            )

    asyncio.run(main())
