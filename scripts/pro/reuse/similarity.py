"""Similarity — compara firmas de funciones y clases para detectar duplicación.

Usa:
  - Coincidencia de nombre (exacta, parcial)
  - Coincidencia de parámetros (orden, count, nombres)
  - Coincidencia de body hash (AST idéntico)
  - Coincidencia de imports del archivo
  - Coincidencia de docstring
"""

from __future__ import annotations

from typing import Any


def compare(new: dict, existing: dict) -> dict:
    """Compara una función nueva contra una existente. Retorna score de similitud.

    Si un campo está vacío en la consulta (search por nombre), no penaliza:
    los pesos se redistribuyen entre los campos disponibles.
    """
    scores = []
    details = []
    active_weights = []

    # 1. Nombre (siempre disponible)
    if new.get("name") == existing.get("name"):
        scores.append(1.0)
        details.append("nombre_exacto")
    elif _words(new.get("name", "")) & _words(existing.get("name", "")):
        scores.append(0.6)
        details.append("nombre_parcial")
    else:
        scores.append(0.0)
        details.append("nombre_distinto")
    active_weights.append(0.30)

    # 2. Parámetros (solo si ambos tienen)
    new_params = set(new.get("params", []))
    existing_params = set(existing.get("params", []))
    if new_params and existing_params:
        overlap = len(new_params & existing_params)
        total = max(len(new_params), len(existing_params))
        scores.append(overlap / total)
        details.append(f"params_{overlap}/{total}")
        active_weights.append(0.25)
    # Si la consulta tiene params pero el existente no, no penalizar
    # Si la consulta no tiene params (search rápido), saltar

    # 3. Body hash (solo si ambos tienen)
    if new.get("body_hash") and existing.get("body_hash"):
        if new["body_hash"] == existing["body_hash"]:
            scores.append(1.0)
            details.append("body_identico")
        else:
            scores.append(0.3)
            details.append("body_distinto")
        active_weights.append(0.25)

    # 4. Llamadas internas (solo si ambos tienen)
    new_calls = set(new.get("calls", []))
    existing_calls = set(existing.get("calls", []))
    if new_calls and existing_calls:
        overlap = len(new_calls & existing_calls)
        total = max(len(new_calls), len(existing_calls))
        scores.append(overlap / total)
        details.append(f"calls_{overlap}/{total}")
        active_weights.append(0.10)

    # 5. Docstring (solo si ambos tienen)
    new_doc = new.get("docstring_preview", "").strip()
    exist_doc = existing.get("docstring_preview", "").strip()
    if new_doc and exist_doc:
        overlap = len(set(new_doc.split()) & set(exist_doc.split()))
        total = max(len(new_doc.split()), len(exist_doc.split()))
        scores.append(overlap / total)
        details.append(f"doc_{overlap}/{total}")
        active_weights.append(0.10)

    # Normalizar pesos según campos activos
    if active_weights:
        total_weight = sum(active_weights)
        normalized = [w / total_weight for w in active_weights]
        total_score = sum(s * nw for s, nw in zip(scores, normalized))
    else:
        total_score = 0.0

    return {
        "new_name": new.get("name", ""),
        "existing_name": existing.get("name", ""),
        "existing_file": existing.get("file", ""),
        "existing_line": existing.get("line", 0),
        "score": round(total_score, 2),
        "details": details,
        "categoria": _categoria(total_score),
    }


def _words(name: str) -> set[str]:
    return set(name.replace("_", " ").replace(".", " ").lower().split())


def _categoria(score: float) -> str:
    if score >= 0.85:
        return "reutilizar"
    if score >= 0.65:
        return "adaptar"
    if score >= 0.40:
        return "revisar"
    return "descarta"
