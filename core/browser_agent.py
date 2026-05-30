#!/usr/bin/env python3
"""
URA Browser Agent - Automatización general con Playwright
Automatización de navegador sin credenciales hardcodeadas
"""

from pathlib import Path
import asyncio

from playwright.async_api import Browser, BrowserContext, Page, async_playwright

from core.logging_config import get_logger

logger = get_logger("browser_agent", log_dir="./logs")

# Ruta de persistencia de sesión (reutiliza WhatsApp session si existe)
PROJECT_ROOT = Path(__file__).parent.parent
SESSION_PATH = PROJECT_ROOT / "data" / "whatsapp_session"


class BrowserAgent:
    """Agente de automatización de navegador con Playwright"""

    def __init__(self, headless: bool = True):
        self.headless = headless
        self.playwright = None
        self.browser: Browser | None = None
        self.context: BrowserContext | None = None
        self.page: Page | None = None
        self.session_file = SESSION_PATH / "state.json"

    async def __aenter__(self):
        """Context manager entry"""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        await self.close()

    async def connect(self) -> bool:
        """
        Conectar al navegador con persistencia de sesión

        Returns:
            True si conexión exitosa
        """
        try:
            logger.info("Iniciando Playwright...")

            self.playwright = await async_playwright().start()

            # Verificar si existe sesión previa
            session_file = SESSION_PATH / "state.json"
            has_session = session_file.exists()

            # Iniciar navegador con persistencia
            self.browser = await self.playwright.chromium.launch(
                headless=self.headless,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-web-security",
                ],
            )

            # Crear contexto con persistencia de sesión si existe
            if has_session:
                logger.info("Reutilizando sesión existente")
                self.context = await self.browser.new_context(
                    storage_state=str(session_file),
                    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                )
            else:
                logger.info("Creando nueva sesión")
                self.context = await self.browser.new_context(
                    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
                )

            # Crear página
            self.page = await self.context.new_page()
            logger.info("Navegador iniciado correctamente")
            return True

        except Exception as e:
            logger.error(f"Error conectando al navegador: {e}")
            return False

    async def abrir_url(self, url: str) -> bool:
        """
        Abrir URL en el navegador

        Args:
            url: URL a abrir

        Returns:
            True si se abrió correctamente
        """
        try:
            if not self.page:
                logger.error("Navegador no conectado")
                return False

            logger.info(f"Navegando a: {url}")
            await self.page.goto(url, wait_until="networkidle", timeout=30000)
            logger.info("URL cargada correctamente")
            return True

        except Exception as e:
            logger.error(f"Error abriendo URL {url}: {e}")
            return False

    async def capturar_pantalla(self, path: str) -> bool:
        """
        Capturar screenshot de la página actual

        Args:
            path: Ruta donde guardar el screenshot

        Returns:
            True si se capturó correctamente
        """
        try:
            if not self.page:
                logger.error("Navegador no conectado")
                return False

            # Asegurar que el directorio existe
            Path(path).parent.mkdir(parents=True, exist_ok=True)

            await self.page.screenshot(path=path, full_page=False)
            logger.info(f"Screenshot guardado en: {path}")
            return True

        except Exception as e:
            logger.error(f"Error capturando pantalla: {e}")
            return False

    async def copiar_texto(self, selector: str) -> str | None:
        """
        Extraer texto de un elemento CSS

        Args:
            selector: Selector CSS del elemento

        Returns:
            Texto del elemento o None si no se encuentra
        """
        try:
            if not self.page:
                logger.error("Navegador no conectado")
                return None

            element = await self.page.query_selector(selector)
            if not element:
                logger.warning(f"Elemento no encontrado: {selector}")
                return None

            text = await element.inner_text()
            logger.info(f"Texto extraído de {selector}: {text[:50]}...")
            return text

        except Exception as e:
            logger.error(f"Error copiando texto de {selector}: {e}")
            return None

    async def close(self):
        """Cierra navegador y guarda sesión."""
        await self.context.storage_state(path=self.session_file)
        await self.browser.close()
        await self.playwright.stop()
        logger.info("Navegador cerrado correctamente")

    async def buscar_y_clicar(self, texto_buscar: str) -> bool:
        """Busca un botón o enlace con el texto dado y hace clic. Como un humano leyendo la pantalla."""
        try:
            page = self.page
            # Buscar botones
            btn = await page.query_selector(f'button:has-text("{texto_buscar}")')
            if not btn:
                btn = await page.query_selector(f'a:has-text("{texto_buscar}")')
            if not btn:
                btn = await page.query_selector(f'input[type="submit"][value*="{texto_buscar}"]')
            if not btn:
                # Busqueda flexible: cualquier elemento clickable que contenga el texto
                btn = await page.query_selector(f'[role="button"]:has-text("{texto_buscar}")')
            if btn:
                await btn.click()
                logger.info(f"Clic en: {texto_buscar}")
                await asyncio.sleep(1)
                return True
            logger.info(f"No encontrado: {texto_buscar}")
            return False
        except Exception as e:
            logger.error(f"Error buscando '{texto_buscar}': {e}")
            return False

    async def rellenar_campo(self, placeholder: str, valor: str) -> bool:
        """Busca un campo de formulario por su placeholder y escribe el valor."""
        try:
            campo = await self.page.query_selector(f'input[placeholder*="{placeholder}"]')
            if not campo:
                campo = await self.page.query_selector(f'input[name*="{placeholder}"]')
            if not campo:
                campo = await self.page.query_selector(f'input[id*="{placeholder}"]')
            if not campo:
                campo = await self.page.query_selector('input[type="email"]')
                if placeholder.lower() not in ("email", "correo"):
                    campo = None
            if campo:
                await campo.fill(valor)
                logger.info(f"Rellenado: {placeholder} = {valor}")
                return True
            logger.info(f"Campo no encontrado: {placeholder}")
            return False
        except Exception as e:
            logger.error(f"Error rellenando '{placeholder}': {e}")
            return False

    async def auto_registro(self, url: str, datos: dict) -> dict:
        """
        Auto-registro en una web: abre la URL, busca 'registrarse'/'sign up', clica,
        rellena el formulario con los datos, y envía.
        """
        if not await self.abrir_url(url):
            return {"ok": False, "error": "No se pudo abrir la URL"}
        await asyncio.sleep(2)

        # Paso 1: Buscar botón de registro
        clicado = False
        for texto in [
            "Registrarse",
            "Sign up",
            "Crear cuenta",
            "Sign Up",
            "Registro",
            "Únete",
            "Empezar gratis",
            "Get started",
            "Alta",
            "Suscribirse",
        ]:
            if await self.buscar_y_clicar(texto):
                clicado = True
                break

        if not clicado:
            return {"ok": False, "error": "No se encontró botón de registro"}

        await asyncio.sleep(2)

        # Paso 2: Rellenar formulario
        campos_rellenados = 0
        for placeholder, valor in datos.items():
            if await self.rellenar_campo(placeholder, valor):
                campos_rellenados += 1

        # Paso 3: Buscar botón de envío
        enviado = False
        for texto in [
            "Enviar",
            "Submit",
            "Crear cuenta",
            "Registrarse",
            "Continuar",
            "Sign up",
            "Crear",
        ]:
            if await self.buscar_y_clicar(texto):
                enviado = True
                break

        return {
            "ok": True,
            "clicado": clicado,
            "campos_rellenados": campos_rellenados,
            "enviado": enviado,
        }


# Funciones de conveniencia
async def abrir_url(url: str, headless: bool = True) -> BrowserAgent | None:
    """
    Abrir URL en el navegador

    Args:
        url: URL a abrir
        headless: Ejecutar en modo headless

    Returns:
        Instancia de BrowserAgent o None si falla
    """
    agent = BrowserAgent(headless=headless)
    if await agent.connect():
        if await agent.abrir_url(url):
            return agent
    await agent.close()
    return None


async def capturar_pantalla(path: str, agent: BrowserAgent) -> bool:
    """
    Capturar screenshot

    Args:
        path: Ruta donde guardar
        agent: Instancia de BrowserAgent

    Returns:
        True si se capturó correctamente
    """
    return await agent.capturar_pantalla(path)


async def copiar_texto(selector: str, agent: BrowserAgent) -> str | None:
    """
    Extraer texto de elemento

    Args:
        selector: Selector CSS
        agent: Instancia de BrowserAgent

    Returns:
        Texto del elemento o None
    """
    return await agent.copiar_texto(selector)


if __name__ == "__main__":
    # Prueba del browser agent
    import asyncio

    async def main():
        async with BrowserAgent(headless=False) as agent:
            if await agent.abrir_url("https://example.com"):
                text = await agent.copiar_texto("h1")
                print(f"Título: {text}")
                await agent.capturar_pantalla("screenshots/example.png")

    asyncio.run(main())
