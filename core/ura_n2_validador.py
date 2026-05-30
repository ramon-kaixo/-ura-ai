#!/usr/bin/env python3
"""
URA N2 Validator — N2 Infrastructure (Fase 1)

Validates results produced by the N2 swarm:
- HEAD check on every URL (timeout 5s) to detect dead links
- Simple contradiction detection across agent outputs (titles / snippets)
- Aggregate quality score (0.0 - 1.0)
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

logger = logging.getLogger("ura_n2_validador")

HEAD_TIMEOUT_S = 5
MAX_PARALLEL_HEAD = 10

# Regex-based negation / affirmation heuristics for contradiction detection
_NEG_PATTERNS = re.compile(
    r"\b(no|nunca|jamás|sin|tampoco|ilegal|prohibido|falso|incorrecto)\b",
    re.IGNORECASE,
)
_POS_PATTERNS = re.compile(
    r"\b(sí|siempre|legal|permitido|verdadero|correcto|obligatorio)\b",
    re.IGNORECASE,
)


async def check_url(session, url: str) -> tuple[str, bool, int | None]:
    """Single HEAD check, return (url, ok, status)."""
    try:
        async with session.head(url, allow_redirects=True) as resp:
            return url, 200 <= resp.status < 400, resp.status
    except Exception as e:  # noqa: BLE001
        logger.debug("HEAD fallido %s: %s", url, e)
        return url, False, None


async def validate_urls(
    urls: list[str], timeout_s: int = HEAD_TIMEOUT_S
) -> dict[str, dict[str, Any]]:
    """Return mapping url -> {ok, status}. Missing aiohttp → optimistic ok=True."""
    if not urls:
        return {}
    try:
        import aiohttp  # type: ignore
    except ImportError:
        logger.warning("aiohttp ausente — saltando validación HEAD")
        return {u: {"ok": True, "status": None} for u in urls}

    timeout = aiohttp.ClientTimeout(total=timeout_s)
    sem = asyncio.Semaphore(MAX_PARALLEL_HEAD)
    results: dict[str, dict[str, Any]] = {}

    async with aiohttp.ClientSession(timeout=timeout) as session:

        async def _bounded(u: str):
            async with sem:
                return await check_url(session, u)

        tasks = [_bounded(u) for u in urls]
        for coro in asyncio.as_completed(tasks):
            url, ok, status = await coro
            results[url] = {"ok": ok, "status": status}
    return results


def detect_contradictions(resultados_por_agente: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Heuristic contradiction detection.

    For every pair of agent results whose titles share a common keyword, we
    inspect their snippets: if one has strong negation markers and the other
    strong affirmation markers referring to the same keyword, flag it.
    """
    contradictions: list[dict[str, Any]] = []

    flat_results: list[tuple[str, dict[str, Any]]] = []
    for agente in resultados_por_agente:
        agente_id = agente.get("agente_id", "unknown")
        for r in agente.get("resultados", []) or []:
            flat_results.append((agente_id, r))

    # Build keyword map: keyword -> list of (agente_id, result)
    keyword_map: dict[str, list[tuple[str, dict[str, Any]]]] = {}
    for agente_id, r in flat_results:
        title = (r.get("titulo") or r.get("title") or "").lower()
        # keep significant words (len > 4, exclude stopwords-ish)
        words = list(re.findall(r"[a-záéíóúñ]{5,}", title))
        for w in set(words):
            keyword_map.setdefault(w, []).append((agente_id, r))

    for keyword, items in keyword_map.items():
        if len(items) < 2:
            continue
        # count polarity on snippets
        stances: list[tuple[str, int, dict[str, Any]]] = []
        for agente_id, r in items:
            text = " ".join(
                [
                    r.get("titulo", "") or r.get("title", "") or "",
                    r.get("resumen", "") or r.get("snippet", "") or "",
                ]
            )
            neg = len(_NEG_PATTERNS.findall(text))
            pos = len(_POS_PATTERNS.findall(text))
            polarity = pos - neg
            stances.append((agente_id, polarity, r))

        positives = [s for s in stances if s[1] > 0]
        negatives = [s for s in stances if s[1] < 0]
        if positives and negatives:
            contradictions.append(
                {
                    "keyword": keyword,
                    "positivos": [{"agente": p[0], "url": p[2].get("url")} for p in positives],
                    "negativos": [{"agente": n[0], "url": n[2].get("url")} for n in negatives],
                    "severidad": min(1.0, (len(positives) + len(negatives)) / 6.0),
                }
            )
    return contradictions


def quality_score(
    total_results: int,
    alive_ratio: float,
    contradictions: list[dict[str, Any]],
    errors: int,
) -> float:
    """
    Compute quality score:
      base = alive_ratio
      penalties: contradictions, errors, zero results
      bonus: high result count
    """
    if total_results == 0:
        return 0.0

    score = alive_ratio
    score -= min(0.3, 0.05 * len(contradictions))
    score -= min(0.3, 0.05 * errors)
    score += min(0.1, total_results / 100.0)
    return round(max(0.0, min(1.0, score)), 3)


def consolidate_sources(resultados_por_agente: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate URLs and count how many agents cited each one."""
    url_meta: dict[str, dict[str, Any]] = {}
    for agente in resultados_por_agente:
        agente_id = agente.get("agente_id", "unknown")
        for r in agente.get("resultados", []) or []:
            url = r.get("url") or ""
            if not url:
                continue
            existing = url_meta.setdefault(
                url,
                {
                    "url": url,
                    "titulo": r.get("titulo") or r.get("title"),
                    "cited_by": [],
                    "count": 0,
                },
            )
            if agente_id not in existing["cited_by"]:
                existing["cited_by"].append(agente_id)
                existing["count"] += 1
    consolidated = sorted(url_meta.values(), key=lambda x: x["count"], reverse=True)
    return consolidated


async def validate_swarm_output(resultados_por_agente: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Run the full validation pipeline on swarm output.

    Returns::
        {
          "alive_urls_ratio": float,
          "contradictions": [...],
          "fuentes_consolidadas": [...],
          "score_calidad": float,
          "alertas": [str, ...]
        }
    """
    all_urls: list[str] = []
    errors = 0
    for agente in resultados_por_agente:
        if agente.get("estado") == "error":
            errors += 1
        for r in agente.get("resultados", []) or []:
            url = r.get("url")
            if url:
                all_urls.append(url)

    url_results = await validate_urls(list(set(all_urls)))
    alive = sum(1 for v in url_results.values() if v["ok"])
    total = len(url_results) or 1
    alive_ratio = alive / total

    contradictions = detect_contradictions(resultados_por_agente)
    fuentes = consolidate_sources(resultados_por_agente)
    total_results = sum(len(a.get("resultados", []) or []) for a in resultados_por_agente)
    score = quality_score(total_results, alive_ratio, contradictions, errors)

    alertas: list[str] = []
    if alive_ratio < 0.5:
        alertas.append(f"Alto ratio de URLs inaccesibles ({round((1 - alive_ratio) * 100)}%)")
    if errors:
        alertas.append(f"{errors} agentes reportaron error")
    if contradictions:
        alertas.append(f"{len(contradictions)} posibles contradicciones detectadas")
    if total_results == 0:
        alertas.append("Swarm no produjo resultados")

    return {
        "alive_urls_ratio": round(alive_ratio, 3),
        "contradictions": contradictions,
        "fuentes_consolidadas": fuentes,
        "score_calidad": score,
        "alertas": alertas,
        "url_head_checks": url_results,
    }
