"""CLI: read, search, related."""

import sys

from knowledge.engine.cli.main import _resolve_db_path
from knowledge.engine.reader import KnowledgeReader


def cmd_read(args) -> int:
    db_path = _resolve_db_path(args)
    if not db_path.exists():
        print("Knowledge DB not found", file=sys.stderr)
        return 1
    reader = KnowledgeReader(db_path=db_path)
    doc = reader.get_document(args.doc_id)
    if doc is None:
        print(f"Document not found: {args.doc_id}", file=sys.stderr)
        return 1
    print(f"ID:    {doc.doc_id}")
    print(f"Type:  {doc.doc_type}")
    print(f"Path:  {doc.path}")
    print(f"Title: {doc.frontmatter.title}")
    print(f"Tags:  {', '.join(doc.tags)}")
    body_preview = doc.body[:500]
    print(f"Body:  {body_preview}..." if len(doc.body) > 500 else f"Body:  {doc.body}")
    return 0


def cmd_search(args) -> int:
    db_path = _resolve_db_path(args)
    if not db_path.exists():
        print("Knowledge DB not found", file=sys.stderr)
        return 1
    filters: dict = {}
    if hasattr(args, "type") and args.type:
        filters["type"] = args.type
    mode = getattr(args, "mode", "lexical")
    limit = getattr(args, "limit", 10)
    reader = KnowledgeReader(db_path=db_path)
    results = reader.search(args.query, mode=mode, filters=filters, limit=limit)
    if not results:
        print("No results.")
        return 0
    for r in results:
        snippet = r.snippet[:120].replace("\n", " ")
        print(f"  {r.score:.4f} [{r.doc_id}] {r.title} — {snippet}")
    return 0


def cmd_related(args) -> int:
    db_path = _resolve_db_path(args)
    if not db_path.exists():
        print("Knowledge DB not found", file=sys.stderr)
        return 1
    depth = getattr(args, "depth", 2)
    relation = getattr(args, "relation", None)
    reader = KnowledgeReader(db_path=db_path)
    try:
        related = reader.related(args.doc_id, relation=relation, depth=depth)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    if not related:
        print("No related documents found.")
        return 0
    for r in related:
        print(f"  [{r.relation}] {r.doc_id} ({r.title})")
    return 0
