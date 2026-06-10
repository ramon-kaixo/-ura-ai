import re
from pathlib import Path

import bs4


def _limpiar(texto: str | None) -> str:
    if not texto:
        return ""
    return re.sub(r"\s+", " ", str(texto)).strip()


def _extraer_metadatos(soup: bs4.BeautifulSoup) -> dict:
    meta: dict[str, str] = {}

    if soup.title and soup.title.string:
        meta["titulo"] = _limpiar(soup.title.string)

    for tag in soup.find_all("meta"):
        name = (tag.get("name") or tag.get("property") or "").lower()
        content = tag.get("content", "")
        if not content:
            continue
        if name in ("description", "og:description"):
            meta["descripcion"] = _limpiar(content)
        elif name in ("author", "article:author"):
            meta["autor"] = _limpiar(content)
        elif name in ("article:published_time", "date", "pubdate"):
            meta["fecha"] = _limpiar(content)

    return meta


def _extraer_enlaces(soup: bs4.BeautifulSoup, max_links: int = 50) -> list[dict[str, str]]:
    enlaces: list[dict[str, str]] = []
    for a in soup.find_all("a", href=True):
        if len(enlaces) >= max_links:
            break
        href = a.get("href", "")
        text = _limpiar(a.get_text())
        if href and not href.startswith("#") and text:
            enlaces.append({"url": href, "texto": text[:200]})
    return enlaces


def _extraer_texto(soup: bs4.BeautifulSoup) -> str:
    for tag in soup.find_all(["script", "style", "nav", "footer", "noscript"]):
        tag.decompose()
    texto = soup.get_text(separator="\n")
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    texto = re.sub(r"[ \t]{2,}", " ", texto)
    return texto.strip()


def extraer_html(ruta: Path) -> dict:
    with open(ruta, encoding="utf-8", errors="replace") as f:
        html = f.read()

    soup = bs4.BeautifulSoup(html, "lxml")
    meta = _extraer_metadatos(soup)
    enlaces = _extraer_enlaces(soup)
    texto = _extraer_texto(soup)

    return {
        "tipo": "html",
        "metadatos": {
            "titulo": meta.get("titulo", ""),
            "autor": meta.get("autor", ""),
            "fecha": meta.get("fecha", ""),
            "descripcion": meta.get("descripcion", ""),
            "enlaces": len(enlaces),
            "tamano_bytes": ruta.stat().st_size,
        },
        "texto_plano": texto,
        "ruta": str(ruta),
    }
