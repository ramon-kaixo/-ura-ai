"""Knowledge Base — genera documentación MkDocs desde el grafo de conocimiento.

Lee los documentos del grafo y genera una estructura MkDocs navegable:
  - Archivos .md en docs/knowledge/
  - Organizados por tipo de documento
  - Con frontmatter y metadatos
  - mkdocs.yml generado automáticamente
  - Escritura atómica (temp dir + rename)
  - Determinista (mismo grafo → mismos archivos)
  - Escapado de HTML/Markdown en body
  - Enlaces internos verificados
  - Nombres de archivo seguros (solo doc_id hex)

Uso:
    generate_knowledge_base(db_path, output_dir)
    ke docs generate --output docs/knowledge
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import shutil as _shutil
import string
import tempfile
from pathlib import Path
from typing import Any

import yaml

log = logging.getLogger("ura.knowledge.knowledge_base")

_KB_DIR = Path("docs/knowledge")
_SAFE_FILENAME_CHARS = set(string.ascii_lowercase + string.digits + "-_")
_MAX_FILENAME_LENGTH = 200


def _sanitize_filename(name: str) -> str:
    """Genera un nombre de archivo seguro (solo ASCII imprimible, sin espacios)."""
    safe = "".join(c if c in _SAFE_FILENAME_CHARS else "_" for c in name.lower())
    safe = safe.strip("_") or "untitled"
    return safe[:_MAX_FILENAME_LENGTH]


def _safe_markdown(text: str) -> str:
    """Escapa solo caracteres que rompen HTML, preservando Markdown.

    - `<` y `&` se escapan (evitan inyección HTML al renderizar Markdown)
    - `>`, `'`, `"` NO se escapan (son válidos en Markdown)
    - ` ``` ` NO se escapa (bloques de código Markdown)
    - Entidades HTML ya escapadas se preservan
    """
    # Preservar entidades HTML existentes para no doble-escapar
    preserved: list[tuple[str, str]] = []

    def _save(m: re.Match) -> str:
        token = f"__SAVE{len(preserved)}__"
        preserved.append((token, m.group(0)))
        return token

    text = re.sub(r"&[a-zA-Z0-9#]+;", _save, text)

    # Escapar solo < y & (no otros caracteres)
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;")
    # No escapar >, ', " — son válidos en Markdown

    # Restaurar entidades preservadas
    for token, original in preserved:
        text = text.replace(token, original)
    # Corregir doble escape: &amp;amp; → &amp;
    return re.sub(r"&amp;(#[0-9]+|[a-zA-Z]+);", r"&\1;", text)


def _verify_links(content: str, valid_ids: set[str]) -> list[str]:
    """Verifica enlaces internos en el contenido. Retorna enlaces rotos."""
    broken: list[str] = []
    for match in re.finditer(r"\(([a-f0-9]{12})\.md\)", content):
        link_id = match.group(1)
        if link_id not in valid_ids:
            broken.append(link_id)
    return broken


def _load_manifest(output: Path) -> dict[str, str]:
    """Carga el manifest anterior (doc_id → SHA-256 del contenido generado)."""
    manifest_file = output / ".meta" / "manifest.json"
    if manifest_file.exists():
        try:
            return json.loads(manifest_file.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_manifest(output: Path, manifest: dict[str, str]) -> None:
    """Guarda el manifest (doc_id → SHA-256 del contenido)."""
    meta_dir = output / ".meta"
    meta_dir.mkdir(parents=True, exist_ok=True)
    (meta_dir / "manifest.json").write_text(json.dumps(manifest, sort_keys=True))


def _content_hash(text: str) -> str:
    """SHA-256 del contenido generado para detección de cambios."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def generate_knowledge_base(db_path: Path, output_dir: Path | None = None) -> int:
    """Genera la documentación MkDocs desde el grafo de conocimiento.

    Escritura atómica: primero escribe en un directorio temporal,
    luego renombra atómicamente al destino final.
    Si el proceso falla a mitad, el destino original queda intacto.

    Args:
        db_path: Ruta a la base de datos.
        output_dir: Directorio de salida (def: docs/knowledge).

    Returns:
        Número de documentos generados.

    """
    from knowledge.engine.connection import open_db

    # 1. Leer datos (paginado para escalabilidad)
    conn = open_db(db_path)
    cursor = conn.execute("SELECT COUNT(*) as c FROM kg_nodes").fetchone()
    total_docs = cursor["c"] if cursor else 0

    if total_docs == 0:
        log.warning("No documents in graph")
        conn.close()
        return 0

    output = output_dir or _KB_DIR
    return _generar_knowledge_base(conn, total_docs, output)


def _generar_knowledge_base(conn: Any, total_docs: int, output: Path) -> int:
    """Genera en temp dir y renombra atómicamente a `output`. Retorna nº de docs."""
    tmp_dir = Path(tempfile.mkdtemp(prefix="kb_"))
    try:
        dest = tmp_dir / "docs"
        dest.mkdir(parents=True, exist_ok=True)

        all_ids_set, by_type = _cargar_datos_grafo(conn, total_docs)
        conn.close()

        # Cargar manifest anterior para detección incremental
        prev_manifest = _load_manifest(output)
        new_manifest: dict[str, str] = {}

        nav, count, changed_count = _escribir_docs(dest, by_type, prev_manifest, new_manifest)

        # Verificar enlaces internos
        broken_links_total = _verificar_enlaces(by_type, all_ids_set)

        # Generar mkdocs.yml (determinista: sorted nav keys)
        _escribir_config_mkdocs(dest, nav, new_manifest)

        # Generar index.md
        _escribir_index(dest, by_type, count)

        # Renombrar atómicamente
        _swap_atomico(output, dest)

        _log_resultado(count, changed_count, output, broken_links_total)
        return count

    except Exception:
        log.exception("Knowledge base generation failed")
        _shutil.rmtree(tmp_dir, ignore_errors=True)
        return 0


def _log_resultado(count: int, changed_count: int, output: Path, broken_links_total: int) -> None:
    log.info(
        "Knowledge base generated: %d docs (%d changed) in %s%s",
        count,
        changed_count,
        output,
        f" ({broken_links_total} broken links)" if broken_links_total else "",
    )


def _cargar_datos_grafo(conn: Any, total_docs: int) -> tuple[set[str], dict[str, list[dict[str, Any]]]]:
    """Lee edges, feedback y nodos paginados del grafo → (all_ids_set, by_type)."""
    edge_map: dict[str, list[dict[str, Any]]] = {}
    for e in conn.execute("SELECT src, dst, relation FROM kg_edges").fetchall():
        edge_map.setdefault(e["src"], []).append({"dst": e["dst"], "relation": e["relation"]})

    fb_map: dict[str, dict[str, Any]] = {}
    for r in conn.execute("SELECT doc_id, avg_rating, n_ratings FROM op_feedback_agg").fetchall():
        fb_map[r["doc_id"]] = dict(r)

    by_type: dict[str, list[dict[str, Any]]] = {}
    all_ids_set: set[str] = set()
    batch_size = 1000
    offset = 0
    while offset < total_docs:
        batch = conn.execute(
            "SELECT id, type, path, frontmatter, body FROM kg_nodes ORDER BY type, id LIMIT ? OFFSET ?",
            (batch_size, offset),
        ).fetchall()
        if not batch:
            break
        for r in batch:
            doc_id = r["id"]
            all_ids_set.add(doc_id)
            doc_type = r["type"] or "doc"
            by_type.setdefault(doc_type, []).append(_construir_doc_entry(r, edge_map, fb_map))
        offset += len(batch)
    return all_ids_set, by_type


def _construir_doc_entry(r: Any, edge_map: dict[str, Any], fb_map: dict[str, Any]) -> dict[str, Any]:
    """Construye la entrada de documento (frontmatter, relaciones, feedback, body)."""
    doc_id = r["id"]
    doc_type = r["type"] or "doc"
    fm = json.loads(r["frontmatter"]) if r["frontmatter"] else {}
    body = r["body"] or ""
    title = fm.get("title", doc_id)

    rels = edge_map.get(doc_id, [])
    content = _construir_content(
        doc_id,
        doc_type,
        title,
        fm,
        r,
        body,
        _construir_relaciones(rels),
        _construir_rating(fb_map.get(doc_id)),
    )
    return {
        "id": doc_id,
        "title": title,
        "content": content,
        "path": r["path"],
        "rels": [e["dst"] for e in rels],
    }


def _construir_relaciones(rels: list[dict[str, Any]]) -> str:
    """Sección de relaciones del documento (Markdown)."""
    rel_lines = [f"- [{_safe_markdown(e['relation'])}]({e['dst']}.md)" for e in rels]
    return "\n\n## Relaciones\n" + "\n".join(rel_lines) if rel_lines else ""


def _construir_rating(fb: dict[str, Any] | None) -> str:
    """Sección de rating del documento (Markdown), vacía si no hay feedback."""
    if not fb or fb["n_ratings"] <= 0:
        return ""
    stars = "\u2b50" * round(fb["avg_rating"])
    return f"\n\n**Rating:** {stars} ({fb['avg_rating']:.1f}/5, {fb['n_ratings']} votes)"


def _construir_content(
    doc_id: str,
    doc_type: str,
    title: str,
    fm: dict[str, Any],
    r: Any,
    body: str,
    rel_section: str,
    rating_section: str,
) -> str:
    """Contenido Markdown completo del documento."""
    safe_body = _safe_markdown(body)

    return f"""# {_safe_markdown(title)}

**Type:** {_safe_markdown(doc_type)}
**ID:** `{doc_id}`
**Path:** `{_safe_markdown(r["path"])}`
**Tags:** {", ".join(_safe_markdown(t) for t in (fm.get("tags", []) or [])) if fm.get("tags") else "none"}

---

{safe_body}{rel_section}{rating_section}

---

*Generated by Knowledge Engine v0.2.0*
"""


def _escribir_docs(
    dest: Path,
    by_type: dict[str, list[dict[str, Any]]],
    prev_manifest: dict[str, str],
    new_manifest: dict[str, str],
) -> tuple[list[dict[str, Any]], int, int]:
    """Escribe archivos .md (determinista) → (nav, count, changed_count)."""
    nav: list[dict[str, Any]] = []
    count = 0
    changed_count = 0

    for doc_type in sorted(by_type.keys()):
        docs = sorted(by_type[doc_type], key=lambda d: (d["title"].lower(), d["id"]))
        type_dir = dest / _sanitize_filename(doc_type)
        type_dir.mkdir(exist_ok=True)
        nav_entry: dict[str, Any] = {doc_type: []}

        for doc in docs:
            doc_id = doc["id"]
            new_hash = _content_hash(doc["content"])
            new_manifest[doc_id] = new_hash
            count += 1
            nav_link = f"{_sanitize_filename(doc_type)}/{_sanitize_filename(doc_id)}.md"
            if prev_manifest.get(doc_id) == new_hash:
                nav_entry[doc_type].append({doc["title"]: nav_link})
                continue
            (type_dir / f"{_sanitize_filename(doc_id)}.md").write_text(doc["content"], encoding="utf-8")
            changed_count += 1
            nav_entry[doc_type].append({doc["title"]: nav_link})

        nav.append(nav_entry)
    return nav, count, changed_count


def _verificar_enlaces(by_type: dict[str, list[dict[str, Any]]], all_ids_set: set[str]) -> int:
    """Verifica enlaces internos de todo el contenido → total de enlaces rotos."""
    broken_total = 0
    for doc_type in by_type:  # noqa: PLC0206
        for doc in by_type[doc_type]:
            broken = _verify_links(doc["content"], all_ids_set)
            if broken:
                broken_total += len(broken)
                log.warning("Broken links in doc %s: %s", doc["id"], broken)
    return broken_total


def _escribir_config_mkdocs(dest: Path, nav: list[dict[str, Any]], new_manifest: dict[str, str]) -> None:
    """Genera mkdocs.yml y guarda el manifest de la próxima generación incremental."""
    mkdocs_config: dict[str, Any] = {
        "site_name": "Knowledge Base",
        "site_description": "URA Knowledge Engine — Generated Documentation",
        "theme": "material",
        "nav": [{"Home": "index.md"}, *nav],
        "plugins": ["search"],
        "markdown_extensions": ["admonition", "pymdownx.superfences"],
    }
    _save_manifest(dest, new_manifest)
    (dest / "mkdocs.yml").write_text(
        yaml.dump(mkdocs_config, default_flow_style=False, sort_keys=True),
        encoding="utf-8",
    )


def _escribir_index(dest: Path, by_type: dict[str, list[dict[str, Any]]], count: int) -> None:
    """Genera index.md con índice por categorías."""
    index_lines = [
        "# Knowledge Base\n",
        "Generated from Knowledge Engine v0.2.0\n",
        f"**{count} documents**\n",
        "\n## Categories\n",
    ]
    for doc_type in sorted(by_type.keys()):
        docs = by_type[doc_type]
        index_lines.append(f"\n### {doc_type.capitalize()} ({len(docs)})\n")
        for doc in sorted(docs, key=lambda d: (d["title"].lower(), d["id"])):
            safe_type = _sanitize_filename(doc_type)
            safe_name = _sanitize_filename(doc["id"])
            index_lines.append(f"- [{doc['title']}]({safe_type}/{safe_name}.md)")
    (dest / "index.md").write_text("\n".join(index_lines), encoding="utf-8")


def _swap_atomico(output: Path, dest: Path) -> None:
    """Renombra dest a output con backup transitorio."""
    if output.exists():
        backup = output.parent / f"{output.name}.bak"
        if backup.exists():
            _shutil.rmtree(backup)
        output.rename(backup)
    dest.rename(output)

    backup = output.parent / f"{output.name}.bak"
    if backup.exists():
        _shutil.rmtree(backup)
