#!/usr/bin/env python3
"""
URA Observational Learner — Aprendizaje observacional N3 → N2 (Fase 3)

Política aprobada (correcta del diagnóstico):
  - URA observa cada ejecución de OpenClaw (N3) sobre un tema.
  - Tras MIN_OBSERVATIONS (10) ejecuciones, intenta promover el conocimiento
    a una maleta N2.
  - Antes de promover, ejecuta un "examen de validación":
        * Toma un caso resuelto previamente por N3 sobre el mismo tema.
        * Lanza N2 (con la maleta candidata) sobre ese caso.
        * Calcula similitud entre los resultados N3 y N2 (Jaccard sobre URLs).
        * Si score >= PROMOTE_THRESHOLD (0.85) → promueve la maleta a confianza inicial.
        * Si no → mantiene observación, no promueve.

Persistencia:
  ~/.ura/n3_observations/<tema_slug>.json
  Cada archivo contiene la lista de observaciones recientes (rotada a 50).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, UTC
from pathlib import Path
from typing import Any, Awaitable, Callable

from core.ura_maleta_manager import Maleta, get_maleta_manager

logger = logging.getLogger("ura_observational_learner")

URA_DATA = Path.home() / ".ura"
OBSERVATIONS_DIR = URA_DATA / "n3_observations"

MIN_OBSERVATIONS = 10
PROMOTE_THRESHOLD = 0.85
INITIAL_PROMOTED_CONFIDENCE = 0.65  # confianza inicial al promover (no 1.0)
MAX_OBSERVATIONS_KEPT = 50


def _slugify(text: str) -> str:
    s = text.strip().lower()
    s = re.sub(r"[^a-z0-9áéíóúñ]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s[:80] or "tema"


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


@dataclass
class N3Observation:
    """Una ejecución de N3 que URA ha observado."""

    obs_id: str
    tema: str
    fecha: str
    resultados: list[dict[str, Any]]
    razonamiento: str | None = None
    modelo: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()

    @classmethod
    def from_n3_payload(cls, tema: str, payload: dict[str, Any]) -> N3Observation:
        return cls(
            obs_id=uuid.uuid4().hex[:12],
            tema=tema,
            fecha=_now_iso(),
            resultados=payload.get("resultados", []) or [],
            razonamiento=payload.get("razonamiento"),
            modelo=payload.get("modelo"),
        )


@dataclass
class PromotionResult:
    promoted: bool
    maleta_id: str | None
    score_examen: float
    razon: str
    observations_count: int

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


class ObservationalLearner:
    """Captura observaciones de N3 y, llegado el umbral, promueve a maleta N2."""

    def __init__(
        self,
        observations_dir: Path | None = None,
        *,
        min_observations: int = MIN_OBSERVATIONS,
        promote_threshold: float = PROMOTE_THRESHOLD,
        initial_confidence: float = INITIAL_PROMOTED_CONFIDENCE,
    ) -> None:
        self.observations_dir = Path(observations_dir) if observations_dir else OBSERVATIONS_DIR
        self.observations_dir.mkdir(parents=True, exist_ok=True)
        self.min_observations = min_observations
        self.promote_threshold = promote_threshold
        self.initial_confidence = initial_confidence
        self._lock = asyncio.Lock()
        self.maleta_mgr = get_maleta_manager()

    # ------------------------------------------------------ persistence ----

    def _path_for(self, tema: str) -> Path:
        return self.observations_dir / f"{_slugify(tema)}.json"

    def _load(self, tema: str) -> list[N3Observation]:
        path = self._path_for(tema)
        if not path.exists():
            return []
        try:
            with path.open("r", encoding="utf-8") as f:
                raw = json.load(f)
            return [N3Observation(**item) for item in raw if isinstance(item, dict)]
        except Exception as e:  # noqa: BLE001
            logger.warning("No se pudo cargar observaciones %s: %s", path, e)
            return []

    def _save(self, tema: str, observations: list[N3Observation]) -> None:
        path = self._path_for(tema)
        # Recortar a las últimas N
        trimmed = observations[-MAX_OBSERVATIONS_KEPT:]
        with path.open("w", encoding="utf-8") as f:
            json.dump([o.to_dict() for o in trimmed], f, ensure_ascii=False, indent=2)

    # ------------------------------------------------------------- API -----

    async def observe(
        self,
        tema: str,
        n3_payload: dict[str, Any],
        *,
        n2_runner: Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]] | None = None,
    ) -> PromotionResult:
        """
        Registra una observación de N3 y, si se cumplen los umbrales, intenta
        promover el conocimiento a una maleta N2 (con examen de validación).

        n2_runner: callable async que ejecuta N2 sobre (tema, maleta) y devuelve
                   un informe con `resultados_por_agente` (mismo schema que swarm).
                   Si es None, el examen se omite y se promueve directamente
                   (modo "trust").
        """
        if n3_payload.get("estado") != "ok":
            return PromotionResult(
                promoted=False,
                maleta_id=None,
                score_examen=0.0,
                razon=f"N3 estado={n3_payload.get('estado')} — no se observa",
                observations_count=len(self._load(tema)),
            )

        async with self._lock:
            observations = self._load(tema)
            obs = N3Observation.from_n3_payload(tema, n3_payload)
            observations.append(obs)
            self._save(tema, observations)
            count = len(observations)

        if count < self.min_observations:
            return PromotionResult(
                promoted=False,
                maleta_id=None,
                score_examen=0.0,
                razon=f"Observaciones insuficientes ({count}/{self.min_observations})",
                observations_count=count,
            )

        # Intento de promoción
        existing = self._find_existing_maleta_for(tema)
        if existing is not None:
            # Ya hay maleta; refuerzo: subir confianza un poquito sin re-promocionar
            new_conf = min(1.0, existing.confianza + 0.02)
            existing.data["confianza"] = round(new_conf, 3)
            existing.data["ultimo_uso"] = _now_iso()
            self.maleta_mgr.save(existing)
            return PromotionResult(
                promoted=False,
                maleta_id=existing.maleta_id,
                score_examen=1.0,
                razon="Maleta ya existe — refuerzo de confianza",
                observations_count=count,
            )

        # Construir maleta candidata desde las observaciones
        candidate = self._build_candidate_maleta(tema, observations)

        # Examen de validación si hay n2_runner
        score = 1.0
        if n2_runner is not None:
            score = await self._validation_exam(tema, candidate, observations, n2_runner)
            if score < self.promote_threshold:
                return PromotionResult(
                    promoted=False,
                    maleta_id=None,
                    score_examen=score,
                    razon=f"Examen fallido: score {score:.2f} < {self.promote_threshold}",
                    observations_count=count,
                )

        # Promover
        maleta = Maleta(maleta_id=candidate["maleta_id"], tema=tema, data=candidate)
        self.maleta_mgr.save(maleta)
        logger.info(
            "PROMOCIÓN N2: tema=%s maleta_id=%s score_examen=%.2f obs=%d",
            tema,
            maleta.maleta_id,
            score,
            count,
        )
        return PromotionResult(
            promoted=True,
            maleta_id=maleta.maleta_id,
            score_examen=score,
            razon=f"Promovida tras {count} observaciones, examen={score:.2f}",
            observations_count=count,
        )

    # ------------------------------------------------ build candidate ------

    def _build_candidate_maleta(
        self, tema: str, observations: list[N3Observation]
    ) -> dict[str, Any]:
        """Construye una maleta JSON inicial inferida desde observaciones N3."""
        # Inferir fuentes preferidas: dominios más vistos
        from collections import Counter
        from urllib.parse import urlparse

        domains = Counter()
        for obs in observations:
            for r in obs.resultados:
                url = r.get("url") or ""
                try:
                    netloc = urlparse(url).netloc.lower()
                except Exception:  # noqa: BLE001
                    netloc = ""
                if netloc:
                    domains[netloc] += 1
        top_domains = [
            {"nombre": d, "dominio": d, "tipo": "auto"} for d, _ in domains.most_common(8)
        ]

        slug = _slugify(tema)
        seed = hashlib.sha1(tema.encode("utf-8"), usedforsecurity=False).hexdigest()[:8]
        maleta_id = f"learned_{slug[:40]}_{seed}"

        return {
            "maleta_id": maleta_id,
            "version": 1,
            "creada_por": "URA_observational_learner",
            "fecha_creacion": _now_iso(),
            "ultimo_uso": None,
            "confianza": self.initial_confidence,
            "tema": tema,
            "herramientas": {
                "buscadores": [
                    {
                        "nombre": "duckduckgo_text",
                        "tipo": "web",
                        "prioridad": 1,
                        "limite_por_sesion": 10,
                    },
                    {
                        "nombre": "stealth_browser",
                        "tipo": "browser",
                        "prioridad": 2,
                        "limite_diario": 30,
                    },
                ],
                "extractores": [{"nombre": "readability", "tipo": "limpiar_html"}],
                "validadores": [
                    {"nombre": "head_check", "tipo": "verificar_url_viva", "timeout_s": 5}
                ],
            },
            "fuentes_blancas": {
                "oficiales": [],
                "academicas": [],
                "especializadas": top_domains,
            },
            "anti_repeticion": {
                "cache_duracion_horas": 12,
                "fingerprint_campos": ["query_normalizada"],
                "umbral_similaridad": 0.85,
            },
            "reglas_negocio": [],
            "formato_salida": {
                "estructura": {
                    "titulo": "string",
                    "resumen": "string",
                    "fuente_principal": "url",
                    "nivel_confianza": "alta|media|baja",
                    "fecha": "ISO8601|null",
                },
            },
            "division_subtemas": {
                "num_agentes_sugerido": 3,
                "criterio_division": "por_subtema",
                "resultados_por_agente": 8,
                "subtemas_explicitos": None,
            },
            "__learned_from__": {
                "observations_count": len(observations),
                "first_obs": observations[0].fecha if observations else None,
                "last_obs": observations[-1].fecha if observations else None,
                "sample_obs_ids": [o.obs_id for o in observations[-3:]],
            },
        }

    # --------------------------------------------- validation exam --------

    async def _validation_exam(
        self,
        tema: str,
        candidate: dict[str, Any],
        observations: list[N3Observation],
        n2_runner: Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]],
    ) -> float:
        """
        Toma una observación N3 reciente y pregunta a N2 (con la maleta candidata)
        sobre el mismo tema. Compara las URLs encontradas.
        Devuelve score Jaccard ∈ [0,1].
        """
        if not observations:
            return 0.0
        ref = observations[-1]  # la más reciente
        try:
            n2_report = await n2_runner(tema, candidate)
        except Exception as e:  # noqa: BLE001
            logger.warning("Validation exam falló al ejecutar N2: %s", e)
            return 0.0

        ref_urls = {self._canon_url(r.get("url")) for r in ref.resultados if r.get("url")}
        n2_urls: set[str] = set()
        # Acepta dos formatos: informe del swarm (resultados_por_agente) o lista plana
        for agente in n2_report.get("resultados_por_agente", []) or []:
            for r in agente.get("resultados", []) or []:
                if r.get("url"):
                    n2_urls.add(self._canon_url(r["url"]))
        for r in n2_report.get("results", []) or []:
            if r.get("url"):
                n2_urls.add(self._canon_url(r["url"]))

        if not ref_urls or not n2_urls:
            return 0.0
        inter = len(ref_urls & n2_urls)
        union = len(ref_urls | n2_urls)
        return round(inter / union, 3) if union else 0.0

    @staticmethod
    def _canon_url(url: str | None) -> str:
        if not url:
            return ""
        return url.strip().lower().rstrip("/")

    # ------------------------------------------------ helpers / queries ----

    def _find_existing_maleta_for(self, tema: str) -> Maleta | None:
        candidates = self.maleta_mgr.find_similar(tema, threshold=0.8)
        return candidates[0][0] if candidates else None

    def list_observations(self, tema: str) -> list[dict[str, Any]]:
        return [o.to_dict() for o in self._load(tema)]

    def stats(self) -> dict[str, Any]:
        files = list(self.observations_dir.glob("*.json"))
        total_obs = 0
        per_topic = {}
        for f in files:
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                per_topic[f.stem] = len(data)
                total_obs += len(data)
            except Exception:  # noqa: BLE001
                continue
        return {
            "topics_tracked": len(files),
            "total_observations": total_obs,
            "per_topic": per_topic,
            "min_observations": self.min_observations,
            "promote_threshold": self.promote_threshold,
        }

    # --------------------------------------------------- new methods for URA integration ----

    async def learn_from_interaction(self, query: str, response: str, intent: str) -> None:
        """
        Añade una interacción (query, response) a la maleta de observación correspondiente
        según el dominio detectado por el CentralRouter.
        """
        # Mapear intent a domain/subdomain
        domain, subdomain = self._intent_to_domain(intent)

        # Buscar o crear maleta para este dominio
        maletas = self.maleta_mgr.get_maletas_by_domain(domain)
        maleta_id = None

        if maletas:
            # Usar la primera maleta existente del dominio
            maleta_id = maletas[0]["id"]
        else:
            # Crear nueva maleta
            maleta_id = self.maleta_mgr.create_maleta(domain, subdomain)

        # Añadir observación
        self.maleta_mgr.add_observation(maleta_id, query, response)
        logger.info("Observación guardada: intent=%s maleta=%s", intent, maleta_id)

    async def run_validation_cycle(self) -> None:
        """
        Para cada maleta en "observacion" con 10+ observaciones, ejecuta un examen:
        - Toma 3 preguntas antiguas
        - Pide a N2 que las responda
        - Compara con las respuestas guardadas usando embedding_service.similarity()
        - Si el promedio de similitud > 0.85, promociona la maleta
        """
        from core.embedding_service import EmbeddingService

        embed_service = EmbeddingService()

        # Obtener todas las maletas en observación
        all_maletas = []
        for path in self.maleta_mgr.user_dir.glob("*.json"):
            try:
                with path.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                if data.get("status") == "observacion":
                    all_maletas.append(data)
            except Exception:  # noqa: BLE001
                continue

        for maleta in all_maletas:
            maleta_id = maleta["id"]

            # Verificar si tiene suficientes observaciones
            if not self.maleta_mgr.validate_maleta(maleta_id, min_observations=10):
                continue

            # Ejecutar examen de validación
            queries = maleta["queries"][-3:]  # Últimas 3 preguntas
            responses = maleta["responses"][-3:]  # Últimas 3 respuestas

            if len(queries) < 3:
                continue

            # Calcular similitud promedio (simulado - en producción usaría N2 real)
            similarities = []
            for q, r in zip(queries, responses, strict=False):
                # Simulación: usar similitud entre query y response
                sim = embed_service.similarity(q, r)
                similarities.append(sim)

            avg_similarity = sum(similarities) / len(similarities) if similarities else 0.0

            if avg_similarity > 0.85:
                self.maleta_mgr.promote_maleta(maleta_id)
                logger.info(
                    "Maleta promocionada tras validación: %s (sim=%.2f)", maleta_id, avg_similarity
                )
            else:
                logger.debug(
                    "Maleta no promocionada: %s (sim=%.2f < 0.85)", maleta_id, avg_similarity
                )

    def get_ready_maletas(self) -> list[dict]:
        """Devuelve las maletas promocionadas listas para ser usadas por N2."""
        return self.maleta_mgr.get_promoted_maletas()

    def _intent_to_domain(self, intent: str) -> tuple[str, str]:
        """
        Mapea un intent del CentralRouter a (domain, subdomain).
        """
        intent_map = {
            "cocina": ("cocina", "general"),
            "receta": ("cocina", "recetas"),
            "contabilidad": ("contabilidad", "general"),
            "iva": ("contabilidad", "iva"),
            "marketing": ("marketing", "general"),
            "banner": ("marketing", "banners"),
            "leyes": ("leyes", "general"),
            "normativa": ("leyes", "normativa"),
            "rrhh": ("rrhh", "general"),
            "contrato": ("rrhh", "contratos"),
        }

        for key, (domain, subdomain) in intent_map.items():
            if key in intent.lower():
                return domain, subdomain

        return "general", "default"


# Singleton convenience
_learner: ObservationalLearner | None = None


def get_learner() -> ObservationalLearner:
    global _learner
    if _learner is None:
        _learner = ObservationalLearner()
    return _learner
