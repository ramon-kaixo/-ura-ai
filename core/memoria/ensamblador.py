"""Ensamblador de contexto RAG con asignación por residuo.

Chunks se podan primero (si exceden ventana). Historial recibe el 100%
del presupuesto restante. Ratio dinámico: 2.0 código, 3.8 prosa.
"""

import logging

log = logging.getLogger("ura.ensamblador")


class ContextWindowGuard:
    def __init__(self, limite_tokens_ctx: int = 4096, margen_salida: int = 1024):
        self.limite_entrada_tokens = limite_tokens_ctx - margen_salida
        self.OVERHEAD_MSG = 4

    def _estimar_tokens_atomico(self, texto: str) -> int:
        """Ratio dinámico: 2.0 para código denso, 3.8 para prosa/instrucciones."""
        caracteres_criticos = sum(texto.count(c) for c in ["{", "}", "[", "]", "_", "=", "/", "\\"])
        ratio = 2.0 if caracteres_criticos > 5 else 3.8
        return int(len(texto) / ratio) + self.OVERHEAD_MSG

    def ensamblar_prompt_seguro(
        self,
        query: str,
        chunks_reranked: list[dict],
        historial: list[dict] | None = None,
    ) -> dict:
        if historial is None:
            historial = []

        system_instruction = (
            "Eres URA, un asistente técnico experto. Responde basándote estrictamente "
            "en el contexto provisto. Si la información no está, di que no lo sabes."
        )

        # 1. Costes fijos base
        tokens_sistema = self._estimar_tokens_atomico(system_instruction)
        tokens_query = self._estimar_tokens_atomico(query)
        coste_fijo_total = tokens_sistema + tokens_query

        # 2. Pre-calcular pesos de chunks (una sola pasada)
        chunks_evaluados = [
            {"datos": c, "tokens": self._estimar_tokens_atomico(c.get("payload", {}).get("texto", ""))}
            for c in chunks_reranked
        ]

        # 3. Poda lineal de chunks (solo si ellos SOLOS exceden la ventana)
        while chunks_evaluados and (
            coste_fijo_total + sum(ch["tokens"] for ch in chunks_evaluados) > self.limite_entrada_tokens
        ):
            log.warning("Chunks RAG exceden ventana. Evictando menos relevante.")
            chunks_evaluados.pop()

        tokens_chunks = sum(ch["tokens"] for ch in chunks_evaluados)

        # 4. Historial: consume el 100% del espacio remanente (asignación dinámica)
        presupuesto_historial = self.limite_entrada_tokens - (coste_fijo_total + tokens_chunks)
        historial_seguro: list[dict] = []
        tokens_historial = 0

        for mensaje in reversed(historial):
            t_msg = self._estimar_tokens_atomico(mensaje.get("content", ""))
            if tokens_historial + t_msg > presupuesto_historial:
                break
            historial_seguro.append(mensaje)
            tokens_historial += t_msg
        historial_seguro.reverse()

        # 5. Construcción final
        texto_contexto = "\n\n".join(
            f"--- DOCUMENTO ---\n{ch['datos'].get('payload', {}).get('texto', '')}" for ch in chunks_evaluados
        )
        prompt_base = f"CONTEXTO:\n{texto_contexto}\n\nPREGUNTA:\n{query}"

        mensajes_finales = [{"role": "system", "content": system_instruction}]
        mensajes_finales.extend(historial_seguro)
        mensajes_finales.append({"role": "user", "content": prompt_base})

        total = coste_fijo_total + tokens_chunks + tokens_historial
        log.info(
            "Prompt: ~%d/%d tokens (chunks=%d, historial=%d).",
            total,
            self.limite_entrada_tokens,
            tokens_chunks,
            tokens_historial,
        )
        return {"messages": mensajes_finales, "tokens_estimados": total}
