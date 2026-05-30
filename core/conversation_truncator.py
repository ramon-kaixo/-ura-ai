#!/usr/bin/env python3
"""
Módulo: core/conversation_truncator.py
Propósito: Trunca conversaciones largas para no exceder límites de tokens usando caché de resúmenes.
Dependencias principales: hashlib, collections.deque, pathlib, json
Reglas especiales: Usar SHA256 para hashing. No truncar mensajes a mitad. Mantener contexto de 10 mensajes.
"""

import hashlib


class ConversationTruncator:
    """
    Trunca conversaciones largas resumiendo mensajes antiguos.

    Uso:
        ct = ConversationTruncator(max_tokens=3000)
        truncated = ct.truncate(history_messages)
    """

    def __init__(self, max_tokens: int = 3000, summary_model: str = "llama3.2:3b"):
        self.max_tokens = max_tokens
        self.summary_model = summary_model
        self._summary_cache: dict[str, str] = {}  # Hash → summary

    def estimate_tokens(self, text: str) -> int:
        """Estimación rápida de tokens (4 chars ≈ 1 token)."""
        return max(1, len(text) // 4)

    def truncate(self, messages: list[dict]) -> list[dict]:
        """
        Trunca la lista de mensajes si excede max_tokens.
        Los mensajes más antiguos se resumen en uno solo.

        Args:
            messages: Lista de {"role": "user"|"assistant", "content": str}

        Returns:
            Lista truncada de mensajes.
        """
        total = sum(self.estimate_tokens(m["content"]) for m in messages)

        if total <= self.max_tokens:
            return messages

        # Encontrar punto de corte
        running = 0
        cut_index = len(messages)

        for i, m in enumerate(messages):
            running += self.estimate_tokens(m["content"])
            if running > self.max_tokens * 0.7:  # 70% para mensajes recientes
                cut_index = i
                break

        if cut_index <= 0:
            return [messages[-1]] if messages else []

        old_messages = messages[:cut_index]
        recent_messages = messages[cut_index:]

        # Intentar resumir los antiguos
        summary = self._summarize(old_messages)

        if summary:
            result = [
                {"role": "system", "content": f"[Resumen de conversación anterior]\n{summary}"}
            ]
            result.extend(recent_messages)
            return result

        return recent_messages

    def _summarize(self, messages: list[dict]) -> str | None:
        """Resume mensajes antiguos usando Ollama."""
        text = "\n".join(f"{m['role']}: {m['content'][:500]}" for m in messages[-10:])
        text_hash = hashlib.sha256(text.encode()).hexdigest()

        if text_hash in self._summary_cache:
            return self._summary_cache[text_hash]

        try:
            import requests

            r = requests.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": self.summary_model,
                    "prompt": (
                        "Resume esta conversación en 2-3 frases en español. "
                        "Solo incluye los hechos clave y decisiones importantes:\n\n"
                        f"{text[:2000]}"
                    ),
                    "stream": False,
                    "options": {"max_tokens": 150, "temperature": 0.2},
                },
                timeout=20,
            )
            summary = r.json().get("response", "").strip()
            if summary:
                self._summary_cache[text_hash] = summary
                # Limitar caché
                if len(self._summary_cache) > 50:
                    oldest = next(iter(self._summary_cache))
                    del self._summary_cache[oldest]
                return summary
        except Exception:
            pass

        return None


# ── Singleton ──────────────────────────────────────────────

_truncator: ConversationTruncator | None = None


def get_conversation_truncator() -> ConversationTruncator:
    global _truncator
    if _truncator is None:
        _truncator = ConversationTruncator()
    return _truncator
