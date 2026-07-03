"""CLI: feedback rate, top."""

import sys

from knowledge.engine.cli.main import _resolve_db_path


def cmd_feedback_rate(args) -> int:
    """Registrar valoración de un documento."""
    from knowledge.engine.feedback import record_feedback

    db_path = _resolve_db_path(args)
    doc_id = args.doc_id
    rating = args.rating

    if rating < 1 or rating > 5:
        print("Rating must be between 1 and 5", file=sys.stderr)
        return 1

    ok = record_feedback(db_path, doc_id, rating)
    if ok:
        print(f"Feedback recorded: {doc_id} → {rating}/5")
        return 0
    print("Failed to record feedback", file=sys.stderr)
    return 1


def cmd_feedback_top(args) -> int:
    """Listar documentos mejor valorados."""
    from knowledge.engine.feedback import top_rated

    db_path = _resolve_db_path(args)
    limit = getattr(args, "limit", 10)

    results = top_rated(db_path, limit=limit)
    if not results:
        print("No feedback data yet.")
        return 0

    print(f"{'Rating':8s} {'Doc ID':15s} {'Last feedback'}")
    print("-" * 50)
    for fb in results:
        stars = "\u2b50" * fb.rating + "\u2606" * (5 - fb.rating)
        print(f"  {fb.rating}/5  {stars:6s}  {fb.doc_id:15s}  {fb.timestamp[:10] if fb.timestamp else '':10s}")
    return 0
