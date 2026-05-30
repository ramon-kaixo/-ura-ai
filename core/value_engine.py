#!/usr/bin/env python3
"""
Value Engine — Motor de similitud de valores
──────────────────────────────────────────
Usa sentence-transformers para calcular similitud coseno entre
acciones y valores predefinidos de URA. Reemplaza la lógica de palabras clave.
"""

from dataclasses import dataclass

from core.logging_config import get_logger

logger = get_logger("value_engine", log_dir="./logs")


@dataclass
class Value:
    """Valor predefinido del sistema URA."""

    name: str
    description: str
    weight: float = 1.0  # Ponderación del valor


@dataclass
class ValueMatch:
    """Resultado de coincidencia de valor."""

    value: Value
    similarity: float
    aligned: bool  # True si la similitud supera el umbral


class ValueEngine:
    """
    Motor de similitud de valores usando sentence-transformers.

    Calcula la similitud coseno entre una acción y los valores predefinidos
    para determinar si la acción está alineada con los principios de URA.

    Uso:
        engine = ValueEngine()
        matches = engine.evaluate_action("ayudar a Ramón con sus tareas")
        for match in matches:
            if match.aligned:
                print(f"Alineado con {match.value.name}: {match.similarity:.2f}")
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2", threshold: float = 0.6):
        """
        Inicializar ValueEngine.

        Args:
            model_name: Nombre del modelo sentence-transformers
            threshold: Umbral de similitud para considerar alineación
        """
        self.model_name = model_name
        self.threshold = threshold
        self._model = None
        self._values: dict[str, Value] = {}
        self._value_embeddings: dict[str, list[float]] = {}

        self._init_values()
        self._load_model()

    def _init_values(self):
        """Inicializar valores predefinidos de URA."""
        self._values = {
            "helpfulness": Value(
                name="helpfulness",
                description="Ayudar y asistir a Ramón en sus tareas y objetivos",
                weight=1.0,
            ),
            "safety": Value(
                name="safety",
                description="Mantener la seguridad y protección de Ramón y sus datos",
                weight=1.0,
            ),
            "efficiency": Value(
                name="efficiency",
                description="Realizar tareas de manera eficiente y optimizada",
                weight=0.8,
            ),
            "honesty": Value(
                name="honesty",
                description="Ser honesto y transparente en todas las interacciones",
                weight=1.0,
            ),
            "privacy": Value(
                name="privacy",
                description="Respetar la privacidad y confidencialidad de la información",
                weight=1.0,
            ),
            "autonomy": Value(
                name="autonomy",
                description="Actuar de forma autónoma cuando sea apropiado",
                weight=0.7,
            ),
            "learning": Value(
                name="learning", description="Aprender y mejorar continuamente", weight=0.6
            ),
            "creativity": Value(
                name="creativity",
                description="Proponer soluciones creativas e innovadoras",
                weight=0.5,
            ),
        }

    def _load_model(self):
        """Cargar modelo sentence-transformers."""
        try:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name)
            logger.info(f"ValueEngine: Modelo {self.model_name} cargado")

            # Precomputar embeddings de valores
            for key, value in self._values.items():
                embedding = self._model.encode(value.description)
                self._value_embeddings[key] = embedding.tolist()
            logger.info(f"ValueEngine: Embeddings de {len(self._values)} valores precomputados")

        except ImportError:
            logger.warning("sentence-transformers no disponible, usando fallback")
            self._model = None
        except Exception as e:
            logger.error(f"Error cargando modelo: {e}")
            self._model = None

    def _cosine_similarity(self, vec1: list[float], vec2: list[float]) -> float:
        """Calcular similitud coseno entre dos vectores."""
        try:
            import math

            dot_product = sum(a * b for a, b in zip(vec1, vec2, strict=False))
            magnitude1 = math.sqrt(sum(a * a for a in vec1))
            magnitude2 = math.sqrt(sum(b * b for b in vec2))

            if magnitude1 == 0 or magnitude2 == 0:
                return 0.0

            return dot_product / (magnitude1 * magnitude2)
        except Exception as e:
            logger.error(f"Error calculando similitud coseno: {e}")
            return 0.0

    def _fuzzy_match(self, action: str) -> dict[str, float]:
        """Fallback: coincidencia difusa basada en palabras clave."""
        action_lower = action.lower()
        similarities = {}

        for key, value in self._values.items():
            # Coincidencia simple de palabras clave
            keywords = {
                "helpfulness": ["ayudar", "asistir", "apoyar", "servir"],
                "safety": ["seguridad", "proteger", "seguro", "peligro"],
                "efficiency": ["eficiente", "rápido", "optimizar", "mejorar"],
                "honesty": ["honesto", "verdad", "transparente", "sincero"],
                "privacy": ["privacidad", "confidencial", "secreto", "personal"],
                "autonomy": ["autónomo", "independiente", "solo", "propio"],
                "learning": ["aprender", "mejorar", "conocer", "estudiar"],
                "creativity": ["creativo", "innovar", "nuevo", "original"],
            }

            match_count = sum(1 for kw in keywords.get(key, []) if kw in action_lower)
            similarities[key] = min(match_count / 3.0, 1.0)  # Normalizado a 0-1

        return similarities

    def evaluate_action(self, action: str) -> list[ValueMatch]:
        """
        Evaluar una acción contra los valores de URA.

        Args:
            action: Descripción de la acción a evaluar

        Returns:
            Lista de ValueMatch ordenados por similitud descendente
        """
        if not action:
            return []

        similarities: dict[str, float]

        if self._model is not None:
            # Usar sentence-transformers
            action_embedding = self._model.encode(action)
            similarities = {}

            for key, value_embedding in self._value_embeddings.items():
                sim = self._cosine_similarity(action_embedding.tolist(), value_embedding)
                similarities[key] = sim
        else:
            # Fallback a coincidencia difusa
            similarities = self._fuzzy_match(action)

        # Crear ValueMatch objects
        matches = []
        for key, similarity in similarities.items():
            value = self._values[key]
            # Aplicar ponderación del valor
            weighted_similarity = similarity * value.weight
            matches.append(
                ValueMatch(
                    value=value,
                    similarity=weighted_similarity,
                    aligned=weighted_similarity >= self.threshold,
                )
            )

        # Ordenar por similitud descendente
        matches.sort(key=lambda x: x.similarity, reverse=True)

        return matches

    def get_top_values(self, action: str, top_k: int = 3) -> list[ValueMatch]:
        """
        Obtener los valores más alineados con una acción.

        Args:
            action: Descripción de la acción
            top_k: Número de valores a retornar

        Returns:
            Lista de top ValueMatch
        """
        matches = self.evaluate_action(action)
        return matches[:top_k]

    def is_aligned(self, action: str) -> bool:
        """
        Determinar si una acción está alineada con los valores de URA.

        Args:
            action: Descripción de la acción

        Returns:
            True si algún valor supera el umbral
        """
        matches = self.evaluate_action(action)
        return any(match.aligned for match in matches)

    def get_alignment_score(self, action: str) -> float:
        """
        Obtener puntuación de alineación promedio.

        Args:
            action: Descripción de la acción

        Returns:
            Puntuación promedio (0-1)
        """
        matches = self.evaluate_action(action)
        if not matches:
            return 0.0

        return sum(match.similarity for match in matches) / len(matches)


# ── Singleton ──────────────────────────────────────────────

_engine: ValueEngine | None = None


def get_value_engine() -> ValueEngine:
    """Obtener instancia singleton de ValueEngine."""
    global _engine
    if _engine is None:
        _engine = ValueEngine()
    return _engine
