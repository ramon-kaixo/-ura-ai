#!/usr/bin/env python3
"""
Modo Máximo de Investigación — URA usa TODOS los Ollamas cuando el Mac está inactivo.

Activa todos los modelos disponibles, ejecuta el pipeline multi-agente a máxima
velocidad, y libera RAM cuando detecta que el usuario vuelve.
"""

import asyncio
import json
import logging
import subprocess
import sys
import time
from datetime import datetime, UTC
from pathlib import Path

import psutil
import requests

sys.path.insert(0, str(Path(__file__).parent.parent))

logger = logging.getLogger("max_research")
STATE_FILE = Path(__file__).parent.parent / "logs" / "max_research_state.json"

OLLAMA_URL = "http://localhost:11434"


def get_available_models() -> list[str]:
    """Obtiene todos los modelos disponibles en Ollama."""
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        return [m["name"] for m in r.json().get("models", [])]
    except Exception:
        return ["llama3.2:3b"]


def load_all_models() -> int:
    """Carga modelos inteligentemente: solo los que caben en RAM."""
    models = get_available_models()
    ram = psutil.virtual_memory()
    available_gb = ram.available / (1024**3)

    loaded = 0
    for model in models:
        # Verificar cuánta RAM necesita este modelo
        try:
            r = requests.get(f"{OLLAMA_URL}/api/show", json={"name": model}, timeout=5)
            r.json().get("model_info", {}).get("parameter_size", "0B")
        except Exception:
            pass

        # Solo cargar si quedan > 3 GB libres después
        if available_gb - 3 > loaded:
            subprocess.run(
                [
                    "curl",
                    "-s",
                    f"{OLLAMA_URL}/api/generate",
                    "-d",
                    f'{{"model":"{model}","prompt":"1","stream":false,"options":{{"max_tokens":1}}}}',
                    "-o",
                    "/dev/null",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=30,
            )
            loaded += 1
            logger.info(f"📦 {model} cargado")

    # Verificar cuántos se cargaron
    try:
        r = requests.get(f"{OLLAMA_URL}/api/ps", timeout=5)
        loaded_count = len(r.json().get("models", []))
        total_ram = sum(m.get("size", 0) for m in r.json().get("models", [])) // (1024**3)
        logger.info(f"🔥 {loaded_count} modelos — {total_ram} GB RAM")
        return loaded_count
    except Exception:
        return loaded


def unload_all_models():
    """Descarga todos los modelos para liberar RAM."""
    models = get_available_models()
    for model in models:
        try:
            requests.post(
                f"{OLLAMA_URL}/api/generate",
                json={"model": model, "prompt": "", "keep_alive": 0},
                timeout=5,
            )
        except Exception:
            pass


def is_user_active() -> bool:
    """Detecta si el usuario está usando el Mac (teclado/ratón en últimos 5 min)."""
    try:
        # Comprobar idle time de macOS (en segundos)
        result = subprocess.run(
            ["ioreg", "-c", "IOHIDSystem"], capture_output=True, text=True, timeout=5
        )
        for line in result.stdout.split("\n"):
            if "Idle" in line:
                idle_ms = int(line.split("=")[-1].strip())
                idle_minutes = idle_ms / 1000 / 60
                return idle_minutes < 5
    except Exception:
        pass
    return True  # Si no se puede detectar, asumir que está activo


def get_ram_pressure() -> float:
    """Presión de RAM (0-100). >80 = peligro."""
    return psutil.virtual_memory().percent


async def run_max_research_cycle():
    """Ejecuta el pipeline de investigación completo con todos los recursos."""
    results = {"timestamp": datetime.now(UTC).isoformat(), "actions": []}

    # 1. Investigación multi-agente
    try:
        from dashboard.multi_agent_research import ejecutar_ciclo_completo

        r = await ejecutar_ciclo_completo()
        results["actions"].append({"type": "multi_agent", "areas": r.get("areas_investigadas", 0)})
    except Exception as e:
        logger.error(f"Multi-agent error: {e}")

    # 2. Form practice
    try:
        from dashboard.autonomous_form_practice import run_full_autonomous_cycle

        r = await run_full_autonomous_cycle()
        results["actions"].append({"type": "form_practice", "result": str(r)[:200]})
    except Exception as e:
        logger.error(f"Form practice error: {e}")

    # 3. Curar conocimiento
    try:
        from dashboard.multi_agent_research import curar_conocimiento

        curados = await curar_conocimiento()
        results["actions"].append({"type": "curation", "curados": curados})
    except Exception as e:
        logger.error(f"Curation error: {e}")

    # Guardar estado
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(results, indent=2))

    return results


def run_max_mode_forever():
    """Modo adaptativo: mínimo cuando usas el Mac, máximo cuando no."""
    logger.info("🚀 Modo Máximo de Investigación iniciado")

    models_loaded = False
    cycle_count = 0

    while True:
        user_active = is_user_active()
        ram = get_ram_pressure()

        if user_active:
            # 🔵 MODO MÍNIMO — usuario trabajando
            if models_loaded:
                logger.info("👤 Usuario activo — liberando RAM, modo mínimo")
                unload_all_models()
                models_loaded = False
            # Solo 1 ciclo cada 5 minutos, con 1 modelo
            if cycle_count % 5 == 0 and ram < 80:
                try:
                    # Cargar solo 1 modelo ligero
                    subprocess.run(
                        [
                            "curl",
                            "-s",
                            f"{OLLAMA_URL}/api/generate",
                            "-d",
                            '{"model":"llama3.2:3b","prompt":"1","stream":false,"options":{"max_tokens":1}}',
                            "-o",
                            "/dev/null",
                        ],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=30,
                    )
                    asyncio.run(run_max_research_cycle())
                    logger.info(f"🔵 Ciclo mínimo completado (RAM: {ram}%)")
                except Exception as e:
                    logger.error(f"Min cycle error: {e}")
            time.sleep(60)  # 1 min entre checks en modo mínimo
            cycle_count += 1
            continue

        # 🔥 MODO MÁXIMO — usuario fuera
        if not models_loaded and ram < 85:
            logger.info(f"😴 Usuario inactivo (RAM: {ram}%) — MODO MÁXIMO")
            loaded = load_all_models()
            models_loaded = loaded > 0

        if models_loaded and ram < 90:
            try:
                asyncio.run(run_max_research_cycle())
                logger.info(f"🔥 Ciclo máximo (RAM: {ram}%)")
            except Exception as e:
                logger.error(f"Max cycle error: {e}")

        time.sleep(30)  # 30 seg entre ciclos en modo máximo


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")

    # Auto-reinicio: si crashea, vuelve a arrancar
    while True:
        try:
            run_max_mode_forever()
        except Exception as e:
            logger.error(f"💀 Crash: {e} — reiniciando en 30s")
            unload_all_models()
            time.sleep(30)
