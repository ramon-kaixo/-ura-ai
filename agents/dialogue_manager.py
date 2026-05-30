#!/usr/bin/env python3
"""Dialogue manager — maintains conversational context with Redis and LLM."""

import json
import logging
import time
from typing import Any

import requests

from core.memory.episodic_memory import EpisodicMemory

try:
    import redis
except ImportError:
    redis = None

logger = logging.getLogger("DialogueManager")

OLLAMA_URL = "http://10.164.1.99:11434/api/generate"
MODEL_DIALOGO = "qwen3:32b"


class DialogueManager:
    """Manages multi-turn conversations with context and memory enrichment."""

    def __init__(
        self,
        redis_host: str = "localhost",
        redis_port: int = 6379,
        max_history: int = 5,
    ) -> None:
        self.redis_client: Any = None
        if redis is not None:
            try:
                self.redis_client = redis.Redis(
                    host=redis_host, port=redis_port, decode_responses=True
                )
            except Exception as exc:
                logger.warning("Redis no disponible: %s", exc)
        self.episodic = EpisodicMemory()
        self.max_history = max_history

    def _get_history(self, user_id: str) -> list[dict[str, Any]]:
        """Retrieves conversation history for a user.

        Args:
            user_id: Unique user identifier.

        Returns:
            List of conversation turns.
        """
        if self.redis_client is None:
            return []
        key = f"dialog:{user_id}"
        try:
            history = self.redis_client.lrange(key, -self.max_history, -1)
            return [json.loads(h) for h in history]
        except Exception as exc:
            logger.error("Error obteniendo historial: %s", exc)
            return []

    def _save_interaction(self, user_id: str, user_msg: str, bot_response: str) -> None:
        """Saves a conversation turn to Redis.

        Args:
            user_id: Unique user identifier.
            user_msg: User message.
            bot_response: Bot response.
        """
        if self.redis_client is None:
            return
        key = f"dialog:{user_id}"
        try:
            self.redis_client.rpush(
                key,
                json.dumps({"user": user_msg, "bot": bot_response, "timestamp": time.time()}),
            )
            self.redis_client.expire(key, 3600 * 24)
        except Exception as exc:
            logger.error("Error guardando interaccion: %s", exc)

    def generate_response(self, user_id: str, message: str) -> str:
        """Generates a response using LLM with conversation context.

        Args:
            user_id: Unique user identifier.
            message: User message.

        Returns:
            Bot response text.
        """
        history = self._get_history(user_id)
        prompt = ""
        for turn in history[-self.max_history :]:
            prompt += f"Usuario: {turn['user']}\nURA: {turn['bot']}\n"
        prompt += f"Usuario: {message}\nURA:"

        try:
            resp = requests.post(
                OLLAMA_URL,
                json={
                    "model": MODEL_DIALOGO,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.7, "num_predict": 150},
                },
                timeout=30,
            )
            respuesta = resp.json().get("response", "").strip()
        except Exception as exc:
            logger.error("Error en LLM: %s", exc)
            respuesta = "Lo siento, no puedo responder ahora."

        if any(kw in message.lower() for kw in ["recuerdo", "por que", "cuando"]):
            episodios = self.episodic.recordar_sucesos(message, n_resultados=1)
            if episodios:
                respuesta += f"\n\nRecuerdo que {episodios[0][:200]}"

        self._save_interaction(user_id, message, respuesta)
        return respuesta

    def clear_history(self, user_id: str) -> None:
        """Clears conversation history for a user.

        Args:
            user_id: Unique user identifier.
        """
        if self.redis_client is None:
            return
        try:
            self.redis_client.delete(f"dialog:{user_id}")
        except Exception as exc:
            logger.error("Error limpiando historial: %s", exc)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    dm = DialogueManager()
    print(dm.generate_response("test", "Hola, como estas?"))
