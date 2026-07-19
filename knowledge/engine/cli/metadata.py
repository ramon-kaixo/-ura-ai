"""CLI: metadata — lineage, gobernanza y memoria."""

from knowledge.engine.cli.main import _resolve_db_path


def cmd_metadata_lineage(args) -> int:
    """Muestra el lineage de un asset."""
    from knowledge.engine.lineage_store import SQLiteLineageStore

    db_path = _resolve_db_path(args)
    asset_id = args.asset_id
    store = SQLiteLineageStore(db_path)

    events = store.get_lineage(asset_id)
    if not events:
        return 0

    for _ev in events:
        pass

    upstream = store.get_upstream(asset_id)
    downstream = store.get_downstream(asset_id)
    if upstream:
        pass
    if downstream:
        pass
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
            return 0
        for _p in policies:
            pass
    else:
        policies = store.list_policies()
        if not policies:
            return 0
        for _p in policies:
            pass
    return 0


def cmd_memory_create(args) -> int:
    import uuid

    from knowledge.engine.memory_store import MemoryRecord, SQLiteMemoryStore

    db_path = _resolve_db_path(args)
    kind = args.kind
    title = args.title
    content = args.content
    tags = args.tags.split(",") if hasattr(args, "tags") and args.tags else []
    mid = uuid.uuid4().hex[:16]
    r = MemoryRecord(memory_id=mid, kind=kind, title=title, content=content, tags=tuple(t.strip() for t in tags))
    ok = SQLiteMemoryStore(db_path).save(r)
    return 0 if ok else 1


def cmd_memory_list(args) -> int:
    from knowledge.engine.memory_store import SQLiteMemoryStore

    db_path = _resolve_db_path(args)
    kind = getattr(args, "kind", None)
    limit = getattr(args, "limit", 100)
    rs = SQLiteMemoryStore(db_path).list(kind=kind, limit=limit)
    if not rs:
        return 0
    for _r in rs:
        pass
    return 0


def cmd_memory_show(args) -> int:
    from knowledge.engine.memory_store import SQLiteMemoryStore

    db_path = _resolve_db_path(args)
    r = SQLiteMemoryStore(db_path).get(args.memory_id)
    if not r:
        return 1
    return 0


def cmd_memory_search(args) -> int:
    from knowledge.engine.memory_store import SQLiteMemoryStore

    db_path = _resolve_db_path(args)
    kind = getattr(args, "kind", None)
    rs = SQLiteMemoryStore(db_path).search(args.query, kind=kind, limit=getattr(args, "limit", 10))
    if not rs:
        return 0
    for _r in rs:
        pass
    return 0


def cmd_memory_link(args) -> int:
    from knowledge.engine.memory_store import SQLiteMemoryStore

    db_path = _resolve_db_path(args)
    ok = SQLiteMemoryStore(db_path).link_asset(args.memory_id, args.asset_id)
    return 0 if ok else 1


def cmd_metadata_retrieve(args) -> int:
    """Retrieve context from the Knowledge Graph."""
    from knowledge.engine.graphrag import SQLiteGraphRetriever

    db_path = _resolve_db_path(args)
    query = args.query
    limit = getattr(args, "limit", 10)
    retriever = SQLiteGraphRetriever(db_path)
    ctx = retriever.build_context(query=query, max_assets=limit, max_memories=5)
    for _a in ctx.assets[:3]:
        pass
    return 0


def cmd_metadata_context(args) -> int:
    """Build a detailed context bundle for a query."""
    from knowledge.engine.graphrag import SQLiteGraphRetriever

    db_path = _resolve_db_path(args)
    query = args.query
    retriever = SQLiteGraphRetriever(db_path)
    retriever.build_context(query=query, max_assets=20, max_memories=10)
    return 0
