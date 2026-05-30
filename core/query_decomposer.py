#!/usr/bin/env python3
"""
Módulo: core/query_decomposer.py
Propósito: Descompone consultas complejas en subconsultas para distribuir a agentes especializados.
Dependencias principales: re, json, logging
Reglas especiales: Max 5 subconsultas por consulta. No crear dependencias circulares.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
from pathlib import Path
from datetime import datetime
import hashlib

logger = logging.getLogger("query_decomposer")

# Configuración
TOSHIBA_PATH = Path("/Volumes/TOSHIBA_NUEVO/URA_entrenamiento")
CACHE_DB = TOSHIBA_PATH / "decompose_cache.db"
OLLAMA_URL = "http://127.0.0.1:11434"  # Ollama local del Mac
DEFAULT_MODEL = "llama3.2"
SYSTEM_PROMPT = """Eres un experto en desglosar temas complejos en preguntas muy específicas y atómicas. Dado un tema, genera N subpreguntas que cubran todos los ángulos, cada una de una sola frase. Sé meticuloso y variado. Formato: lista numerada."""


class QueryDecomposer:
    """Descompone temas complejos en subpreguntas atómicas."""

    def __init__(
        self, cache_db: Path | None = None, ollama_url: str = OLLAMA_URL, model: str = DEFAULT_MODEL
    ):
        self.cache_db = cache_db or CACHE_DB
        self.ollama_url = ollama_url
        self.model = model
        self._init_cache()

    def _init_cache(self):
        """Inicializa base de datos SQLite para cache."""
        try:
            self.cache_db.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(self.cache_db)
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS decompose_cache (
                    topic_hash TEXT PRIMARY KEY,
                    topic TEXT,
                    subqueries TEXT,
                    created_at TEXT,
                    n INTEGER
                )
            """
            )
            conn.commit()
            conn.close()
            logger.info(f"Cache inicializado en {self.cache_db}")
        except Exception as e:
            logger.warning(f"Error inicializando cache: {e}")

    def _topic_hash(self, topic: str) -> str:
        """Genera hash único para topic."""
        return hashlib.sha256(topic.encode()).hexdigest()

    def _get_from_cache(self, topic: str, n: int) -> list[str] | None:
        """Intenta obtener desglose desde cache."""
        try:
            topic_hash = self._topic_hash(topic)
            conn = sqlite3.connect(self.cache_db)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT subqueries FROM decompose_cache WHERE topic_hash = ? AND n = ?",
                (topic_hash, n),
            )
            row = cursor.fetchone()
            conn.close()

            if row:
                return json.loads(row[0])
        except Exception as e:
            logger.warning(f"Error leyendo cache: {e}")
        return None

    def _save_to_cache(self, topic: str, subqueries: list[str], n: int):
        """Guarda desglose en cache."""
        try:
            topic_hash = self._topic_hash(topic)
            conn = sqlite3.connect(self.cache_db)
            conn.execute(
                """INSERT OR REPLACE INTO decompose_cache
                   (topic_hash, topic, subqueries, created_at, n)
                   VALUES (?, ?, ?, ?, ?)""",
                (topic_hash, topic, json.dumps(subqueries), datetime.now().isoformat(), n),
            )
            conn.commit()
            conn.close()
            logger.info(f"Guardado en cache: {topic[:50]}...")
        except Exception as e:
            logger.warning(f"Error guardando cache: {e}")

    async def _call_ollama(self, prompt: str) -> str:
        """Llama a Ollama local para generar desglose."""
        try:
            import aiohttp

            payload = {
                "model": self.model,
                "prompt": f"{SYSTEM_PROMPT}\n\nTema: {prompt}\n\nGenera {15} subpreguntas:",
                "stream": False,
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.ollama_url}/api/generate",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=60),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("response", "")
                    else:
                        logger.warning(f"Ollama error: {resp.status}")
                        return ""
        except Exception as e:
            logger.warning(f"Error llamando Ollama: {e}")
            return ""

    def _parse_subqueries(self, response: str, n: int) -> list[str]:
        """Parsea respuesta de Ollama para extraer subqueries."""
        subqueries = []
        lines = response.strip().split("\n")

        for line in lines:
            line = line.strip()
            # Buscar líneas numeradas
            if line and (line[0].isdigit() or line.startswith("-") or line.startswith("•")):
                # Remover número/bullet
                clean_line = line.lstrip("0123456789.-• ")
                if clean_line and "?" in clean_line:
                    subqueries.append(clean_line)
                elif clean_line:
                    # Añadir signo de interrogación si no tiene
                    subqueries.append(clean_line + "?")

        # Si no obtuvimos suficientes, usar fallback
        if len(subqueries) < n:
            subqueries.extend(self._fallback_subqueries(response, n - len(subqueries)))

        return subqueries[:n]

    def _fallback_subqueries(self, topic: str, n: int) -> list[str]:
        """Genera subqueries simples como fallback."""
        fallbacks = []
        templates = [
            f"¿Qué es {topic}?",
            f"¿Cómo funciona {topic}?",
            f"¿Por qué es importante {topic}?",
            f"¿Cuáles son los beneficios de {topic}?",
            f"¿Cuáles son los riesgos de {topic}?",
            f"¿Cómo se implementa {topic}?",
            f"¿Qué ejemplos hay de {topic}?",
            f"¿Qué tendencias hay sobre {topic}?",
            f"¿Qué herramientas se usan para {topic}?",
            f"¿Qué problemas resuelve {topic}?",
        ]

        for i in range(min(n, len(templates))):
            fallbacks.append(templates[i])

        return fallbacks

    async def decompose(self, topic: str, n: int = 15) -> list[str]:
        """
        Descompone un tema en N subpreguntas atómicas.

        Args:
            topic: Tema a descomponer
            n: Número de subpreguntas a generar

        Returns:
            Lista de subpreguntas
        """
        # Verificar cache primero
        cached = self._get_from_cache(topic, n)
        if cached:
            logger.info(f"Cache hit para: {topic[:50]}...")
            return cached

        logger.info(f"Descomponiendo: {topic[:50]}...")

        # Intentar llamar Ollama
        response = await self._call_ollama(topic)

        if response:
            subqueries = self._parse_subqueries(response, n)
        else:
            # Fallback si Ollama falla
            logger.warning("Usando fallback simple")
            subqueries = self._fallback_subqueries(topic, n)

        # Guardar en cache
        self._save_to_cache(topic, subqueries, n)

        logger.info(f"Generadas {len(subqueries)} subpreguntas")
        return subqueries

    def is_complex(self, topic: str) -> bool:
        """
        Determina si un tema es complejo y requiere descomposición.

        Args:
            topic: Tema a evaluar

        Returns:
            True si es complejo, False si no
        """
        # Heurística simple: temas con más de 3 palabras o ciertas palabras clave
        words = topic.split()

        complex_keywords = [
            "sistema",
            "proceso",
            "infraestructura",
            "arquitectura",
            "implementación",
            "desarrollo",
            "integración",
            "gestión",
            "análisis",
            "diseño",
            "optimización",
        ]

        is_long = len(words) > 3
        has_complex_keyword = any(kw in topic.lower() for kw in complex_keywords)

        return is_long or has_complex_keyword


# Singleton
_decomposer_instance: QueryDecomposer | None = None


def get_query_decomposer() -> QueryDecomposer:
    """Obtener singleton del descomponedor."""
    global _decomposer_instance
    if _decomposer_instance is None:
        _decomposer_instance = QueryDecomposer()
    return _decomposer_instance


if __name__ == "__main__":
    # Test del descomponedor
    async def test():
        decomposer = QueryDecomposer()
        topic = "inteligencia artificial en seguridad"

        print(f"¿Es complejo '{topic}'? {decomposer.is_complex(topic)}")

        subqueries = await decomposer.decompose(topic, n=10)
        print(f"\nSubpreguntas ({len(subqueries)}):")
        for i, sq in enumerate(subqueries, 1):
            print(f"{i}. {sq}")

    asyncio.run(test())
