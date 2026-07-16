"""Agente Hostelería — analiza tendencias, recetas y gestión hostelera."""

import re


def process(text: str, meta: dict) -> dict:
    result = {
        "categoria": "hosteleria",
        "tokens": len(text.split()),
        "tema_principal": "general",
        "tendencias": [],
        "recetas": [],
        "relevante": False,
    }

    # Detectar tema
    temas = {
        "cocina": ["receta", "cocina", "chef", "plato", "ingrediente"],
        "gestion": ["gestion", "clientes", "plantilla", "turnos", "reservas"],
        "tendencias": ["tendencia", "moda", "nuevo", "innovacion", "foodie"],
        "normativa": ["normativa", "terraza", "aforo", "sanidad", "municipal"],
    }
    for tema, keywords in temas.items():
        if any(k in text.lower() for k in keywords):
            result["tema_principal"] = tema
            result["relevante"] = True
            break

    # Detectar menciones a restaurantes locales
    local = re.findall(r"(Navarra|Pamplona|Iruña|Tudela|Estella|Barañáin)", text)
    if local:
        result["zona"] = list(set(local))
        result["relevante"] = True

    return result
