"""CLI: docs — genera Knowledge Base MkDocs desde el grafo."""

from pathlib import Path

from knowledge.engine.cli.main import _resolve_db_path


def cmd_docs_generate(args) -> int:
    """Generate MkDocs knowledge base from the graph."""
    from knowledge.engine.knowledge_base import generate_knowledge_base

    db_path = _resolve_db_path(args)
    output = Path(args.output) if hasattr(args, "output") and args.output else None

    n = generate_knowledge_base(db_path, output_dir=output)
    if n == 0:
        return 1
    if output:
        pass
    return 0
