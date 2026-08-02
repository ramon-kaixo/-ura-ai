"""DFS desde la raíz
lanza error si hay spans inalcanzables  (OBS-04)."""

visited: set[str] = set()


def dfs(sid: str) -> None:
    if sid in visited:
        return
    visited.add(sid)
    for s in trace_spans:
        if s.parent_span_id == sid:
            dfs(s.span_id)
