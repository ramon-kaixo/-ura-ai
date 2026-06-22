"""Motor de inferencia seguro con liberación garantizada de VRAM ante CancelledError.

InferenciaStreamEngine:
  Consume el payload del ensamblador (ContextWindowGuard) y transmite tokens
  con liberación asegurada del slot de GPU incluso si el cliente se desconecta.
"""

import asyncio
import logging
from collections.abc import AsyncGenerator
from typing import Any

log = logging.getLogger("ura.inferencia")


class InferenciaStreamEngine:
    """Streaming asíncrono con blindaje contra tareas zombis en VRAM."""

    def __init__(self, model_router: Any, cliente_ollama: Any) -> None:
        self.router = model_router
        self.client = cliente_ollama

    async def ejecutar_inferencia_RAG(
        self,
        modelo: str,
        payload_seguro: dict,
    ) -> AsyncGenerator[str, None]:
        """Consume el payload del ensamblador y transmite tokens.
        Garantiza liberación del slot VRAM mediante captura de CancelledError.
        """
        try:
            slot_adquirido = await self.router.adquirir_slot_vram(modelo)
        except asyncio.CancelledError:
            log.warning("Inferencia cancelada antes de adquirir slot VRAM para %s.", modelo)
            raise

        if not slot_adquirido:
            yield "Error 504: Tiempo de espera en cola excedido sin slots de GPU disponibles."
            return

        log.info(
            "Slot GPU asignado para %s. Tokens estimados: %d.",
            modelo,
            payload_seguro.get("tokens_estimados", 0),
        )

        try:
            async for chunk in await self.client.chat(
                model=modelo,
                messages=payload_seguro["messages"],
                stream=True,
            ):
                token = chunk.get("message", {}).get("content", "")
                yield token
                await asyncio.sleep(0)

        except asyncio.CancelledError:
            log.warning("Conexión cerrada por el usuario mid-stream. Deteniendo generación.")
            raise

        except Exception as e:
            log.exception("Fallo en el flujo de inferencia: %s", e)
            yield f"\n[Fallo en la respuesta del modelo: {e!s}]"

        finally:
            await self.router.liberar_slot_vram(modelo)
            log.info("Slot de GPU devuelto al pool para %s.", modelo)
