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

import json
import logging
import re
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
    text = re.sub(r"&amp;(#[0-9]+|[a-zA-Z]+);", r"&\1;", text)

    return text


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
    import hashlib

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

    # Leer en lotes de 1000 para no cargar todo en memoria
    batch_size = 1000
    all_doc_ids: set[str] = set()

    output = output_dir or _KB_DIR

    # 2. Escribir en directorio temporal, luego renombrar atómicamente
    tmp_dir = Path(tempfile.mkdtemp(prefix="kb_"))
    try:
        dest = tmp_dir / "docs"
        dest.mkdir(parents=True, exist_ok=True)

        # Leer edges (cargarlos todos — normalmente 2x nodos)
        edges = conn.execute("SELECT src, dst, relation FROM kg_edges").fetchall()
        edge_map: dict[str, list[dict[str, Any]]] = {}
        for e in edges:
            edge_map.setdefault(e["src"], []).append({"dst": e["dst"], "relation": e["relation"]})

        # Leer feedback
        fb_map: dict[str, dict[str, Any]] = {}
        fb_rows = conn.execute("SELECT doc_id, avg_rating, n_ratings FROM op_feedback_agg").fetchall()
        for r in fb_rows:
            fb_map[r["doc_id"]] = dict(r)

        # Procesar documentos por lotes
        offset = 0
        by_type: dict[str, list[dict[str, Any]]] = {}
        all_ids_set: set[str] = set()
        broken_links_total: int = 0

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
                all_doc_ids.add(doc_id)
                doc_type = r["type"] or "doc"
                if doc_type not in by_type:
                    by_type[doc_type] = []
                fm = json.loads(r["frontmatter"]) if r["frontmatter"] else {}
                body = r["body"] or ""
                title = fm.get("title", doc_id)

                # Relaciones
                rels = edge_map.get(doc_id, [])
                rel_lines = []
                for e in rels:
                    rel_lines.append(f"- [{_safe_markdown(e['relation'])}]({e['dst']}.md)")
                rel_section = "\n\n## Relaciones\n" + "\n".join(rel_lines) if rel_lines else ""

                # Feedback
                fb = fb_map.get(doc_id)
                rating_section = ""
                if fb and fb["n_ratings"] > 0:
                    stars = "\u2b50" * round(fb["avg_rating"])
                    rating_section = f"\n\n**Rating:** {stars} ({fb['avg_rating']:.1f}/5, {fb['n_ratings']} votes)"

                # Sanitizar body para Markdown/HTML
                safe_body = _safe_markdown(body)

                content = f"""# {_safe_markdown(title)}

**Type:** {_safe_markdown(doc_type)}  
**ID:** `{doc_id}`  
**Path:** `{_safe_markdown(r["path"])}`  
**Tags:** {", ".join(_safe_markdown(t) for t in (fm.get("tags", []) or [])) if fm.get("tags") else "none"}

---

{safe_body}{rel_section}{rating_section}

---

*Generated by Knowledge Engine v0.2.0*
"""

                by_type[doc_type].append(
                    {
                        "id": doc_id,
                        "title": title,
                        "content": content,
                        "path": r["path"],
                        "rels": [e["dst"] for e in rels],
                    }
                )

            offset += len(batch)

        conn.close()

        # 3. Cargar manifest anterior para detección incremental
        prev_manifest = _load_manifest(output)
        new_manifest: dict[str, str] = {}
        changed_count = 0

        # 3b. Escribir archivos (determinista: ordenado por type, luego por title)
        nav: list[dict[str, Any]] = []
        count = 0

        for doc_type in sorted(by_type.keys()):
            docs = sorted(by_type[doc_type], key=lambda d: (d["title"].lower(), d["id"]))
            type_dir = dest / _sanitize_filename(doc_type)
            type_dir.mkdir(exist_ok=True)
            nav_entry: dict[str, Any] = {doc_type: []}

            for doc in docs:
                doc_id = doc["id"]
                content = doc["content"]
                new_hash = _content_hash(content)
                new_manifest[doc_id] = new_hash

                # Solo escribir si el contenido cambió
                if prev_manifest.get(doc_id) == new_hash:
                    # No cambió — podemos saltar
                    nav_entry[doc_type].append(
                        {doc["title"]: f"{_sanitize_filename(doc_type)}/{_sanitize_filename(doc_id)}.md"}
                    )
                    count += 1
                    continue

                safe_name = _sanitize_filename(doc_id)
                file_path = type_dir / f"{safe_name}.md"
                file_path.write_text(content, encoding="utf-8")
                changed_count += 1
                nav_entry[doc_type].append({doc["title"]: f"{_sanitize_filename(doc_type)}/{safe_name}.md"})
                count += 1

            nav.append(nav_entry)

        # 4. Verificar enlaces internos
        for doc_type in by_type:
            for doc in by_type[doc_type]:
                broken = _verify_links(doc["content"], all_ids_set)
                if broken:
                    broken_links_total += len(broken)
                    log.warning("Broken links in doc %s: %s", doc["id"], broken)

        # 5. Generar mkdocs.yml (determinista: sorted nav keys)
        mkdocs_config: dict[str, Any] = {
            "site_name": "Knowledge Base",
            "site_description": "URA Knowledge Engine — Generated Documentation",
            "theme": "material",
            "nav": [{"Home": "index.md"}] + nav,
            "plugins": ["search"],
            "markdown_extensions": ["admonition", "pymdownx.superfences"],
        }
        # Guardar manifest para próxima generación incremental
        _save_manifest(dest, new_manifest)
        (dest / "mkdocs.yml").write_text(
            yaml.dump(mkdocs_config, default_flow_style=False, sort_keys=True), encoding="utf-8"
        )

        # 6. Generar index.md
        index_lines = [
            "# Knowledge Base\n",
            f"Generated from Knowledge Engine v0.2.0\n",
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

        # 7. Renombrar atómicamente
        if output.exists():
            backup = output.parent / f"{output.name}.bak"
            if backup.exists():
                import shutil as _shutil

                _shutil.rmtree(backup)
            output.rename(backup)
        dest.rename(output)

        # Limpiar backup
        backup = output.parent / f"{output.name}.bak"
        if backup.exists():
            import shutil as _shutil

            _shutil.rmtree(backup)

        log.info(
            "Knowledge base generated: %d docs (%d changed) in %s%s",
            count,
            changed_count,
            output,
            f" ({broken_links_total} broken links)" if broken_links_total else "",
        )
        return count

    except Exception:
        log.exception("Knowledge base generation failed")
        # Limpiar temp dir (el destino original NO se toca si falló)
        import shutil as _shutil

        _shutil.rmtree(tmp_dir, ignore_errors=True)
        return 0
