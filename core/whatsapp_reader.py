#!/usr/bin/env python3
"""
core/whatsapp_reader.py - Lector de WhatsApp (Solo Lectura)
Extrae mensajes nuevos de WhatsApp Web sin permiso para escribir/enviar
"""

import asyncio
import logging
from datetime import datetime
from pathlib import Path

from playwright.async_api import Browser, BrowserContext, Page, async_playwright

logger = logging.getLogger(__name__)

# Ruta de persistencia de sesión (absoluta del proyecto)
PROJECT_ROOT = Path(__file__).parent.parent
SESSION_PATH = PROJECT_ROOT / "data" / "whatsapp_session"


class WhatsAppReader:
    """Lector de WhatsApp Web (Solo Lectura)"""

    def __init__(self, headless: bool = False):
        self.headless = headless
        self.browser: Browser | None = None
        self.context: BrowserContext | None = None
        self.page: Page | None = None

        # Crear directorio de sesión con permisos totales
        SESSION_PATH.mkdir(parents=True, exist_ok=True)

        # Asegurar permisos de escritura
        try:
            SESSION_PATH.chmod(0o755)
            logger.info(f"✅ Carpeta de sesión creada con permisos: {SESSION_PATH}")
        except Exception as e:
            logger.warning(f"⚠️ No se pudo establecer permisos: {e}")


async def connect(self) -> bool:
    """
    Conectar a WhatsApp Web con persistencia de sesión

    Returns:
        True si conexión exitosa
    """
    try:
        logger.info("Iniciando Playwright para WhatsApp Web...")

        session_file = SESSION_PATH / "state.json"
        has_session = await check_session_existence(session_file)

        if not has_session:
            logger.info("⚠️ No existe sesión previa")
            logger.info("🖥️ Abriendo navegador en modo VISIBLE para escanear QR")
            self.headless = False
        else:
            logger.info("✅ Sesión previa encontrada")

        playwright = await async_playwright().start()

        self.browser = await launch_browser(playwright, headless=self.headless)

        if has_session:
            self.context = await create_context_with_storage_state(self.browser, str(session_file))
        else:
            self.context = await create_context(self.browser)

        self.page = await self.context.new_page()

        logger.info("Navegando a WhatsApp Web...")
        await navigate_to_whatsapp_web(self.page)

        print("\n" + "=" * 60)
        print("🔴 ESCANEA EL QR Y NO TOQUES NADA")
        print("=" * 60)
        print(f"📍 Sesión se guardará en: {SESSION_PATH}")
        print("🔴 Pulsa ENTER aquí solo cuando termines...")
        print("=" * 60)
        input()

        await check_and_scan_qr_code(self.page)

        if await is_logged_in(self.page):
            logger.info("✅ Sesión iniciada correctamente")

            await save_session_state(self.context, session_file)
            logger.info(f"💾 Sesión guardada en: {session_file}")

            print("\n✅ Sesión guardada correctamente")
            print("👉 Pulsa ENTER en esta terminal para continuar...")
            input()

            return True
        else:
            logger.error("❌ No se pudo iniciar sesión")
            print("\n❌ No se pudo iniciar sesión. Intenta de nuevo.")
            print("👉 Pulsa ENTER para salir...")
            input()
            return False

    except Exception as e:
        logger.error(f"❌ Error conectando a WhatsApp Web: {e}")
        print(f"\n❌ Error conectando a WhatsApp Web: {e}")
        print("👉 Pulsa ENTER para salir...")
        input()
        return False


async def check_session_existence(session_file) -> bool:
    return session_file.exists()


async def launch_browser(playwright, headless):
    return await playwright.chromium.launch(
        headless=headless,
        args=[
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--disable-web-security",
            "--disable-features=IsolateOrigins,site-per-process",
        ],
    )


async def create_context_with_storage_state(browser, storage_state_path):
    return await browser.new_context(
        storage_state=storage_state_path,
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    )


async def create_context(browser):
    return await browser.new_context(
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )


async def navigate_to_whatsapp_web(page):
    await page.goto("https://web.whatsapp.com", wait_until="networkidle", timeout=120000)


async def check_and_scan_qr_code(page):
    qr_code = await page.query_selector('canvas[aria-label="Scan this QR code"]')

    if qr_code:
        logger.info("⚠️ Se requiere escanear código QR")
        logger.info(f"📍 Sesión se guardará en: {SESSION_PATH}")
        logger.info("ℹ️ Solo necesitas escanear el QR la primera vez")
        logger.info("📱 Escanea el QR con tu teléfono...")
        print("\n" + "=" * 60)
        print("📱 ESCANEO DE CÓDIGO QR")
        print("=" * 60)
        print("🔍 Esperando escaneo de código QR...")
        print("📲 Abre WhatsApp en tu teléfono")
        print("⚙️ Ve a Configuración > Dispositivos vinculados")
        print("📷 Escanea el código QR que aparece en el navegador")
        print("=" * 60)

        await page.wait_for_selector('div[contenteditable="true"][data-tab="3"]', timeout=300000)


async def is_logged_in(page):
    return await page.query_selector('div[contenteditable="true"][data-tab="3"]') is not None


async def save_session_state(context, session_file_path):
    await context.storage_state(path=session_file_path)

    async def obtener_mensajes_whatsapp(self, max_chats: int = 10) -> list[dict]:
        """
        Obtener últimos chats sin leer de WhatsApp (Solo Lectura)

        Args:
            max_chats: Número máximo de chats a obtener

        Returns:
            Lista de diccionarios con información de los chats
        """
        try:
            if not self.page:
                logger.error("❌ No hay conexión a WhatsApp Web")
                return []

            logger.info("🔍 Buscando mensajes no leídos...")

            # Esperar a que cargue la lista de chats
            await asyncio.sleep(2)

            # Buscar chats con mensajes no leídos
            chats = []

            # Seleccionar todos los elementos de chat
            chat_elements = await self.page.query_selector_all('div[role="listitem"]')

            for i, chat_element in enumerate(chat_elements[:max_chats]):
                try:
                    # Extraer nombre del contacto
                    name_element = await chat_element.query_selector("span[title]")
                    name = (
                        await name_element.get_attribute("title") if name_element else "Desconocido"
                    )

                    # Verificar si tiene mensajes no leidos
                    unread_element = await chat_element.query_selector(
                        'span[data-icon="unread-chat"]'
                    )
                    unread_count_element = await chat_element.query_selector(
                        'span[class*="unread"]'
                    )

                    unread_count = 0
                    if unread_count_element:
                        unread_text = await unread_count_element.inner_text()
                        try:
                            unread_count = int(unread_text)
                        except:
                            unread_count = 1

                    # Extraer último mensaje
                    last_message_element = await chat_element.query_selector(
                        'span[class*="message"]'
                    )
                    last_message = ""
                    if last_message_element:
                        last_message = await last_message_element.inner_text()

                    # Extraer hora
                    time_element = await chat_element.query_selector('span[title*=":"]')
                    time_str = ""
                    if time_element:
                        time_str = await time_element.get_attribute("title")

                    if unread_count > 0 or unread_element:
                        chat_info = {
                            "name": name,
                            "unread_count": unread_count,
                            "last_message": last_message[:100],  # Limitar longitud
                            "time": time_str,
                            "timestamp": datetime.now().isoformat(),
                        }
                        chats.append(chat_info)
                        logger.info(f"📩 {name}: {unread_count} mensajes no leídos")

                except Exception as e:
                    logger.warning(f"⚠️ Error extrayendo chat {i}: {e}")
                    continue

            logger.info(f"📊 Total chats con mensajes no leídos: {len(chats)}")
            return chats

        except Exception as e:
            logger.error(f"❌ Error obteniendo mensajes: {e}")
            return []

    async def close(self):
        """
        NO cerrar navegador - el usuario debe cerrarlo manualmente
        """
        logger.info("ℹ️ Navegador permanece abierto - ciérralo manualmente cuando termines")
        # NO cerrar navegador - dejar abierto para el usuario


async def obtener_mensajes_whatsapp(headless: bool = False, max_chats: int = 10) -> list[dict]:
    """
    Función principal para obtener mensajes de WhatsApp (Solo Lectura)

    Args:
        headless: Ejecutar navegador en modo headless
        max_chats: Número máximo de chats a obtener

    Returns:
        Lista de diccionarios con información de los chats
    """
    reader = WhatsAppReader(headless=headless)

    try:
        # Conectar a WhatsApp Web
        if not await reader.connect():
            logger.error("❌ No se pudo conectar a WhatsApp Web")
            return []

        # Obtener mensajes
        chats = await reader.obtener_mensajes_whatsapp(max_chats=max_chats)

        return chats

    finally:
        # Cerrar navegador
        await reader.close()


def mostrar_mensajes_en_consola(chats: list[dict]):
    """
    Mostrar mensajes en consola de URA

    Args:
        chats: Lista de chats a mostrar
    """
    if not chats:
        print("📭 No hay mensajes no leídos")
        return

    print("\n" + "=" * 60)
    print("📱 MENSAJES NO LEÍDOS DE WHATSAPP")
    print("=" * 60)

    for i, chat in enumerate(chats, 1):
        print(f"\n📩 Chat {i}")
        print(f"   👤 Contacto: {chat['name']}")
        print(f"   📊 No leídos: {chat['unread_count']}")
        print(f"   💬 Último mensaje: {chat['last_message']}")
        print(f"   ⏰ Hora: {chat['time']}")

    print("\n" + "=" * 60)
    print(f"Total: {len(chats)} chats con mensajes no leídos")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    # Prueba del lector de WhatsApp
    async def main():
        print("🔐 Iniciando lector de WhatsApp (Solo Lectura)...")
        print("⚠️ Modo SOLO LECTURA: No se enviarán mensajes\n")

        chats = await obtener_mensajes_whatsapp(headless=False, max_chats=10)

        mostrar_mensajes_en_consola(chats)

    asyncio.run(main())
