from pathlib import Path

import fitz


def extraer_pdf(ruta: Path) -> dict:
    doc = fitz.open(str(ruta))
    metadatos_raw = doc.metadata or {}
    titulo = metadatos_raw.get("title", "") or ruta.stem
    autor = metadatos_raw.get("author", "")
    total_paginas = doc.page_count

    paginas = []
    for i in range(total_paginas):
        pagina = doc[i]
        texto = pagina.get_text("text")
        if texto.strip():
            paginas.append(texto)
        if i >= 50:
            paginas.append(f"... ({total_paginas - 51} paginas restantes)")
            break

    doc.close()

    return {
        "tipo": "pdf",
        "metadatos": {
            "titulo": titulo.strip() if titulo else ruta.stem,
            "autor": autor.strip() if autor else "",
            "paginas": total_paginas,
            "tamano_bytes": ruta.stat().st_size,
        },
        "texto_plano": "\n\n".join(paginas),
        "ruta": str(ruta),
    }
