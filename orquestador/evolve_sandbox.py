#!/usr/bin/env python3
"""Sandbox de evolucion — reescribe macros fallidas usando GX10."""

import logging
import subprocess

logger = logging.getLogger("EvolveSandbox")


class EvolveSandbox:
    """Repara macros fallidas enviandolas al GX10 para reescritura."""

    def __init__(self, gx10_alias: str = "gx10") -> None:
        self.gx10 = gx10_alias

    def reparar_macro(self, macro_code: str, manual_fragment: str) -> str | None:
        """Envia una macro fallida al GX10 para que la reescriba.

        Args:
            macro_code: Codigo Python de la macro fallida.
            manual_fragment: Fragmento del manual relevante.

        Returns:
            Nuevo codigo generado o None si fallo.
        """
        prompt = (
            f"Macro fallida:\n{macro_code}\n\n"
            f"Segun manual:\n{manual_fragment}\n"
            f"Reescribela en Python con type hints."
        )
        try:
            cmd = ["ssh", self.gx10, "ollama", "run", "qwen2.5-coder", prompt]
            resultado = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
            )
            nuevo_codigo = resultado.stdout.strip()
            if nuevo_codigo:
                logger.info("Macro reparada por GX10")
                return nuevo_codigo
        except Exception as exc:
            logger.error("Error reparando macro: %s", exc)
        return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    sandbox = EvolveSandbox()
    print("Sandbox de evolucion listo")
