#!/usr/bin/env python3
"""
Sistema Multi-Silla — Validación externa de conocimiento.

URA consulta a 3 IAs externas (Gemini, ChatGPT, Claude) en sus versiones gratuitas.
Cada una responde lo mismo. URA descarga, filtra, cruza y solo se queda con lo verificado.
Si se acaba el tiempo gratuito, pausa y continúa después.

Pipeline:
  Internet (búsqueda) → Filtro interno → 3 sillas externas → Cruce → Conocimiento validado
"""

import asyncio
import hashlib
import json
import logging
import sys
from datetime import datetime, UTC
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent.parent))

import requests

logger = logging.getLogger("multi_chair")

SILLAS_DIR = Path(__file__).parent.parent / "biblioteca" / "consultas_sillas"
SILLAS_DIR.mkdir(parents=True, exist_ok=True)

# ── Configuración de sillas ────────────────────────────────────────────────
CHAIRS = [
    {
        "nombre": "Gemini",
        "url": "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent",
        "auth_header": "key",
        "env_var": "GEMINI_API_KEY",
        "free_limit_per_day": 1500,
        "used_today": 0,
        # Por delante (browser)
        "web_url": "https://gemini.google.com/app",
        "web_selector_input": "rich-textarea",
        "web_selector_response": "message-content",
    },
    {
        "nombre": "ChatGPT",
        "url": "https://api.openai.com/v1/chat/completions",
        "auth_header": "Authorization",
        "auth_prefix": "Bearer ",
        "env_var": "OPENAI_API_KEY",
        "free_limit_per_day": 200,
        "used_today": 0,
        "web_url": "https://chat.openai.com",
        "web_selector_input": "#prompt-textarea",
        "web_selector_response": "div[data-message-author-role='assistant']",
    },
    {
        "nombre": "Claude",
        "url": "https://api.anthropic.com/v1/messages",
        "auth_header": "x-api-key",
        "env_var": "ANTHROPIC_API_KEY",
        "free_limit_per_day": 100,
        "used_today": 0,
        "web_url": "https://claude.ai/chat",
        "web_selector_input": "div[contenteditable='true']",
        "web_selector_response": "div[data-testid='assistant-message']",
    },
]


def _load_usage() -> dict:
    """Carga contadores de uso diario."""
    usage_file = SILLAS_DIR / "usage_today.json"
    if usage_file.exists():
        try:
            data = json.loads(usage_file.read_text())
            if data.get("date") == datetime.now(UTC).strftime("%Y-%m-%d"):
                return data
        except Exception:
            pass
    return {"date": datetime.now(UTC).strftime("%Y-%m-%d"), "chairs": {}}


def _save_usage(usage: dict):
    (SILLAS_DIR / "usage_today.json").write_text(json.dumps(usage, indent=2))


def _puede_consultar(chair: dict) -> bool:
    """Verifica si una silla tiene cuota disponible hoy."""
    usage = _load_usage()
    name = chair["nombre"]
    used = usage.get("chairs", {}).get(name, 0)
    limit = chair["free_limit_per_day"]
    return used < limit


def _registrar_uso(chair: dict):
    """Registra una consulta consumida."""
    usage = _load_usage()
    name = chair["nombre"]
    usage["chairs"][name] = usage.get("chairs", {}).get(name, 0) + 1
    _save_usage(usage)


def consultar_silla(chair: dict, pregunta: str) -> dict:
    """Consulta a una silla externa. Respeta límites gratuitos."""
    if not _puede_consultar(chair):
        return {"ok": False, "chair": chair["nombre"], "error": "Límite gratuito alcanzado"}

    api_key = chair.get("env_var", "")
    if api_key:
        api_key = __import__("os").getenv(api_key, "")
    if not api_key:
        return {"ok": False, "chair": chair["nombre"], "error": "Sin API key"}

    try:
        headers = {"Content-Type": "application/json"}
        if chair["auth_header"] == "key":
            url = f"{chair['url']}?key={api_key}"
            body = {"contents": [{"parts": [{"text": pregunta}]}]}
        elif chair["nombre"] == "ChatGPT":
            url = chair["url"]
            headers["Authorization"] = f"Bearer {api_key}"
            body = {
                "model": "gpt-3.5-turbo",
                "messages": [{"role": "user", "content": pregunta}],
                "max_tokens": 300,
            }
        else:  # Claude
            url = chair["url"]
            headers["x-api-key"] = api_key
            headers["anthropic-version"] = "2023-06-01"
            body = {
                "model": "claude-3-haiku-20240307",
                "max_tokens": 300,
                "messages": [{"role": "user", "content": pregunta}],
            }

        r = requests.post(url, headers=headers, json=body, timeout=30)
        _registrar_uso(chair)

        if r.status_code == 200:
            data = r.json()
            # Extraer respuesta según formato
            if "candidates" in data:  # Gemini
                resp = data["candidates"][0]["content"]["parts"][0]["text"]
            elif "choices" in data:  # ChatGPT
                resp = data["choices"][0]["message"]["content"]
            elif "content" in data:  # Claude
                resp = data["content"][0]["text"]
            else:
                resp = str(data)[:500]
            return {"ok": True, "chair": chair["nombre"], "respuesta": resp}
        else:
            return {
                "ok": False,
                "chair": chair["nombre"],
                "error": f"HTTP {r.status_code}",
                "respuesta": r.text[:200],
            }
    except Exception as e:
        return {"ok": False, "chair": chair["nombre"], "error": str(e)}


async def consultar_todas(pregunta: str) -> dict:
    """Consulta a TODAS las sillas. Si API bloquea → browser automático."""
    resultados = {}

    for chair in CHAIRS:
        # Intentar API (por detrás)
        r = consultar_silla(chair, pregunta)
        # Si falla, intentar browser (por delante)
        if not r.get("ok") and r.get("error") in ("Sin API key", "HTTP 403", "HTTP 429"):
            logger.info(f"{chair['nombre']}: API bloqueada → probando browser...")
            r = await consultar_por_delante(chair, pregunta)
        resultados[chair["nombre"]] = r

    # Guardar conversación
    consulta = {
        "timestamp": datetime.now(UTC).isoformat(),
        "pregunta": pregunta,
        "hash_pregunta": hashlib.sha256(pregunta.encode()).hexdigest()[:12],
        "sillas_consultadas": disponibles,
        "resultados": resultados,
    }
    filename = f"{datetime.now(UTC).strftime('%Y%m%d_%H%M')}_{hashlib.sha256(pregunta.encode()).hexdigest()[:8]}.json"
    (SILLAS_DIR / filename).write_text(json.dumps(consulta, indent=2, ensure_ascii=False))

    return consulta


async def consultar_por_delante(chair: dict, pregunta: str) -> dict:
    """Consulta POR DELANTE (navegador) — indetectable, como un humano."""
    try:
        from core.browser_agent import BrowserAgent

        agent = BrowserAgent(headless=True)
        if not await agent.connect():
            return {"ok": False, "chair": chair["nombre"], "error": "Browser no disponible"}

        await agent.abrir_url(chair["web_url"])
        await asyncio.sleep(5)

        page = agent.page
        if not page:
            await agent.close()
            return {"ok": False, "chair": chair["nombre"], "error": "Página no cargó"}

        try:
            input_el = await page.query_selector(chair["web_selector_input"])
            if input_el:
                await input_el.click()
                await asyncio.sleep(0.5)
                await input_el.fill(pregunta)
                await page.keyboard.press("Enter")
                await asyncio.sleep(8)
        except Exception:
            pass

        respuesta = ""
        try:
            resp_el = await page.query_selector(chair["web_selector_response"])
            if resp_el:
                respuesta = await resp_el.inner_text()
        except Exception:
            respuesta = await agent.copiar_texto("body") or ""

        await agent.close()

        if respuesta and len(respuesta) > 20:
            _registrar_uso(chair)
            return {
                "ok": True,
                "chair": chair["nombre"],
                "respuesta": respuesta[:1000],
                "metodo": "browser",
            }
        return {"ok": False, "chair": chair["nombre"], "error": "No se pudo leer respuesta"}
    except Exception as e:
        return {"ok": False, "chair": chair["nombre"], "error": str(e)}


def generar_pregunta_trampa(tema: str) -> str:
    """Genera una pregunta trampa para evaluar profundidad de las sillas."""
    return (
        f"Sobre el tema '{tema}', dime: ¿cuál es el mayor error que cometen "
        f"los principiantes y por qué la solución obvia es incorrecta? "
        f"Responde en español, máximo 3 frases."
    )


def get_sillas_stats() -> dict:
    """Estadísticas de uso de sillas."""
    usage = _load_usage()
    stats = {"fecha": usage["date"]}
    for chair in CHAIRS:
        name = chair["nombre"]
        used = usage.get("chairs", {}).get(name, 0)
        stats[name] = {
            "usadas_hoy": used,
            "limite": chair["free_limit_per_day"],
            "restantes": chair["free_limit_per_day"] - used,
        }
    total_consultas = len(list(SILLAS_DIR.glob("*.json")))
    stats["total_consultas_guardadas"] = total_consultas
    return stats


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("🪑 Sistema Multi-Silla — test")

    stats = get_sillas_stats()
    print("\n📊 Uso hoy:")
    for chair in CHAIRS:
        s = stats.get(chair["nombre"], {})
        print(f"   {chair['nombre']}: {s.get('usadas_hoy', 0)}/{s.get('limite', 0)}")

    # Generar pregunta trampa
    trampa = generar_pregunta_trampa("agentes IA para restaurantes")
    print(f"\n🎯 Pregunta trampa: {trampa}")
