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
        print("No documents found in graph. Run 'ke compile' first.")
        return 1
    print(f"Knowledge base generated: {n} documents")
    if output:
        print(f"  Output: {output.resolve()}")
        print(f"  Serve:  mkdocs serve --config-file {output / 'mkdocs.yml'}")
    return 0
