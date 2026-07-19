"""CLI: read, search, related."""

from knowledge.engine.cli.main import _resolve_db_path
from knowledge.engine.reader import KnowledgeReader


def cmd_read(args) -> int:
    db_path = _resolve_db_path(args)
    if not db_path.exists():
        return 1
    reader = KnowledgeReader(db_path=db_path)
    doc = reader.get_document(args.doc_id)
    if doc is None:
        return 1
    doc.body[:500]
    return 0


def cmd_search(args) -> int:
    db_path = _resolve_db_path(args)
    if not db_path.exists():
        return 1
    filters: dict = {}
    if hasattr(args, "type") and args.type:
        filters["type"] = args.type
    mode = getattr(args, "mode", "lexical")
    limit = getattr(args, "limit", 10)
    reader = KnowledgeReader(db_path=db_path)
    results = reader.search(args.query, mode=mode, filters=filters, limit=limit)
    if not results:
        return 0
    for r in results:
        r.snippet[:120].replace("\n", " ")
    return 0


def cmd_related(args) -> int:
    db_path = _resolve_db_path(args)
    if not db_path.exists():
        return 1
    depth = getattr(args, "depth", 2)
    relation = getattr(args, "relation", None)
    reader = KnowledgeReader(db_path=db_path)
    try:
        related = reader.related(args.doc_id, relation=relation, depth=depth)
    except Exception:
        return 1
    if not related:
        return 0
    for _r in related:
        pass
    return 0
