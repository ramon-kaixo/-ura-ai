#!/usr/bin/env python3
"""
Práctica autónoma de formularios web + investigación — URA aprende cuando está sola.
Combina: práctica de formularios + investigación con agentes existentes.
"""

import asyncio
import json
import logging
import random
import sys
import subprocess
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.browser_agent import BrowserAgent

logger = logging.getLogger("ura_autonomous")
FORM_LOG = Path(__file__).parent.parent / "logs" / "form_practice.jsonl"
KNOWLEDGE_BASE = Path(__file__).parent.parent / "biblioteca" / "conocimiento_autonomo"
KNOWLEDGE_BASE.mkdir(parents=True, exist_ok=True)

# Webs seguras con formularios de registro gratuitos
SAFE_SITES = [
    "https://github.com/signup",
    "https://www.wordpress.com/start/user",
    "https://www.canva.com/signup",
    "https://www.figma.com/signup",
    "https://www.notion.so/signup",
    "https://slack.com/get-started",
    "https://trello.com/signup",
    "https://airtable.com/signup",
    "https://miro.com/signup",
    "https://linear.app/signup",
    "https://vercel.com/signup",
    "https://netlify.com/signup",
    "https://render.com/signup",
    "https://replit.com/signup",
    "https://glitch.com/signup",
]

TEST_NAMES = [
    "María García",
    "Carlos López",
    "Ana Martínez",
    "Pedro Sánchez",
    "Laura Fernández",
    "José Ruiz",
    "Carmen Jiménez",
    "David Torres",
]
TEST_DOMAINS = ["gmail.com", "outlook.com", "yahoo.com", "proton.me", "icloud.com"]


def generate_test_data() -> dict:
    """Genera datos de prueba realistas para formularios."""
    import random as _random
    import unicodedata

    name = _random.choice(TEST_NAMES)
    # Normalizar: quitar acentos para email
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    first = ascii_name.lower().replace(" ", ".")
    domain = _random.choice(TEST_DOMAINS)
    email = f"{first}.test{_random.randint(100, 999)}@{domain}"
    return {
        "name": name,
        "email": email,
        "password": f"Test{_random.randint(1000, 9999)}!",
        "username": ascii_name.lower().replace(" ", "") + str(_random.randint(10, 99)),
    }


async def practice_one_site(url: str, data: dict) -> dict:
    """Practica registro en un sitio: rellena todo menos enviar."""
    agent = None
    try:
        agent = BrowserAgent(headless=True)
        connected = await agent.connect()
        if not connected:
            return {"site": url, "ok": False, "error": "No se pudo conectar"}

        await agent.abrir_url(url)
        await asyncio.sleep(4)

        # Explorar: buscar campos de formulario
        page = agent.page
        if not page:
            return {"site": url, "ok": False, "error": "Página no disponible"}

        # Encontrar todos los campos de formulario visibles
        campos_encontrados = []
        botones_registro = []
        try:
            inputs = await page.query_selector_all("input:not([type='hidden'])")
            for inp in inputs:
                try:
                    info = await inp.evaluate(
                        """el => ({
                        name: el.name, type: el.type, placeholder: el.placeholder,
                        id: el.id, required: el.required
                    })"""
                    )
                    if info["type"] not in ("submit", "button", "hidden"):
                        campos_encontrados.append(info)
                except Exception as e:
                    logger.warning(f"Error silencioso en form_practice.scan_fields: {e}")
                    # fallback: continuar

            # Buscar botones de registro
            for texto in [
                "Sign up",
                "Create",
                "Registrarse",
                "Get started",
                "Sign Up",
                "Crear cuenta",
                "Empezar",
            ]:
                try:
                    btns = await page.query_selector_all('button, a, input[type="submit"]')
                    for btn in btns:
                        try:
                            text = await btn.inner_text()
                            if texto.lower() in text.lower():
                                botones_registro.append(
                                    {"texto": text.strip()[:50], "tag": "button/link"}
                                )
                        except Exception as e:
                            logger.warning(f"Error silencioso en form_practice.scan_buttons: {e}")
                            # fallback: continuar
                except Exception as e:
                    logger.warning(f"Error silencioso en form_practice.scan_outer: {e}")
                    # fallback: continuar
        except Exception as e:
            logger.warning(f"Error explorando campos: {e}")

        # Cerrar limpiamente
        try:
            await agent.close()
        except Exception:
            pass  # silenciado intencional: cleanup del agente al cerrar

        result = {
            "site": url,
            "ok": True,
            "campos_encontrados": len(campos_encontrados),
            "campos": campos_encontrados[:10],
            "botones_registro": list({b["texto"]: b for b in botones_registro}.values())[:5],
            "timestamp": datetime.now().isoformat(),
        }
        logger.info(f"✅ {url}: {len(campos_encontrados)} campos, {len(botones_registro)} botones")
        return result

    except Exception as e:
        if agent:
            try:
                await agent.close()
            except Exception as e:
                logger.warning(f"Error silencioso en form_practice.collect_results: {e}")
                # fallback: continuar  # silenciado intencional: cleanup al cerrar agente con error
        return {"site": url, "ok": False, "error": str(e)}


async def run_practice_cycle():
    """Ciclo de práctica: elige webs aleatorias y practica."""
    site = random.choice(SAFE_SITES)
    data = generate_test_data()
    result = await practice_one_site(site, data)

    # Guardar aprendizaje
    FORM_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(FORM_LOG, "a") as f:
        f.write(json.dumps(result) + "\n")

    return result


async def run_research_cycle():
    """Ciclo de investigación: usa el agente investigador existente."""
    try:
        # Ejecutar el agente investigador semanal
        result = subprocess.run(
            [sys.executable, "-m", "agents.agente_investigador_ia"],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(Path(__file__).parent.parent),
        )
        if result.returncode == 0 and result.stdout:
            logger.info(f"Investigación completada: {len(result.stdout)} bytes")
            return {"ok": True, "output": result.stdout[:500]}
        return {"ok": False, "error": result.stderr[:200]}
    except Exception as e:
        return {"ok": False, "error": str(e)}


async def run_full_autonomous_cycle():
    """Ciclo completo: práctica de formularios + investigación."""
    results = {}
    # 1 de cada 3 ciclos: investigar
    if random.random() < 0.33:
        results["research"] = await run_research_cycle()
    # 2 de cada 3 ciclos: practicar formularios
    else:
        results["forms"] = await run_practice_cycle()
    return results


def get_practice_stats() -> dict:
    """Estadísticas de aprendizaje acumulado."""
    if not FORM_LOG.exists():
        return {"total": 0, "sites": []}
    sites = []
    campos_total = 0
    with open(FORM_LOG) as f:
        for line in f:
            try:
                r = json.loads(line)
                if r.get("ok"):
                    sites.append(r["site"])
                    campos_total += r.get("campos_encontrados", 0)
            except Exception:
                pass
    return {
        "total_sesiones": len(sites),
        "sitios_visitados": len(set(sites)),
        "campos_totales": campos_total,
        "ultimo": sites[-1] if sites else None,
    }


def get_knowledge_stats() -> dict:
    """Estadísticas de la biblioteca de conocimiento."""
    if not KNOWLEDGE_BASE.exists():
        return {"total": 0, "categories": {}}
    categories = {}
    total = 0
    for f in KNOWLEDGE_BASE.rglob("*.json"):
        cat = f.parent.name
        categories[cat] = categories.get(cat, 0) + 1
        total += 1
    return {"total": total, "categories": categories}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = asyncio.run(run_full_autonomous_cycle())
    print(json.dumps(result, indent=2))
    print(f"\n📝 Formularios: {get_practice_stats()}")
    print(f"📚 Biblioteca: {get_knowledge_stats()}")
