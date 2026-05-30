#!/usr/bin/env python3
"""
URA Maleta Manager — N2 Infrastructure (Fase 1)

CRUD para "maletas" de información y comportamiento. Cada maleta es un JSON que
describe cómo URA debe buscar sobre un tema (herramientas, reglas, fuentes).

Features:
- Load / save maletas from disk (config/maletas/ and ~/.ura/maletas/)
- Schema validation (minimal required fields)
- Confidence updates after each execution
- Semantic cloning (cosine > 0.75 → sufijo "clon", confianza inicial 0.4)

NOTE: Fase 1 uses a lightweight TF-IDF-like similarity when
      sentence-transformers is not available, to avoid forcing heavy deps.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, UTC
from pathlib import Path
from typing import Any

logger = logging.getLogger("ura_maleta_manager")

# Proyecto y datos de usuario
URA_BASE = Path(__file__).resolve().parent.parent
CONFIG_MALETAS = URA_BASE / "config" / "maletas"
USER_MALETAS = Path.home() / ".ura" / "maletas"

# Campos obligatorios mínimos
_REQUIRED_FIELDS = ("maleta_id", "version", "tema", "herramientas", "formato_salida")

# Umbrales
CLONE_SIMILARITY_THRESHOLD = 0.75
CLONE_INITIAL_CONFIDENCE = 0.4
DEFAULT_CONFIDENCE = 0.5

# Try optional embeddings
try:
    from sentence_transformers import SentenceTransformer  # type: ignore
    import numpy as np  # type: ignore

    _HAS_EMBEDDINGS = True
except ImportError:
    _HAS_EMBEDDINGS = False
    SentenceTransformer = None  # type: ignore
    np = None  # type: ignore


@dataclass
class Maleta:
    """In-memory representation of a maleta."""

    maleta_id: str
    tema: str
    data: dict[str, Any]
    source_path: Path | None = None

    @property
    def confianza(self) -> float:
        return float(self.data.get("confianza", DEFAULT_CONFIDENCE))

    @property
    def version(self) -> int:
        return int(self.data.get("version", 1))


class MaletaValidationError(ValueError):
    """Raised when a maleta fails schema validation."""


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _normalize_text(text: str) -> str:
    """Lowercase + strip + collapse whitespace."""
    return re.sub(r"\s+", " ", text.strip().lower())


def _cosine_similarity_lexical(a: str, b: str) -> float:
    """Lightweight similarity without embeddings: token Jaccard over normalized text."""
    ta = set(_normalize_text(a).split())
    tb = set(_normalize_text(b).split())
    if not ta or not tb:
        return 0.0
    inter = len(ta & tb)
    union = len(ta | tb)
    return inter / union if union else 0.0


class MaletaManager:
    """Gestiona el ciclo de vida de las maletas de URA."""

    def __init__(
        self,
        config_dir: Path | None = None,
        user_dir: Path | None = None,
    ) -> None:
        self.config_dir = Path(config_dir) if config_dir else CONFIG_MALETAS
        self.user_dir = Path(user_dir) if user_dir else USER_MALETAS
        self._embedder = None
        for d in (self.config_dir, self.user_dir):
            d.mkdir(parents=True, exist_ok=True)

    # --------------------------------------------------------- observational learning
    def create_maleta(self, domain: str, subdomain: str) -> str:
        """Create a new observational maleta for learning. Returns maleta_id."""
        maleta_id = f"maleta_{domain}_{subdomain}_{uuid.uuid4().hex[:8]}"
        maleta_data = {
            "id": maleta_id,
            "domain": domain,
            "subdomain": subdomain,
            "queries": [],
            "responses": [],
            "confidence": 0.0,
            "usage_count": 0,
            "status": "observacion",
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
        }
        path = self.user_dir / f"{maleta_id}.json"
        with path.open("w", encoding="utf-8") as f:
            json.dump(maleta_data, f, indent=2, ensure_ascii=False)
        logger.info("Maleta de observación creada: %s", maleta_id)
        return maleta_id

    def add_observation(self, maleta_id: str, query: str, response: str) -> None:
        """Add a (query, response) pair to an observational maleta."""
        maleta_path = self.user_dir / f"{maleta_id}.json"
        if not maleta_path.exists():
            logger.warning("Maleta no encontrada: %s", maleta_id)
            return
        with maleta_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        data["queries"].append(query)
        data["responses"].append(response)
        data["updated_at"] = _now_iso()
        with maleta_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.debug("Observación añadida a maleta %s: %d pares", maleta_id, len(data["queries"]))

    def validate_maleta(self, maleta_id: str, min_observations: int = 10) -> bool:
        """Check if maleta has enough observations to be validated."""
        maleta_path = self.user_dir / f"{maleta_id}.json"
        if not maleta_path.exists():
            return False
        with maleta_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return len(data.get("queries", [])) >= min_observations

    def promote_maleta(self, maleta_id: str) -> None:
        """Promote maleta from 'observacion' to 'promocionada' status."""
        maleta_path = self.user_dir / f"{maleta_id}.json"
        if not maleta_path.exists():
            logger.warning("Maleta no encontrada para promocionar: %s", maleta_id)
            return
        with maleta_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        data["status"] = "promocionada"
        data["promoted_at"] = _now_iso()
        data["updated_at"] = _now_iso()
        with maleta_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info("Maleta promocionada: %s", maleta_id)

    def get_maletas_by_domain(self, domain: str) -> list[dict]:
        """Get all observational maletas for a domain."""
        maletas = []
        for path in self.user_dir.glob("*.json"):
            try:
                with path.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                if data.get("domain") == domain:
                    maletas.append(data)
            except Exception:  # noqa: BLE001
                continue
        return maletas

    def get_promoted_maletas(self) -> list[dict]:
        """Get all promoted maletas ready for use."""
        promoted = []
        for path in self.user_dir.glob("*.json"):
            try:
                with path.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                if data.get("status") == "promocionada":
                    promoted.append(data)
            except Exception:  # noqa: BLE001
                continue
        return promoted

    def get_maleta_by_id(self, maleta_id: str) -> dict | None:
        """Get observational maleta by ID."""
        maleta_path = self.user_dir / f"{maleta_id}.json"
        if not maleta_path.exists():
            return None
        with maleta_path.open("r", encoding="utf-8") as f:
            return json.load(f)

    # ------------------------------------------------------------------ loading
    def _iter_json_files(self) -> list[Path]:
        files: list[Path] = []
        for directory in (self.config_dir, self.user_dir):
            if directory.exists():
                files.extend(sorted(directory.glob("*.json")))
        return files

    def load_all(self) -> dict[str, Maleta]:
        """Load every valid maleta from both directories, keyed by maleta_id."""
        maletas: dict[str, Maleta] = {}
        for path in self._iter_json_files():
            try:
                m = self.load(path)
                maletas[m.maleta_id] = m
            except MaletaValidationError as e:
                logger.warning("Maleta inválida descartada %s: %s", path, e)
            except Exception as e:  # noqa: BLE001
                logger.error("Error cargando maleta %s: %s", path, e)
        return maletas

    def load(self, path: Path) -> Maleta:
        path = Path(path)
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        self.validate(data)
        return Maleta(
            maleta_id=data["maleta_id"],
            tema=data["tema"],
            data=data,
            source_path=path,
        )

    def find_by_id(self, maleta_id: str) -> Maleta | None:
        for path in self._iter_json_files():
            try:
                with path.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                if data.get("maleta_id") == maleta_id:
                    self.validate(data)
                    return Maleta(
                        maleta_id=data["maleta_id"],
                        tema=data["tema"],
                        data=data,
                        source_path=path,
                    )
            except Exception:  # noqa: BLE001
                continue
        return None

    # --------------------------------------------------------------- validation
    def validate(self, data: dict[str, Any]) -> None:
        """Raise MaletaValidationError if required fields are missing."""
        missing = [f for f in _REQUIRED_FIELDS if f not in data]
        if missing:
            raise MaletaValidationError(f"Campos obligatorios ausentes: {missing}")
        if not isinstance(data.get("herramientas"), dict):
            raise MaletaValidationError("'herramientas' debe ser un objeto")
        herramientas = data["herramientas"]
        if not herramientas.get("buscadores"):
            raise MaletaValidationError("Se requiere al menos un buscador en herramientas")
        conf = data.get("confianza", DEFAULT_CONFIDENCE)
        if not (0.0 <= float(conf) <= 1.0):
            raise MaletaValidationError(f"'confianza' fuera de rango [0,1]: {conf}")

    # ------------------------------------------------------------------ saving
    def save(self, maleta: Maleta, target_dir: Path | None = None) -> Path:
        """Persist maleta to disk. Returns the final path."""
        self.validate(maleta.data)
        directory = (
            Path(target_dir)
            if target_dir
            else (maleta.source_path.parent if maleta.source_path else self.user_dir)
        )
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{maleta.maleta_id}.json"
        with path.open("w", encoding="utf-8") as f:
            json.dump(maleta.data, f, indent=2, ensure_ascii=False)
        maleta.source_path = path
        logger.info("Maleta guardada: %s", path)
        return path

    # ------------------------------------------------------------ confidence
    def update_confidence(
        self,
        maleta: Maleta,
        *,
        success: bool,
        score: float | None = None,
        delta: float = 0.05,
    ) -> float:
        """Update confidence based on execution result. Returns new confidence."""
        current = maleta.confianza
        if score is not None:
            # Use observed quality score directly, smoothed
            target = max(0.0, min(1.0, float(score)))
            new_conf = round(current * 0.7 + target * 0.3, 3)
        else:
            new_conf = round(current + delta, 3) if success else round(current - delta, 3)
        new_conf = max(0.0, min(1.0, new_conf))
        maleta.data["confianza"] = new_conf
        maleta.data["ultimo_uso"] = _now_iso()
        self.save(maleta)
        return new_conf

    # ------------------------------------------------------------------ cloning
    def _embed(self, text: str):
        """Lazy-load embedder and return a single embedding vector."""
        if not _HAS_EMBEDDINGS:
            return None
        if self._embedder is None:
            try:
                self._embedder = SentenceTransformer("all-MiniLM-L6-v2")
            except Exception as e:  # noqa: BLE001
                logger.warning("No se pudo cargar embedder: %s", e)
                return None
        return self._embedder.encode(text, convert_to_numpy=True)

    def similarity(self, a: str, b: str) -> float:
        """Cosine similarity via embeddings if available; fallback = Jaccard."""
        if _HAS_EMBEDDINGS:
            va = self._embed(a)
            vb = self._embed(b)
            if va is not None and vb is not None:
                import numpy as _np

                num = float(_np.dot(va, vb))
                den = float(_np.linalg.norm(va) * _np.linalg.norm(vb))
                return (num / den) if den else 0.0
        return _cosine_similarity_lexical(a, b)

    def find_similar(
        self, tema: str, *, threshold: float = CLONE_SIMILARITY_THRESHOLD
    ) -> list[tuple[Maleta, float]]:
        """Return maletas above the similarity threshold, sorted descending."""
        results: list[tuple[Maleta, float]] = []
        for maleta in self.load_all().values():
            sim = self.similarity(tema, maleta.tema)
            if sim >= threshold:
                results.append((maleta, sim))
        results.sort(key=lambda x: x[1], reverse=True)
        return results

    def clone_emergency(self, tema_nuevo: str) -> Maleta | None:
        """If a similar maleta exists (cos > 0.75), clone it with reduced confidence."""
        candidates = self.find_similar(tema_nuevo, threshold=CLONE_SIMILARITY_THRESHOLD)
        if not candidates:
            return None
        source, sim = candidates[0]
        new_data = json.loads(json.dumps(source.data))  # deep copy
        new_id = f"{source.maleta_id}_clon_{uuid.uuid4().hex[:8]}"
        new_data["maleta_id"] = new_id
        new_data["tema"] = tema_nuevo
        new_data["creada_por"] = "URA_clone"
        new_data["fecha_creacion"] = _now_iso()
        new_data["confianza"] = CLONE_INITIAL_CONFIDENCE
        new_data["version"] = 1
        new_data["ultimo_uso"] = None
        new_data["__clon_origen__"] = {
            "maleta_id": source.maleta_id,
            "similarity": round(sim, 3),
        }
        clone = Maleta(maleta_id=new_id, tema=tema_nuevo, data=new_data)
        self.save(clone, target_dir=self.user_dir)
        logger.info("Clonada maleta %s → %s (sim=%.2f)", source.maleta_id, new_id, sim)
        return clone


# Module-level singleton
_manager: MaletaManager | None = None


def get_maleta_manager() -> MaletaManager:
    global _manager
    if _manager is None:
        _manager = MaletaManager()
    return _manager
