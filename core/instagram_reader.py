#!/usr/bin/env python3
"""
core/instagram_reader.py - Lector de Instagram (Solo Lectura)
Lee mensajes directos (DMs) no leídos de Instagram con sesión persistente
"""

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# Rutas de configuración
SESSION_PATH = Path(__file__).parent.parent / "data" / "instagram_session"

# Crear directorio
SESSION_PATH.mkdir(parents=True, exist_ok=True)


@dataclass
class InstagramMessage:
    """Información de un mensaje de Instagram"""

    id: int
    from_username: str
    from_full_name: str
    thread_id: int
    text: str
    date: str
    has_media: bool
    media_type: str  # photo, video, none


class InstagramReader:
    """Lector de Instagram (Solo Lectura)"""

    def __init__(self, username: str | None = None, password: str | None = None):
        self.username = username
        self.password = password
        self.session_file = SESSION_PATH / "instagram_session"
        self.client = None

    async def connect(self) -> bool:
        """
        Conectar a Instagram con sesión persistente

        Returns:
            True si conexión exitosa
        """
        try:
            from instagrapi import Client

            # Si no se proporcionan credenciales, intentar cargar desde config
            if not self.username or not self.password:
                config_file = Path(__file__).parent.parent / "config" / "instagram_config.json"
                if config_file.exists():
                    import json

                    with open(config_file) as f:
                        config = json.load(f)
                    self.username = config.get("username")
                    self.password = config.get("password")
                else:
                    logger.error("❌ No existe config/instagram_config.json")
                    logger.info(
                        '💡 Crea el archivo con: {"username": "tu_usuario", "password": "tu_contraseña"}'
                    )
                    return False

            logger.info(f"Conectando a Instagram como {self.username}...")

            # Crear cliente con sesión persistente
            self.client = Client()

            # Cargar sesión si existe
            if self.session_file.exists():
                try:
                    self.client.load_settings(str(self.session_file))
                    logger.info("✅ Sesión cargada")
                except Exception as e:
                    logger.warning(f"⚠️ No se pudo cargar sesión: {e}")

            # Intentar login
            try:
                self.client.login(self.username, self.password)
                logger.info("✅ Sesión iniciada correctamente")

                # Guardar sesión
                self.client.dump_settings(str(self.session_file))
                logger.info(f"💾 Sesión guardada en: {self.session_file}")

                return True
            except Exception as e:
                logger.error(f"❌ Error iniciando sesión: {e}")
                logger.info("💡 Verifica que tu usuario y contraseña son correctos")
                return False

        except ImportError as e:
            logger.error(f"❌ Faltan dependencias para Instagram: {e}")
            logger.info("💡 Instala: pip install instagrapi")
            return False
        except Exception as e:
            logger.error(f"❌ Error conectando a Instagram: {e}")
            return False

    async def obtener_dms_no_leidos(self, max_threads: int = 20) -> list[InstagramMessage]:
        """
        Obtener mensajes directos no leídos de Instagram

        Args:
            max_threads: Número máximo de hilos a obtener

        Returns:
            Lista de mensajes no leídos
        """
        try:
            if not self.client:
                logger.error("❌ No hay conexión a Instagram")
                return []

            logger.info("🔍 Buscando DMs no leídos...")

            messages = []

            # Obtener hilos de mensajes directos
            threads = self.client.direct_threads(amount=max_threads)

            for thread in threads:
                if thread.unread_count > 0:
                    # Obtener mensajes del hilo
                    thread_messages = self.client.direct_messages(thread_id=thread.id, limit=10)

                    for msg in thread_messages:
                        # Solo mensajes recibidos (no enviados por mí)
                        if msg.user_id == self.client.user_id:
                            continue

                        # Determinar tipo de media
                        has_media = False
                        media_type = "none"
                        if hasattr(msg, "media") and msg.media:
                            has_media = True
                            if hasattr(msg.media, "media_type"):
                                if msg.media.media_type == 1:
                                    media_type = "photo"
                                elif msg.media.media_type == 2:
                                    media_type = "video"
                            else:
                                media_type = "media"

                        # Obtener información del remitente
                        sender = thread.users[0] if thread.users else None
                        if sender:
                            from_username = sender.username
                            from_full_name = sender.full_name or sender.username
                        else:
                            from_username = "Desconocido"
                            from_full_name = "Desconocido"

                        # Crear objeto InstagramMessage
                        ig_msg = InstagramMessage(
                            id=msg.id,
                            from_username=from_username,
                            from_full_name=from_full_name,
                            thread_id=thread.id,
                            text=msg.text or "[Media]",
                            date=(
                                msg.timestamp.strftime("%Y-%m-%d %H:%M:%S") if msg.timestamp else ""
                            ),
                            has_media=has_media,
                            media_type=media_type,
                        )

                        messages.append(ig_msg)

                        if len(messages) >= max_threads:
                            break

                if len(messages) >= max_threads:
                    break

            logger.info(f"📊 {len(messages)} DMs no leídos encontrados")
            return messages

        except Exception as e:
            logger.error(f"❌ Error obteniendo DMs: {e}")
            return []

    async def close(self):
        """Cerrar conexión a Instagram"""
        try:
            if self.client:
                self.client.dump_settings(str(self.session_file))
                logger.info("✅ Sesión guardada")
        except Exception as e:
            logger.error(f"❌ Error cerrando conexión: {e}")


async def obtener_dms_instagram(
    username: str | None = None, password: str | None = None, max_threads: int = 20
) -> list[InstagramMessage]:
    """
    Función principal para obtener DMs de Instagram

    Args:
        username: Usuario de Instagram
        password: Contraseña de Instagram
        max_threads: Número máximo de hilos a obtener

    Returns:
        Lista de mensajes no leídos
    """
    reader = InstagramReader(username=username, password=password)

    try:
        # Conectar
        if not await reader.connect():
            logger.error("❌ No se pudo conectar a Instagram")
            return []

        # Obtener DMs
        messages = await reader.obtener_dms_no_leidos(max_threads=max_threads)

        return messages

    finally:
        # Cerrar conexión
        await reader.close()


def mostrar_dms_instagram_en_consola(messages: list[InstagramMessage]):
    """
    Mostrar DMs de Instagram en consola de URA

    Args:
        messages: Lista de mensajes a mostrar
    """
    if not messages:
        print("📭 No hay DMs no leídos en Instagram")
        return

    print("\n" + "=" * 60)
    print("📷 DMs NO LEÍDOS DE INSTAGRAM")
    print("=" * 60)

    for i, msg in enumerate(messages, 1):
        media_icon = (
            "📷" if msg.media_type == "photo" else "🎥" if msg.media_type == "video" else ""
        )
        print(f"\n📩 DM {i}")
        print(f"   👤 @{msg.from_username} ({msg.from_full_name})")
        print(f"   💬 Texto: {msg.text[:100]}...")
        if msg.has_media:
            print(f"   {media_icon} Media: {msg.media_type}")
        print(f"   ⏰ Fecha: {msg.date}")

    print("\n" + "=" * 60)
    print(f"Total: {len(messages)} DMs no leídos")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    # Prueba del lector de Instagram
    import asyncio

    async def main():
        print("🔐 Iniciando lector de Instagram...")
        print("⚠️ Modo SOLO LECTURA\n")

        # Cargar credenciales desde config
        config_file = Path(__file__).parent.parent / "config" / "instagram_config.json"
        if config_file.exists():
            import json

            with open(config_file) as f:
                config = json.load(f)

            messages = await obtener_dms_instagram(
                username=config.get("username"), password=config.get("password"), max_threads=10
            )

            mostrar_dms_instagram_en_consola(messages)
        else:
            print("❌ No existe config/instagram_config.json")
            print('💡 Crea el archivo con: {"username": "tu_usuario", "password": "tu_contraseña"}')

    asyncio.run(main())
