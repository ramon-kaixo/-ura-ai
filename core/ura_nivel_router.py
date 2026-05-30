#!/usr/bin/env python3
"""
URA Nivel Router — N2 Infrastructure (Fase 2)

Decide which execution level handles a given search:

  - N3 (OpenClaw, master): novel / low confidence topics
  - N2 (local swarm):      familiar topics, learned maletas
  - N1 (n8n workflow):     mature topics (20+ uses, >95% confidence)

Confidence policy::

    conf < 0.60           → N3 puro
    0.60 ≤ conf < 0.85    → N2 + N3 audita (en paralelo o background)
    conf ≥ 0.85           → N2 puro (N3 en red de seguridad opcional)
    conf ≥ 0.95 y uses≥20 → candidato N1 (sugerencia al usuario)

Historial de uso: mantiene contador por maleta en ~/.ura/router_usage.json.
Degradación: si no se usa en 90 días, -5% confianza al mes.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, UTC
from enum import StrEnum
from pathlib import Path
from typing import Any, Awaitable, Callable

from core.ura_maleta_manager import Maleta, get_maleta_manager

logger = logging.getLogger("ura_nivel_router")

URA_DATA = Path.home() / ".ura"
USAGE_PATH = URA_DATA / "router_usage.json"

# Umbrales
CONF_N3_PURE = 0.60
CONF_N2_PURE = 0.85
CONF_N1_PROMOTE = 0.95
USES_N1_PROMOTE = 20

# Degradación por inactividad
STALE_DAYS = 90
MONTHLY_DECAY = 0.05


class Nivel(StrEnum):
    N1 = "N1"
    N2 = "N2"
    N3 = "N3"
    N2_N3 = "N2+N3"  # N2 responde rápido, N3 audita en paralelo


@dataclass
class RouterDecision:
    """Decision emitted by the router for a single search."""

    nivel: Nivel
    maleta_id: str | None
    confianza: float
    uses: int
    razon: str
    sugerencias: list[str] = field(default_factory=list)
    clonada: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "nivel": self.nivel.value,
            "maleta_id": self.maleta_id,
            "confianza": round(self.confianza, 3),
            "uses": self.uses,
            "razon": self.razon,
            "sugerencias": self.sugerencias,
            "clonada": self.clonada,
        }


@dataclass
class UsageStats:
    maleta_id: str
    uses: int = 0
    last_used: str | None = None  # ISO 8601
    last_decay_applied: str | None = None

    def is_stale(self, now: datetime) -> bool:
        if not self.last_used:
            return False
        last = datetime.fromisoformat(self.last_used)
        return (now - last).days >= STALE_DAYS


class UsageStore:
    """Persisted per-maleta usage counters."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path else USAGE_PATH
        self._lock = asyncio.Lock()
        self._cache: dict[str, UsageStats] = {}
        self._loaded = False

    def _load_sync(self) -> None:
        if self.path.exists():
            try:
                with self.path.open("r", encoding="utf-8") as f:
                    raw = json.load(f)
                self._cache = {k: UsageStats(**v) for k, v in raw.items() if isinstance(v, dict)}
            except Exception as e:  # noqa: BLE001
                logger.warning("No se pudo leer %s: %s", self.path, e)
                self._cache = {}
        self._loaded = True

    async def load(self) -> None:
        if self._loaded:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.get_event_loop().run_in_executor(None, self._load_sync)

    def _save_sync(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as f:
            json.dump(
                {k: v.__dict__ for k, v in self._cache.items()},
                f,
                ensure_ascii=False,
                indent=2,
            )

    async def save(self) -> None:
        await asyncio.get_event_loop().run_in_executor(None, self._save_sync)

    async def get(self, maleta_id: str) -> UsageStats:
        await self.load()
        if maleta_id not in self._cache:
            self._cache[maleta_id] = UsageStats(maleta_id=maleta_id)
        return self._cache[maleta_id]

    async def record_use(self, maleta_id: str) -> UsageStats:
        async with self._lock:
            await self.load()
            stats = self._cache.setdefault(maleta_id, UsageStats(maleta_id=maleta_id))
            stats.uses += 1
            stats.last_used = datetime.now(UTC).isoformat()
            await self.save()
            return stats

    async def snapshot(self) -> dict[str, UsageStats]:
        await self.load()
        return dict(self._cache)


# -----------------------------------------------------------------------------
# Decay policy
# -----------------------------------------------------------------------------


def apply_decay(maleta: Maleta, stats: UsageStats, *, now: datetime | None = None) -> float:
    """Return the decayed confidence. Also mutates maleta.data if applicable."""
    now = now or datetime.now(UTC)
    if not stats.last_used:
        return maleta.confianza
    if not stats.is_stale(now):
        return maleta.confianza

    months = ((now - datetime.fromisoformat(stats.last_used)).days - STALE_DAYS) // 30 + 1
    if months <= 0:
        return maleta.confianza

    if stats.last_decay_applied:
        last = datetime.fromisoformat(stats.last_decay_applied)
        already = ((now - last).days) // 30
        months = max(0, months - already)
    if months <= 0:
        return maleta.confianza

    new_conf = max(0.0, round(maleta.confianza - MONTHLY_DECAY * months, 3))
    logger.info(
        "Decay aplicado a %s: %.2f → %.2f (%d meses)",
        maleta.maleta_id,
        maleta.confianza,
        new_conf,
        months,
    )
    maleta.data["confianza"] = new_conf
    stats.last_decay_applied = now.isoformat()
    return new_conf


# -----------------------------------------------------------------------------
# Router
# -----------------------------------------------------------------------------


class NivelRouter:
    """Route queries to N1 / N2 / N3 based on maleta state."""

    def __init__(self, usage_store: UsageStore | None = None) -> None:
        self.usage = usage_store or UsageStore()
        self.maleta_mgr = get_maleta_manager()

    async def decide(
        self,
        tema: str,
        *,
        maleta_id: str | None = None,
        allow_clone: bool = True,
    ) -> RouterDecision:
        """Compute the routing decision for `tema` (and optional explicit maleta)."""
        maleta = None
        clonada = False

        if maleta_id:
            maleta = self.maleta_mgr.find_by_id(maleta_id)

        if maleta is None:
            # Try semantic similarity
            candidates = self.maleta_mgr.find_similar(tema, threshold=0.75)
            if candidates:
                maleta = candidates[0][0]
            elif allow_clone:
                # No match at all → try emergency clone from nearest
                clone = self.maleta_mgr.clone_emergency(tema)
                if clone is not None:
                    maleta = clone
                    clonada = True

        if maleta is None:
            # No context whatsoever → full N3 cold start
            return RouterDecision(
                nivel=Nivel.N3,
                maleta_id=None,
                confianza=0.0,
                uses=0,
                razon="Sin maleta existente para este tema — N3 cold start",
                sugerencias=["Pedir a OpenClaw que genere una maleta inicial"],
            )

        stats = await self.usage.get(maleta.maleta_id)
        conf = apply_decay(maleta, stats)
        # Persist decay if we mutated
        if conf != maleta.data.get("confianza"):
            self.maleta_mgr.save(maleta)

        nivel, razon, sugerencias = self._classify(conf, stats.uses)
        return RouterDecision(
            nivel=nivel,
            maleta_id=maleta.maleta_id,
            confianza=conf,
            uses=stats.uses,
            razon=razon,
            sugerencias=sugerencias,
            clonada=clonada,
        )

    @staticmethod
    def _classify(conf: float, uses: int) -> tuple[Nivel, str, list[str]]:
        sugerencias: list[str] = []
        if conf >= CONF_N1_PROMOTE and uses >= USES_N1_PROMOTE:
            sugerencias.append(
                "Maleta madura — considera exportar a n8n (N1) para ejecución sin coste"
            )
            return (
                Nivel.N2,
                (f"Confianza={conf:.2f} uses={uses}: N2 puro, candidato a N1"),
                sugerencias,
            )
        if conf >= CONF_N2_PURE:
            return Nivel.N2, f"Confianza alta ({conf:.2f}) — N2 puro", sugerencias
        if conf >= CONF_N3_PURE:
            return (
                Nivel.N2_N3,
                (f"Confianza media ({conf:.2f}) — N2 responde + N3 audita"),
                sugerencias,
            )
        return Nivel.N3, f"Confianza baja ({conf:.2f}) — N3 puro", sugerencias

    async def record_execution(self, maleta_id: str) -> None:
        await self.usage.record_use(maleta_id)


# -----------------------------------------------------------------------------
# N3 launcher stub (Fase 3 cubrirá la integración real con OpenClaw)
# -----------------------------------------------------------------------------


async def lanzar_n3_background(
    tema: str,
    *,
    on_complete: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
    openclaw_fn: Callable[[str], Awaitable[dict[str, Any]]] | None = None,
) -> asyncio.Task:
    """
    Stub: launch an N3 execution in the background.

    Fase 1-2: devuelve una Task que simula un resultado vacío. En Fase 3,
    `openclaw_fn` será el wrapper real a OpenClaw local.
    """

    async def _run():
        if openclaw_fn is None:
            logger.info("Stub N3: OpenClaw no configurado. Tema=%s", tema)
            result = {
                "tema": tema,
                "nivel": "N3",
                "estado": "stub_noop",
                "resultados": [],
            }
        else:
            try:
                result = await openclaw_fn(tema)
            except Exception as e:  # noqa: BLE001
                logger.error("lanzar_n3_background error: %s", e)
                result = {"tema": tema, "nivel": "N3", "estado": "error", "error": str(e)}
        if on_complete is not None:
            try:
                await on_complete(result)
            except Exception as e:  # noqa: BLE001
                logger.warning("on_complete callback falló: %s", e)
        return result

    return asyncio.create_task(_run())


# Module-level singleton
_router: NivelRouter | None = None


def get_router() -> NivelRouter:
    global _router
    if _router is None:
        _router = NivelRouter()
    return _router
