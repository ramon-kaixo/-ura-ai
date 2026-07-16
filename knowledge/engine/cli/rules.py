"""CLI: rules list|eval, deduce."""

import sys

from knowledge.engine.cli.main import _resolve_db_path


def cmd_rules_list(args) -> int:
    from knowledge.engine.rules import list_rules

    rules = list_rules()
    print(f"{'ID':6s} {'Severidad':10s} {'Nombre':30s} {'Descripción'}")
    print("-" * 80)
    for r in rules:
        sev = {"INFO": "\u2139\ufe0f", "WARN": "\u26a0\ufe0f", "ERROR": "\u274c"}.get(r.metadata.severity, "?")
        print(f"{r.metadata.id:6s} {sev:1s} {r.metadata.severity:8s} {r.metadata.id:30s} {r.metadata.description}")
    return 0


def cmd_rules_eval(args) -> int:
    from knowledge.engine.connection import open_db
    from knowledge.engine.rules import RuleEvaluator
    import json

    db_path = _resolve_db_path(args)
    if not db_path.exists():
        print("DB not found", file=sys.stderr)
        return 1

    conn = open_db(db_path)
    rows = conn.execute("SELECT id, type, path, frontmatter, body FROM kg_nodes").fetchall()
    edges = conn.execute("SELECT src, dst FROM kg_edges").fetchall()
    conn.close()

    all_node_ids = {r["id"] for r in rows}
    all_relation_targets = {e["dst"] for e in edges}

    documents = []
    for r in rows:
        fm = json.loads(r["frontmatter"]) if r["frontmatter"] else {}
        documents.append(
            {
                "id": r["id"],
                "path": r["path"],
                "type": r["type"],
                "title": fm.get("title", ""),
                "tags": fm.get("tags", []),
                "body": r["body"] or "",
                "relations": [e["dst"] for e in edges if e["src"] == r["id"]],
            }
        )

    filter_id = args.doc_id if hasattr(args, "doc_id") and args.doc_id else None
    if filter_id:
        documents = [d for d in documents if d["id"] == filter_id or filter_id in d["path"]]
        if not documents:
            print(f"Documento no encontrado: {filter_id}", file=sys.stderr)
            return 1

    evaluator = RuleEvaluator()
    results = evaluator.evaluate(documents, all_node_ids, all_relation_targets)

    if not results:
        print("No se detectaron incidencias.")
        return 0

    for r in results:
        sev = {"INFO": "\u2139\ufe0f", "WARN": "\u26a0\ufe0f", "ERROR": "\u274c"}.get(r.severity, "?")
        print(f"{sev} [{r.rule_id}] {r.doc_id}: {r.message}")
    print(f"\nTotal: {len(results)} incidencias")
    return 1 if any(r.severity == "ERROR" for r in results) else 0


def cmd_deduce(args) -> int:
    from knowledge.engine.connection import open_db
    from knowledge.engine.deduction import StateDeductor

    db_path = _resolve_db_path(args)
    if not db_path.exists():
        print("DB not found", file=sys.stderr)
        return 1

    conn = open_db(db_path)
    rows = conn.execute("SELECT id, type, path FROM kg_nodes").fetchall()
    edge_rows = conn.execute("SELECT src, dst, relation FROM kg_edges").fetchall()
    conn.close()

    nodes = [dict(r) for r in rows]
    edges = [dict(e) for e in edge_rows]

    deductor = StateDeductor()
    deductions = deductor.deduce(nodes, edges)

    if not deductions:
        print("No se realizaron deducciones.")
        return 0

    for d in deductions:
        conf = f"{d.confidence:.0%}"
        print(f"  [{d.kind:12s}] ({conf:4s}) {d.description}")
    print(f"\nTotal: {len(deductions)} deducciones")
    return 0
