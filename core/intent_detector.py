#!/usr/bin/env python3
"""
Detector de intención para URA
Encapsula la lógica de detección de intención usando embeddings o keywords
"""


class IntentDetector:
    """Detector de intención."""

    def __init__(self, embedding_service=None, intent_keywords: dict[str, list[str]] = None):
        self.embedding_service = embedding_service
        self.intent_keywords = intent_keywords or {}

    def detect(self, texto: str) -> tuple[str, float]:
        """
        Detectar intención del texto.

        Args:
            texto: Texto a analizar

        Returns:
            Tuple (intent, confidence)
        """
        if self.embedding_service:
            return self._detect_embedding(texto)
        return self._detect_keywords(texto)

    def _detect_embedding(self, texto: str) -> tuple[str, float]:
        """Detectar intención usando embeddings."""
        try:
            embedding = self.embedding_service.get_embedding(texto)
            best_intent = "chat"
            best_similarity = 0.0

            for intent, keywords in self.intent_keywords.items():
                keyword_text = " ".join(keywords)
                keyword_embedding = self.embedding_service.get_embedding(keyword_text)
                similarity = self.embedding_service.similarity(embedding, keyword_embedding)

                if similarity > best_similarity:
                    best_similarity = similarity
                    best_intent = intent

            return best_intent, best_similarity
        except Exception:
            return self._detect_keywords(texto)

    def _detect_keywords(self, texto: str) -> tuple[str, float]:
        """Detectar intención usando palabras clave."""
        texto_lower = texto.lower()
        scores = {}

        for intent, keywords in self.intent_keywords.items():
            score = sum(1 for kw in keywords if kw.lower() in texto_lower)
            if score > 0:
                scores[intent] = score / len(keywords)

        if scores:
            best_intent = max(scores, key=scores.get)
            return best_intent, scores[best_intent]

        return "chat", 0.5

    def set_keywords(self, intent_keywords: dict[str, list[str]]) -> None:
        """Establecer keywords por intención."""
        self.intent_keywords = intent_keywords

    def get_keywords(self, intent: str) -> list[str]:
        """Obtener keywords de una intención."""
        return self.intent_keywords.get(intent, [])
