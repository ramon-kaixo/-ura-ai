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
    """Compara una función nueva contra una existente. Retorna score de similitud."""
    scores = []
    details = []

    # 1. Nombre
    if new.get("name") == existing.get("name"):
        scores.append(1.0)
        details.append("nombre_exacto")
    elif _words(new.get("name", "")) & _words(existing.get("name", "")):
        scores.append(0.6)
        details.append("nombre_parcial")
    else:
        scores.append(0.0)
        details.append("nombre_distinto")

    # 2. Parámetros
    new_params = set(new.get("params", []))
    existing_params = set(existing.get("params", []))
    if new_params and existing_params:
        overlap = len(new_params & existing_params)
        total = max(len(new_params), len(existing_params))
        scores.append(overlap / total)
        details.append(f"params_{overlap}/{total}")
    else:
        scores.append(0.0)
        details.append("sin_params")

    # 3. Body hash (código idéntico)
    if new.get("body_hash") and existing.get("body_hash"):
        if new["body_hash"] == existing["body_hash"]:
            scores.append(1.0)
            details.append("body_identico")
        else:
            scores.append(0.3)
            details.append("body_distinto")
    else:
        scores.append(0.0)

    # 4. Llamadas internas
    new_calls = set(new.get("calls", []))
    existing_calls = set(existing.get("calls", []))
    if new_calls and existing_calls:
        overlap = len(new_calls & existing_calls)
        total = max(len(new_calls), len(existing_calls))
        scores.append(overlap / total)
        details.append(f"calls_{overlap}/{total}")
    else:
        scores.append(0.0)

    # 5. Docstring
    new_doc = new.get("docstring_preview", "").strip()
    exist_doc = existing.get("docstring_preview", "").strip()
    if new_doc and exist_doc:
        overlap = len(set(new_doc.split()) & set(exist_doc.split()))
        total = max(len(new_doc.split()), len(exist_doc.split()))
        scores.append(overlap / total)
        details.append(f"doc_{overlap}/{total}")
    else:
        scores.append(0.0)

    # Peso: nombre 30%, params 25%, body 25%, calls 10%, doc 10%
    weights = [0.30, 0.25, 0.25, 0.10, 0.10]
    total_score = sum(s * w for s, w in zip(scores, weights))

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
