#!/usr/bin/env python3
"""
Verificador de salud de OpenClaw.

Verifica si OpenClaw está disponible y respondiendo correctamente.
Usa CLI: openclaw agent --local --message "responde OK" --json
"""

from __future__ import annotations

import asyncio
import json
import logging

logger = logging.getLogger("openclaw_health")


async def check_openclaw_ready(
    url: str = "http://localhost:18789",
    timeout: int = 90,
    max_retries: int = 1,
    retry_delay: int = 2,
) -> bool:
    """
    Verifica si OpenClaw está listo y respondiendo vía CLI.

    OpenClaw ahora usa qwen2.5:3b-instruct que responde en ~70s.
    Timeout aumentado a 90s para acomodar este tiempo.

    Args:
        url: URL base del endpoint de OpenClaw (no usado en CLI mode)
        timeout: Timeout en segundos para cada intento
        max_retries: Número máximo de reintentos
        retry_delay: Segundos de espera entre reintentos

    Returns:
        True si OpenClaw CLI responde correctamente, False si timeout o error
    """
    for attempt in range(max_retries):
        try:
            # Health check con mensaje simple
            result = await asyncio.create_subprocess_exec(
                "openclaw",
                "agent",
                "--local",
                "--agent",
                "main",
                "--message",
                "test",
                "--json",
                "--timeout",
                str(timeout),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(result.communicate(), timeout=timeout + 10)

            if result.returncode == 0:
                try:
                    data = json.loads(stdout.decode())
                    # Verificar que no esté abortado
                    if data.get("aborted", False):
                        logger.warning(
                            f"[HEALTH] OpenClaw CLI abortó la tarea (intentos: {attempt + 1})"
                        )
                        return False
                    # Si tiene meta y agentMeta, está funcionando
                    if "meta" in data and "agentMeta" in data["meta"]:
                        logger.info(f"[HEALTH] OpenClaw CLI listo (intentos: {attempt + 1})")
                        return True
                except json.JSONDecodeError:
                    pass

            logger.warning(
                f"[HEALTH] OpenClaw CLI no responde correctamente (intentos: {attempt + 1})"
            )

        except TimeoutError:
            logger.warning(f"[HEALTH] OpenClaw CLI timeout (intentos: {attempt + 1})")
        except FileNotFoundError:
            logger.warning(f"[HEALTH] Comando 'openclaw' no encontrado (intentos: {attempt + 1})")
            return False
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[HEALTH] Error inesperado: {e} (intentos: {attempt + 1})")

        if attempt < max_retries - 1:
            await asyncio.sleep(retry_delay)

    logger.error(f"[HEALTH] OpenClaw CLI no disponible después de {max_retries} intentos")
    return False


if __name__ == "__main__":
    # Test del health check
    async def test():
        logging.basicConfig(level=logging.INFO)
        result = await check_openclaw_ready()
        print(f"OpenClaw ready: {result}")

    asyncio.run(test())
