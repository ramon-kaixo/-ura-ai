"""Agente Legal — analiza textos normativos y fiscales."""

import re


def process(text: str, meta: dict) -> dict:
    result = {
        "categoria": "legal",
        "tokens": len(text.split()),
        "entidades": [],
        "resumen": "",
        "relevante": False,
    }

    # Keywords de hosteleria/navarra
    keywords = [
        "iva",
        "hosteleria",
        "restauracion",
        "terraza",
        "sanidad",
        "navarra",
        "foral",
        "tributaria",
        "contrato",
        "laboral",
        "catering",
        "bar",
        "cafeteria",
        "consumiciones",
    ]
    found = [k for k in keywords if k.lower() in text.lower()]
    result["entidades"] = found
    result["relevante"] = len(found) >= 2

    # Primer párrafo como resumen
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    result["resumen"] = lines[0][:300] if lines else ""

    # Detectar referencias legales (BOE, artículos, leyes)
    refs = re.findall(r"(Ley\s+\d+/\d+|BOE|Real\s+Decreto|Artículo\s+\d+|Norma\s+Foral)", text)
    result["referencias"] = list(set(refs))

    return result
