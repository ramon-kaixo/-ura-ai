#!/usr/bin/env python3
"""
Pipeline de entrenamiento masivo N3 con Ollama directo + OpenClaw.

Orquesta generación de búsquedas sintéticas y entrenamiento de N3.
"""

from __future__ import annotations

import asyncio
import argparse
import json
import logging
import psutil
from datetime import datetime
from pathlib import Path
from typing import Any
import hashlib

# Configuración
TOSHIBA_PATH = Path("/Volumes/TOSHIBA_NUEVO/URA_entrenamiento")
RESPONSES_DIR = TOSHIBA_PATH / "respuestas"
SEEDS_FILE = TOSHIBA_PATH / "seeds.txt"
REPORTS_DIR = TOSHIBA_PATH / "reports"
TRAINING_LOG = Path.home() / ".ura" / "training.log"

logger = logging.getLogger("training_orchestrator")

# Módulos de seguridad (Paso 2B)
from core.security.input_sanitizer import sanitize_user_input
from core.security.jailbreak_guard import detect_jailbreak_attempt


# Configurar logging a archivo
def setup_training_logging():
    """Configura logging a ~/.ura/training.log."""
    TRAINING_LOG.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(TRAINING_LOG, encoding="utf-8")
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s %(name)s %(levelname)s: %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)


class TrainingOrchestrator:
    """Orquestador de entrenamiento masivo N3."""

    def __init__(
        self,
        max_queries: int = 500,
        concurrency: int = 4,
        cpu_threshold: float = 80.0,
        query_timeout: int = 120,
    ):
        self.max_queries = max_queries
        self.concurrency = concurrency
        self.cpu_threshold = cpu_threshold
        self.query_timeout = query_timeout
        self.responses_dir = RESPONSES_DIR
        self.reports_dir = TOSHIBA_PATH / "reports"
        self.seeds_file = SEEDS_FILE

        # Verificar montaje de Toshiba
        if not TOSHIBA_PATH.exists():
            raise RuntimeError(f"Toshiba no montado en {TOSHIBA_PATH}")

        # Crear directorios
        self.responses_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)

        # Configurar logging a archivo
        setup_training_logging()

        # Estadísticas
        self.stats = {
            "total_queries": 0,
            "successful": 0,
            "failed": 0,
            "decomposed": 0,
            "start_time": None,
            "end_time": None,
            "duration": 0,
        }

    def check_cpu_usage(self) -> float:
        """Verifica uso actual de CPU."""
        return psutil.cpu_percent(interval=1)

    def is_system_busy(self) -> bool:
        """Determina si el sistema está saturado."""
        cpu_usage = self.check_cpu_usage()
        return cpu_usage > self.cpu_threshold

    def load_seeds(self) -> list[str]:
        """Carga semillas desde archivo."""
        if not self.seeds_file.exists():
            logger.warning(f"Archivo de semillas no encontrado: {self.seeds_file}")
            return []

        with open(self.seeds_file, encoding="utf-8") as f:
            seeds = [line.strip() for line in f if line.strip()]

        logger.info(f"Cargadas {len(seeds)} semillas")
        return seeds

    def save_seeds(self, seeds: list[str]):
        """Guarda semillas en archivo."""
        with open(self.seeds_file, "w", encoding="utf-8") as f:
            for seed in seeds:
                f.write(f"{seed}\n")
        logger.info(f"Guardadas {len(seeds)} semillas")

    def _query_hash(self, query: str) -> str:
        """Genera hash único para query."""
        return hashlib.sha256(query.encode()).hexdigest()

    def save_response(self, query: str, response: dict[str, Any]):
        """Guarda respuesta en Toshiba."""
        query_hash = self._query_hash(query)
        response_file = self.responses_dir / f"{query_hash}.json"

        response_data = {
            "query": query,
            "response": response,
            "timestamp": datetime.now().isoformat(),
            "hash": query_hash,
        }

        with open(response_file, "w", encoding="utf-8") as f:
            json.dump(response_data, f, indent=2, ensure_ascii=False)

    def validate_response(self, response: dict[str, Any]) -> tuple[bool, float]:
        """
        Valida respuesta y asigna score.

        Returns:
            (is_valid, score)
        """
        # OllamaSearchResult tiene campo 'success'
        if not response.get("success", False):
            return False, 0.0

        response_text = response.get("response", "")

        # Validación simple: longitud mínima
        if len(response_text) < 50:
            return False, 0.0

        # Validación de keywords de error
        error_keywords = ["error", "failed", "timeout", "abort", "exception"]
        if any(keyword in response_text.lower() for keyword in error_keywords):
            return False, 0.0

        # Score basado en longitud
        score = min(1.0, len(response_text) / 500.0)
        return True, score

    def _detect_intent_from_query(self, query: str) -> str:
        """
        Detecta intent simple basado en keywords del query.
        """
        query_lower = query.lower()

        intent_map = {
            "cocina": ["receta", "cocina", "comida", "plato", "ingredient", "gastronomía"],
            "contabilidad": ["contabilidad", "iva", "impuesto", "factura", "deducción", "tributo"],
            "marketing": ["marketing", "banner", "publicidad", "promoción", "social media"],
            "leyes": ["ley", "normativa", "reglamento", "subvención", "legal"],
            "rrhh": ["contrato", "rrhh", "cámara", "empleado", "nómina"],
        }

        for intent, keywords in intent_map.items():
            if any(keyword in query_lower for keyword in keywords):
                return intent

        return "general"

    async def decompose_complex_seeds(self, seeds: list[str]) -> list[str]:
        """Descompone semillas complejas en subpreguntas."""
        from core.query_decomposer import get_query_decomposer

        decomposer = get_query_decomposer()
        all_seeds = []

        for seed in seeds:
            if decomposer.is_complex(seed):
                logger.info(f"Descomponiendo semilla compleja: {seed[:50]}...")
                subqueries = await decomposer.decompose(seed, n=15)
                all_seeds.extend(subqueries)
                self.stats["decomposed"] += 1
            else:
                all_seeds.append(seed)

        return all_seeds

    async def process_batch(self, queries: list[str]) -> list[dict[str, Any]]:
        """Procesa un lote de queries en paralelo usando OllamaN3Client directamente."""
        from core.ollama_n3_client import OllamaN3Client

        # Paso 2B: Sanitizar queries
        queries = [sanitize_user_input(q) for q in queries]

        # Paso 2B: Detectar jailbreak en queries
        for q in queries:
            if detect_jailbreak_attempt(q):
                logger.warning(f"Jailbreak attempt detectado en training query: {q[:50]}...")
                queries.remove(q)

        # Usar concurrencia con semaphore
        semaphore = asyncio.Semaphore(self.concurrency)

        async def process_query(query: str) -> dict[str, Any]:
            async with semaphore:
                try:
                    async with OllamaN3Client(timeout=self.query_timeout) as client:
                        result = await client.search(query)
                        # OllamaSearchResult tiene success, response, error, tokens
                        return {
                            "success": result.success,
                            "response": result.response,
                            "error": result.error,
                            "tokens": result.tokens,
                        }
                except Exception as e:
                    logger.error(f"Error procesando query '{query[:50]}...': {e}")
                    return {"success": False, "response": "", "error": str(e), "tokens": 0}

        results = await asyncio.gather(*[process_query(q) for q in queries], return_exceptions=True)

        # Procesar excepciones
        processed_results = []
        for result in results:
            if isinstance(result, Exception):
                processed_results.append(
                    {"success": False, "response": "", "error": str(result), "tokens": 0}
                )
            else:
                processed_results.append(result)

        return processed_results


async def night_training(self, max_queries: int | None = None):
    """
    Ejecuta entrenamiento nocturno masivo.

    Args:
        max_queries: Máximo de queries a procesar (usa self.max_queries si no se especifica)
    """
    max_to_process = max_queries or self.max_queries
    logger.info(f"Iniciando entrenamiento nocturno N3 (max_queries={max_to_process})...")
    self.stats["start_time"] = datetime.now().isoformat()

    seeds = await load_seeds(self, max_to_process)

    if not seeds:
        logger.warning("No hay semillas para procesar")
        return

    expanded_seeds = await decompose_complex_seeds(seeds)
    logger.info(f"Semillas expandidas: {len(seeds)} -> {len(expanded_seeds)}")

    save_expanded_seeds(self, seeds, expanded_seeds)

    processed = 0
    batch_size = 50

    while processed < min(len(expanded_seeds), max_to_process):
        if self.is_system_busy():
            logger.warning(f"Sistema ocupado (CPU {self.check_cpu_usage()}%), pausando 60s...")
            await asyncio.sleep(60)
            continue

        batch = expanded_seeds[processed : processed + batch_size]
        logger.info(f"Procesando lote {processed // batch_size + 1}: {len(batch)} queries")

        results = await self.process_batch(batch)

        for query, result in zip(batch, results, strict=False):
            is_valid, score = self.validate_response(result)
            if is_valid:
                self.save_response(query, result)
                self.stats["successful"] += 1
            else:
                self.stats["failed"] += 1

            self.stats["total_queries"] += 1

            try:
                from core.ura_observational_learner import get_learner

                learner = get_learner()
                intent = self._detect_intent_from_query(query)
                await learner.learn_from_interaction(query, result.get("response", ""), intent)
            except Exception as e:
                logger.debug(f"Error en aprendizaje observacional: {e}")

        processed += len(batch)
        logger.info(f"Procesadas {processed}/{min(len(expanded_seeds), max_to_process)} queries")

        await asyncio.sleep(5)

    try:
        pipeline = get_seed_pipeline()
        pipeline.mark_seeds_used(expanded_seeds[:max_to_process])
    except ImportError:
        logger.warning("seed_pipeline no disponible")

    try:
        learner = get_learner()
        await learner.run_validation_cycle()
        logger.info("Ciclo de validación de maletas completado")
    except Exception as e:
        logger.warning(f"Error en ciclo de validación: {e}")

    self.stats["end_time"] = datetime.now().isoformat()
    logger.info(f"Entrenamiento nocturno completado. Stats: {self.stats}")

    if self.stats["start_time"]:
        start = datetime.fromisoformat(self.stats["start_time"])
        end = datetime.fromisoformat(self.stats["end_time"])
        self.stats["duration"] = (end - start).total_seconds()

    self.save_report()

    logger.info("Entrenamiento nocturno completado")
    logger.info(f"Total queries: {self.stats['total_queries']}")
    logger.info(f"Exitosas: {self.stats['successful']}")
    logger.info(f"Fallidas: {self.stats['failed']}")
    logger.info(f"Descompuestas: {self.stats['decomposed']}")
    logger.info(f"Duración: {self.stats['duration']:.2f}s")


async def load_seeds(self, max_to_process: int) -> list:
    try:
        from core.seed_pipeline import get_seed_pipeline

        pipeline = get_seed_pipeline()
        seeds = pipeline.get_pending_seeds()
    except ImportError:
        logger.warning("seed_pipeline no disponible, usando archivo seeds.txt")
        seeds = self.load_seeds()

    return seeds[:max_to_process]


async def decompose_complex_seeds(seeds: list) -> list:
    expanded_seeds = await self.decompose_complex_seeds(seeds)
    return expanded_seeds


def save_expanded_seeds(self, seeds: list, expanded_seeds: list):
    if seeds:
        pass
    else:
        self.save_seeds(expanded_seeds)


async def process_batch(self, batch: list) -> list:
    results = await self.process_batch(batch)
    return results

    def save_report(self):
        """Guarda informe de entrenamiento."""
        report_file = (
            self.reports_dir / f"informe_entrenamiento_{datetime.now().strftime('%Y-%m-%d')}.json"
        )

        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(self.stats, f, indent=2, ensure_ascii=False)

        logger.info(f"Informe guardado en {report_file}")


async def main():
    """Punto de entrada CLI."""
    parser = argparse.ArgumentParser(description="Entrenamiento masivo N3 con Ollama directo")
    parser.add_argument("--max", type=int, default=500, help="Máximo de queries a procesar")
    parser.add_argument("--concurrency", type=int, default=4, help="Concurrencia de queries")
    parser.add_argument(
        "--cpu-threshold", type=float, default=80.0, help="Umbral de CPU para pausar"
    )

    args = parser.parse_args()

    # Configurar logging
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s: %(message)s"
    )

    # Verificar Toshiba
    if not TOSHIBA_PATH.exists():
        logger.error(f"Toshiba no montado en {TOSHIBA_PATH}")
        return 1

    # Crear semillas iniciales si no existen
    if not SEEDS_FILE.exists():
        logger.info("Creando archivo de semillas inicial...")
        initial_seeds = [
            "inteligencia artificial",
            "machine learning",
            "seguridad informática",
            "desarrollo de software",
            "cloud computing",
        ]
        orchestrator = TrainingOrchestrator()
        orchestrator.save_seeds(initial_seeds)

    # Ejecutar entrenamiento
    orchestrator = TrainingOrchestrator(
        max_queries=args.max,
        concurrency=args.concurrency,
        cpu_threshold=args.cpu_threshold,
        query_timeout=120,
    )

    await orchestrator.night_training()

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
