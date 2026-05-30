"""
Intent Detection — extracto de CentralRouter
Responsabilidad: detectar intenciones del usuario usando keywords + embeddings.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.logger import logger


class IntentDetector:
    """Detecta intenciones del usuario."""

    def __init__(self, intent_keywords: dict, embedding_service=None):
        self.keywords = intent_keywords
        self.embedding_service = embedding_service

    def detect_by_keywords(self, texto: str):
        """
        Detectar intención usando palabras clave con doble filtro y pesos específicos.
        Devuelve (intent, confidence) o None si no hay match.
        """
        texto_lower = texto.lower()
        best_intent = None
        best_score = 0.0

        for intent, keywords in self.keywords.items():
            score = 0.0
            for keyword in keywords:
                kw_lower = keyword.lower()
                if kw_lower in texto_lower:
                    score += 1.0
                    if len(kw_lower.split()) > 1:
                        score += 0.5
                    if texto_lower.startswith(kw_lower):
                        score += 0.5
            if score > best_score:
                best_score = score
                best_intent = intent

        if best_intent and best_score > 0:
            confidence = min(1.0, best_score / 3.0)
            return (best_intent, confidence)
        return ("chat", 0.0)

    def detect_by_embedding(self, texto: str):
        """Detectar intención usando similitud semántica con embeddings."""
        if not self.embedding_service:
            return None
        try:
            query_embedding = self.embedding_service.encode(texto)
            intent_texts = [
                f"{intent}: {', '.join(kws[:3])}" for intent, kws in self.keywords.items()
            ]
            intent_embeddings = self.embedding_service.encode(intent_texts)
            from sklearn.metrics.pairwise import cosine_similarity

            similarities = cosine_similarity([query_embedding], intent_embeddings)[0]
            best_idx = similarities.argmax()
            best_score = similarities[best_idx]
            if best_score > 0.3:
                intents = list(self.keywords.keys())
                return (intents[best_idx], float(best_score))
        except Exception as e:
            logger.debug(f"Embedding detection failed: {e}")
        return None

    def detect(self, texto: str):
        """Pipeline completo de detección: keywords → embeddings."""
        kw_result = self.detect_by_keywords(texto)
        if kw_result and kw_result[1] >= 0.5:
            return kw_result
        emb_result = self.detect_by_embedding(texto)
        if emb_result:
            return emb_result
        return kw_result or ("chat", 0.0)

    def find_similar(self, texto: str):
        """Encontrar agentes similares al texto dado."""
        results = []
        for intent, keywords in self.keywords.items():
            score = 0.0
            for kw in keywords:
                if kw.lower() in texto.lower():
                    score += 1.0
            if score > 0:
                results.append((intent, score))
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:5]
