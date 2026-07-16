"""Agente Diseño — analiza carteles, imagenes y diseño visual."""

import re


def process(text: str, meta: dict) -> dict:
    result = {
        "categoria": "diseno",
        "tokens": len(text.split()),
        "tipo_contenido": "desconocido",
        "paletas": [],
        "tipografia": [],
        "relevante": False,
    }

    # Detectar tipo de contenido
    if "poster" in text.lower() or "cartel" in text.lower():
        result["tipo_contenido"] = "cartel"
        result["relevante"] = True
    elif "menu" in text.lower() or "carta" in text.lower():
        result["tipo_contenido"] = "menu"
        result["relevante"] = True
    elif "logo" in text.lower() or "branding" in text.lower():
        result["tipo_contenido"] = "branding"
        result["relevante"] = True

    # Extraer colores mencionados
    colores = re.findall(r"(rojo|azul|verde|negro|blanco|amarillo|naranja|gris|dorado|plateado)", text.lower())
    result["paletas"] = list(set(colores))

    # Fuentes mencionadas
    fonts = re.findall(r"(Helvetica|Arial|Times|Garamond|Futura|Montserrat|Roboto|Open\s+Sans)", text)
    result["tipografia"] = list(set(fonts))

    return result
