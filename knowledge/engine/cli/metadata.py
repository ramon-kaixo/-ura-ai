"""CLI: metadata — lineage, gobernanza y memoria."""

import json
import uuid

from knowledge.engine.cli.main import _resolve_db_path


def cmd_metadata_lineage(args) -> int:
    """Muestra el lineage de un asset."""
    from knowledge.engine.lineage_store import SQLiteLineageStore

    db_path = _resolve_db_path(args)
    asset_id = args.asset_id
    store = SQLiteLineageStore(db_path)

    events = store.get_lineage(asset_id)
    if not events:
        print(f"No lineage data for asset {asset_id}")
        return 0

    print(f"Lineage for {asset_id}:")
    for ev in events:
        print(f"  [{ev['event_type']}] {ev['event_time'][:19]} | {ev['job_name']}")
        print(f"    Inputs:  {ev.get('input_ids', '[]')}")
        print(f"    Outputs: {ev.get('output_ids', '[]')}")

    upstream = store.get_upstream(asset_id)
    downstream = store.get_downstream(asset_id)
    if upstream:
        print(f"\n  Upstream: {', '.join(upstream)}")
    if downstream:
        print(f"\n  Downstream: {', '.join(downstream)}")
    return 0


def cmd_metadata_policy(args) -> int:
    """Gestiona políticas de gobernanza."""
    from knowledge.engine.governance_store import SQLiteGovernanceStore

    db_path = _resolve_db_path(args)
    store = SQLiteGovernanceStore(db_path)
    asset_id = getattr(args, "asset_id", None)

    if asset_id:
        policies = store.get_policies(asset_id)
        if not policies:
            print(f"No policies for {asset_id}")
            return 0
        for p in policies:
            print(f"  [{p['id']}] {p['asset_id']}: {p['policy']} (by {p['actor']} at {p['created_at']})")
    else:
        policies = store.list_policies()
        if not policies:
            print("No policies defined")
            return 0
        for p in policies:
            print(f"  [{p['id']}] {p['asset_id']}: {p['policy']}")
    return 0


def cmd_memory_create(args) -> int:
    from knowledge.engine.memory_store import MemoryRecord, SQLiteMemoryStore
    import uuid
    db_path = _resolve_db_path(args)
    kind = args.kind
    title = args.title
    content = args.content
    tags = args.tags.split(",") if hasattr(args, "tags") and args.tags else []
    mid = uuid.uuid4().hex[:16]
    r = MemoryRecord(memory_id=mid, kind=kind, title=title, content=content, tags=tuple(t.strip() for t in tags))
    ok = SQLiteMemoryStore(db_path).save(r)
    print(f"Memory created: {mid}" if ok else "Error"); return 0 if ok else 1

def cmd_memory_list(args) -> int:
    from knowledge.engine.memory_store import SQLiteMemoryStore
    db_path = _resolve_db_path(args)
    kind = getattr(args, "kind", None)
    limit = getattr(args, "limit", 100)
    rs = SQLiteMemoryStore(db_path).list(kind=kind, limit=limit)
    if not rs: print("No memories."); return 0
    for r in rs: print(f"  [{r.kind:15s}] {r.memory_id:20s} {r.title[:50]}")
    return 0

def cmd_memory_show(args) -> int:
    from knowledge.engine.memory_store import SQLiteMemoryStore
    db_path = _resolve_db_path(args)
    r = SQLiteMemoryStore(db_path).get(args.memory_id)
    if not r: print(f"Not found: {args.memory_id}"); return 1
    print(f"ID: {r.memory_id}\nKind: {r.kind}\nTitle: {r.title}\nContent: {r.content[:500]}\nTags: {', '.join(r.tags)}\nAssets: {', '.join(r.related_assets)}")
    return 0

def cmd_memory_search(args) -> int:
    from knowledge.engine.memory_store import SQLiteMemoryStore
    db_path = _resolve_db_path(args)
    kind = getattr(args, "kind", None)
    rs = SQLiteMemoryStore(db_path).search(args.query, kind=kind, limit=getattr(args,"limit",10))
    if not rs: print("No results."); return 0
    for r in rs: print(f"  [{r.kind:15s}] {r.memory_id:20s} {r.title[:40]} {r.content[:80]}")
    return 0

def cmd_memory_link(args) -> int:
    from knowledge.engine.memory_store import SQLiteMemoryStore
    db_path = _resolve_db_path(args)
    ok = SQLiteMemoryStore(db_path).link_asset(args.memory_id, args.asset_id)
    print(f"Linked {args.asset_id} to {args.memory_id}" if ok else "Error"); return 0 if ok else 1


def cmd_metadata_retrieve(args) -> int:
    """Retrieve context from the Knowledge Graph."""
    from knowledge.engine.graphrag import SQLiteGraphRetriever

    db_path = _resolve_db_path(args)
    query = args.query
    limit = getattr(args, "limit", 10)
    retriever = SQLiteGraphRetriever(db_path)
    ctx = retriever.build_context(query=query, max_assets=limit, max_memories=5)
    print(f"Query: {query}")
    print(f"Assets:   {ctx.asset_count}")
    print(f"Memories: {ctx.memory_count}")
    print(f"Lineage:  {ctx.lineage_count}")
    print(f"Duration: {ctx.total_duration_ms:.0f}ms")
    for a in ctx.assets[:3]:
        print(f"  [{a['kind']:12s}] {a['title'][:50]:50s} score={a['score']:.2f}")
    return 0


def cmd_metadata_context(args) -> int:
    """Build a detailed context bundle for a query."""
    from knowledge.engine.graphrag import SQLiteGraphRetriever
    import json

    db_path = _resolve_db_path(args)
    query = args.query
    retriever = SQLiteGraphRetriever(db_path)
    ctx = retriever.build_context(query=query, max_assets=20, max_memories=10)
    print(json.dumps(ctx.to_dict(), indent=2, ensure_ascii=False))
    return 0
