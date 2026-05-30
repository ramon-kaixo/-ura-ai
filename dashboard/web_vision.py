#!/usr/bin/env python3
"""
URA Web Vision — Lee páginas web visualmente con llava.

Cuando los buscadores bloquean curl/texto, URA abre el navegador con Playwright,
hace un pantallazo de la página, y usa llava para leer el contenido visualmente.
Indetectable: el sitio ve a un humano normal usando Chrome.

Flujo:
  1. browser_agent abre la web
  2. Pantallazo de la página visible
  3. llava analiza la imagen y extrae el contenido
  4. Guarda el resultado en la biblioteca
"""

import asyncio
import base64
import json
import logging
import sys
import time
from datetime import datetime, UTC
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent.parent))

logger = logging.getLogger("web_vision")
VISION_DIR = Path(__file__).parent.parent / "biblioteca" / "vision_web"
VISION_DIR.mkdir(parents=True, exist_ok=True)


async def leer_pagina_visualmente(url: str, pregunta: str = "") -> dict:
    """
    Abre una web con Playwright, captura la pantalla, y llava lee el contenido.
    Esto funciona incluso cuando curl/texto es bloqueado.
    """
    try:
        from core.browser_agent import BrowserAgent

        agent = BrowserAgent(headless=True)
        if not await agent.connect():
            return {"ok": False, "error": "Browser no disponible"}

        await agent.abrir_url(url)
        await asyncio.sleep(4)  # Esperar carga completa

        page = agent.page
        if not page:
            await agent.close()
            return {"ok": False, "error": "Página no cargó"}

        # Scroll para cargar contenido lazy
        try:
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(1)
            await page.evaluate("window.scrollTo(0, 0)")
            await asyncio.sleep(0.5)
        except Exception:
            pass

        # Capturar pantalla
        screenshot_path = VISION_DIR / f"screenshot_{int(time.time())}.png"
        await page.screenshot(path=str(screenshot_path), full_page=False)
        await agent.close()

        # Analizar con llava
        with open(screenshot_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode()

        prompt = (
            f"Estás viendo una página web ({url}). "
            f"{pregunta if pregunta else 'Describe el contenido principal de esta página en español. '}"
            f"Incluye títulos, enlaces importantes y cualquier formulario de registro que veas. "
            f"Máximo 5 frases."
        )

        r = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "llava:latest",
                "prompt": prompt,
                "images": [img_b64],
                "stream": False,
                "options": {"temperature": 0.3, "max_tokens": 300},
            },
            timeout=60,
        )
        descripcion = r.json().get("response", "No se pudo analizar la página")

        # Guardar resultado
        resultado = {
            "url": url,
            "timestamp": datetime.now(UTC).isoformat(),
            "pregunta": pregunta,
            "descripcion": descripcion.strip(),
            "screenshot": str(screenshot_path.name),
            "metodo": "web_vision",
        }

        filename = f"{datetime.now(UTC).strftime('%Y%m%d_%H%M')}_{hash(url) % 10000}.json"
        (VISION_DIR / filename).write_text(json.dumps(resultado, ensure_ascii=False, indent=2))

        return {"ok": True, "descripcion": descripcion.strip(), "url": url}

    except Exception as e:
        return {"ok": False, "error": str(e)}


async def buscar_y_leer_visualmente(query: str) -> dict:
    """
    Busca en Google y lee los resultados visualmente.
    Combina browser + llava para saltarse bloqueos anti-bot.
    """
    url = f"https://www.google.com/search?q={query.replace(' ', '+')}&hl=es"
    return await leer_pagina_visualmente(
        url, pregunta=f"Busqué '{query}'. Dame los resultados principales."
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("👁️ URA Web Vision — test")

    result = asyncio.run(
        leer_pagina_visualmente(
            "https://www.google.com/search?q=mejor+framework+agentes+IA+2025&hl=es",
            "Dame los 3 primeros resultados de búsqueda con sus títulos y descripciones.",
        )
    )
    print(f"OK: {result.get('ok')}")
    print(f"URA ve: {result.get('descripcion', 'ERROR')[:500]}")
