"""CLI: feedback rate, top."""

from knowledge.engine.cli.main import _resolve_db_path


def cmd_feedback_rate(args) -> int:
    """Registrar valoración de un documento."""
    from knowledge.engine.feedback import record_feedback

    db_path = _resolve_db_path(args)
    doc_id = args.doc_id
    rating = args.rating

    if rating < 1 or rating > 5:
        return 1

    ok = record_feedback(db_path, doc_id, rating)
    if ok:
        return 0
    return 1


def cmd_feedback_top(args) -> int:
    """Listar documentos mejor valorados."""
    from knowledge.engine.feedback import top_rated

    db_path = _resolve_db_path(args)
    limit = getattr(args, "limit", 10)

    results = top_rated(db_path, limit=limit)
    if not results:
        return 0

    for fb in results:
        "\u2b50" * fb.rating + "\u2606" * (5 - fb.rating)
    return 0
