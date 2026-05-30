#!/usr/bin/env python3
"""
URA Curiosity — FASE 3
────────────────────────
Decide cuándo URA debe investigar un tema por su cuenta,
basado en la metaconciencia y la falta de conocimiento.
"""

import logging
import time
from collections import deque

logger = logging.getLogger(__name__)


class CuriosityEngine:
    """
    Motor de curiosidad: detecta lagunas de conocimiento
    y programa investigación autónoma.

    Uso:
        ce = CuriosityEngine()
        ce.observe_question("¿Qué es la computación cuántica?")
        if ce.should_research("computación cuántica"):
            topics = ce.get_research_topics()
    """

    def __init__(self, max_history: int = 100):
        self.question_history: deque[dict] = deque(maxlen=max_history)
        self.research_queue: deque[str] = deque(maxlen=50)
        self.known_topics: set[str] = set()
        self.unknown_topics_count: dict[str, int] = {}
        self.unknown_threshold = 3  # Preguntas sin respuesta para disparar
        self.cooldown: dict[str, float] = {}  # Tema → última investigación

    def observe_question(self, question: str):
        """Registra una pregunta del usuario."""
        self.question_history.append(
            {
                "question": question[:200],
                "timestamp": time.time(),
            }
        )

    def register_answer(self, question: str, confidence: float, answer_length: int):
        """Registra si URA pudo responder adecuadamente."""
        topic = self._extract_topic(question)
        if not hasattr(self, "unknown_topics_count"):
            self.unknown_topics_count = {}
        if confidence < 0.5 or answer_length < 50:
            # Respuesta débil → posible laguna de conocimiento
            self.unknown_topics_count[topic] = self.unknown_topics_count.get(topic, 0) + 1
        else:
            self.known_topics.add(topic)

    def should_research(self) -> bool:
        """Decide si URA debería investigar ahora."""
        if not self.research_queue:
            return False

        next_topic = self.research_queue[0]
        last = self.cooldown.get(next_topic, 0)
        if time.time() - last < 300:  # 5 min cooldown
            return False

        return True

    def get_research_topics(self, n: int = 3) -> list[str]:
        """Devuelve los próximos temas a investigar."""
        topics = []
        for topic in list(self.research_queue)[:n]:
            if topic not in self.cooldown or time.time() - self.cooldown[topic] > 300:
                topics.append(topic)
                self.cooldown[topic] = time.time()
        return topics

    def add_topic(self, topic: str):
        """Añade un tema a la cola de investigación."""
        topic = topic.lower().strip()[:100]
        if topic not in self.research_queue and topic not in self.known_topics:
            self.research_queue.append(topic)
            logger.info(f"Curiosidad: nuevo tema '{topic}'")

    def _extract_topic(self, text: str) -> str:
        """Extrae el tema principal de un texto."""
        # Simplificado: primeras 3 palabras significativas
        words = text.lower().split()
        stopwords = {
            "que",
            "es",
            "la",
            "el",
            "los",
            "las",
            "de",
            "del",
            "en",
            "un",
            "una",
            "como",
            "para",
            "por",
            "con",
            "sin",
            "qué",
            "cómo",
            "cuál",
            "cuándo",
        }
        topic_words = [w for w in words if w not in stopwords][:3]
        return " ".join(topic_words)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    ce = CuriosityEngine()

    # Test
    ce.observe_question("¿Qué es la computación cuántica?")
    ce.add_topic("computación cuántica")
    ce.register_answer("¿Qué es la computación cuántica?", 0.3, 30)

    topics = ce.get_research_topics(n=3)
    print(f"Temas de investigación: {topics}")
    print(f"Historial: {len(ce.question_history)} preguntas")
