"""mochila_engine.py — Núcleo de datos del sistema URA-Search v5.0.

Cada artefacto que ingresa al sistema se representa como una MochilaEngine.
La mochila viaja por las 6 fases, y cada fase añade su contribución.
Al finalizar, la mochila contiene el historial completo de la vida del contenido.
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).parent.parent
MOCHILAS_DIR = BASE_DIR / "04_METADATOS"


class TipoPipeline(str, Enum):
    IMAGEN = "IMAGEN"
    SVG = "SVG"
    VIDEO = "VIDEO"
    PDF = "PDF"
    HTML = "HTML"
    TEXTO = "TEXTO"
    MIXTO = "MIXTO"


class FaseID(str, Enum):
    F1_ROUTER = "F1_router"
    F2_CRAWLER = "F2_crawler"
    F3_REFINERY = "F3_refinery"
    F4_ESTETICA = "F4_estetica"
    F5_VECTOR = "F5_vector"
    F6_FEEDBACK = "F6_feedback"


@dataclass
class ContribucionFase:
    """Registro de lo que una fase contribuyó a la mochila."""
    fase_id: str
    timestamp: str
    duracion_ms: float = 0.0
    exito: bool = True
    datos: dict = field(default_factory=dict)
    error: str | None = None


@dataclass
class MochilaEngine:
    """Contenedor único para un artefacto a lo largo de todo el pipeline."""

    id: str
    url: str
    timestamp_creacion: str
    tipo_pipeline: str = "HTML"
    nombre_coleccion: str = "sin_nombre"
    estado: str = "pendiente"  # pendiente | procesando | completado | error

    # Contribuciones por fase
    contribuciones: dict[str, ContribucionFase] = field(default_factory=dict)
    fases_completadas: list[str] = field(default_factory=list)
    historial_errores: list[dict] = field(default_factory=list)

    # Metadatos globales
    hashes: dict = field(default_factory=dict)
    calidad: dict = field(default_factory=dict)
    compresion: dict = field(default_factory=dict)
    feedback: dict = field(default_factory=dict)
    estetica: dict = field(default_factory=dict)
    red: dict = field(default_factory=dict)
    indice: dict = field(default_factory=dict)

    @classmethod
    def nueva(cls, url: str, nombre_coleccion: str = "sin_nombre") -> "MochilaEngine":
        uid = hashlib.sha256(f"{url}:{time.time()}:{uuid.uuid4()}".encode()).hexdigest()[:16]
        return cls(
            id=uid,
            url=url,
            timestamp_creacion=datetime.now(tz=timezone.utc).isoformat(),
            nombre_coleccion=nombre_coleccion,
        )

    def __hash__(self) -> int:
        return hash(self.id)

    # ── Gestión de fases ───────────────────────────────────────────

    async def fase(self, fase_id: FaseID | str) -> "FaseContext":
        """Context manager para registrar contribuciones de fase.

        Uso:
            async with mochila.fase(FaseID.F3_REFINERY) as contrib:
                contrib.datos["clave"] = valor
        """
        return FaseContext(self, fase_id)

    def registrar_contribucion(self, contribucion: ContribucionFase) -> None:
        self.contribuciones[contribucion.fase_id] = contribucion
        if contribucion.exito:
            self.fases_completadas.append(contribucion.fase_id)
        else:
            self.estado = "error"
            self.historial_errores.append({
                "fase": contribucion.fase_id,
                "error": contribucion.error,
                "timestamp": contribucion.timestamp,
            })

    def marcar_completada(self) -> None:
        self.estado = "completado"

    def registrar_error(self, fase: str, error: str) -> None:
        self.estado = "error"
        self.historial_errores.append({
            "fase": fase,
            "error": error,
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        })

    # ── Registro de metadatos ──────────────────────────────────────

    def registrar_hashes(self, sha256: str = "", phash: str = "", simhash: int | None = None) -> None:
        self.hashes = {"sha256": sha256, "phash": phash, "simhash": simhash}

    def registrar_calidad(self, score_combinado: float = 0.0, resolucion: tuple = (0, 0),
                          ratio_aspecto: str = "", ssim: float = 1.0) -> None:
        self.calidad = {
            "score_combinado": score_combinado, "resolucion": list(resolucion),
            "ratio_aspecto": ratio_aspecto, "ssim": ssim,
        }

    def registrar_compresion(self, nivel: int = 0, ratio: float = 1.0,
                             herramienta: str = "", output_path: str = "") -> None:
        self.compresion = {"nivel": nivel, "ratio": ratio, "herramienta": herramienta, "output_path": output_path}

    def registrar_feedback(self, score_fiabilidad: float = 0.0, score_originalidad: float = 0.0,
                           score_sesgo: float = 0.5, requiere_revision: bool = False,
                           keywords_detectadas: list[str] | None = None) -> None:
        self.feedback = {
            "score_fiabilidad": score_fiabilidad, "score_originalidad": score_originalidad,
            "score_sesgo": score_sesgo, "requiere_revision": requiere_revision,
            "keywords_detectadas": keywords_detectadas or [],
        }

    def registrar_estetica(self, **kwargs) -> None:
        self.estetica.update(kwargs)

    def registrar_red(self, **kwargs) -> None:
        self.red.update(kwargs)

    def registrar_indice(self, **kwargs) -> None:
        self.indice.update(kwargs)

    # ── Persistencia ───────────────────────────────────────────────

    def guardar(self, directorio: Path | None = None) -> Path:
        dir_dest = directorio or MOCHILAS_DIR / f"{self.nombre_coleccion}_{self.id[:8]}"
        dir_dest.mkdir(parents=True, exist_ok=True)
        path = dir_dest / f"mochila_{self.id[:8]}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.a_dict(), f, ensure_ascii=False, indent=2)
        return path

    def a_dict(self) -> dict:
        base = asdict(self)
        base["contribuciones"] = {k: asdict(v) for k, v in self.contribuciones.items()}
        return base

    @classmethod
    def cargar(cls, path: Path) -> "MochilaEngine":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        contribs = {}
        for k, v in data.pop("contribuciones", {}).items():
            contribs[k] = ContribucionFase(**v)
        mochila = cls(**data)
        mochila.contribuciones = contribs
        return mochila

    @classmethod
    def cargar_o_crear(cls, url: str, coleccion: str = "sin_nombre") -> "MochilaEngine":
        return cls.nueva(url=url, nombre_coleccion=coleccion)

    def incrementar_workers(self, n: int) -> None:
        pass  # Placeholder para compatibilidad


class FaseContext:
    """Context manager para registrar contribuciones de fase de forma segura."""

    def __init__(self, mochila: MochilaEngine, fase_id: FaseID | str):
        self._mochila = mochila
        self._fase_id = fase_id if isinstance(fase_id, str) else fase_id.value
        self._t0: float = 0.0
        self.datos: dict = {}

    async def __aenter__(self) -> "FaseContext":
        self._t0 = time.time()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        duracion = (time.time() - self._t0) * 1000
        contrib = ContribucionFase(
            fase_id=self._fase_id,
            timestamp=datetime.now(tz=timezone.utc).isoformat(),
            duracion_ms=round(duracion, 2),
            exito=exc_type is None,
            datos=self.datos,
            error=str(exc_val) if exc_val else None,
        )
        self._mochila.registrar_contribucion(contrib)


def obtener_stats_globales() -> dict:
    """Lee estadísticas globales del corpus desde los ficheros en METADATOS."""
    n_mochilas = 0
    for path in MOCHILAS_DIR.rglob("mochila_*.json"):
        n_mochilas += 1
    return {"n_mochilas": n_mochilas}
