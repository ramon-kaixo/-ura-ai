#!/usr/bin/env python3
"""
Model Utils - Paso 3A
──────────────────────
Utilidades para selección de modelos.
"""

import logging

logger = logging.getLogger(__name__)


def select_model_for_message(window, message):
    """Selecciona modelo en función de (a) RAM disponible y (b) complejidad."""
    # Saludos y confirmaciones muy cortas → modelo pequeño siempre
    if len(message) < 20 and message.lower() in ["hola", "adiós", "gracias", "ok", "sí", "no"]:
        return "llama3.2:1b"

    # Resto: el gestor de RAM decide entre 7B y 3B según memoria disponible
    if window.ram_manager:
        try:
            return window.ram_manager.pick_model_for_ram()
        except Exception as exc:
            logger.warning("pick_model_for_ram falló: %s", exc)

    # Fallback seguro si el gestor no está
    return "llama3.2:1b"


def _warmup_model_async(window):
    """Precarga el modelo seleccionado en Ollama sin bloquear la GUI."""
    from core.ram_manager import pick_model_for_ram
    import time

    try:
        model = pick_model_for_ram()
        logger.info("[warmup] Pre-calentando %s…", model)
        t0 = time.time()
        # num_predict=1 → respuesta mínima, solo sirve para cargar pesos a RAM
        try:
            window.ollama_connector.generate(
                "ok", model=model, options={"num_predict": 1, "temperature": 0}
            )
        except Exception as exc:
            logger.warning("[warmup] falló: %s", exc)
            return
        logger.info("[warmup] %s listo en %.1fs", model, time.time() - t0)
    except Exception as exc:
        logger.debug("[warmup] error: %s", exc)
