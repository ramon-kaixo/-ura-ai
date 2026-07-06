"""KnowledgeVerifier — verificaciones de consistencia del conocimiento (KE1xx).

Chequeos:
  - IDs duplicados
  - Paths duplicados
  - Hashes repetidos (documentos duplicados reales)
  - Hash de contenido (content_sha256) vs source/ actual
  - Integridad referencial (edges apuntan a nodes existentes)
  - Nodos huérfanos
  - Ciclos no permitidos en el grafo
  - Ontología: parent_id existente, nodos huérfanos
"""

from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path


def check_duplicate_ids(conn: sqlite3.Connection) -> list[str]:
    issues: list[str] = []
    dups = conn.execute("SELECT id, COUNT(*) as cnt FROM kg_nodes GROUP BY id HAVING cnt > 1").fetchall()
    for d in dups:
        issues.append(f"KE101|ID duplicado: '{d['id']}' aparece {d['cnt']} veces")
    return issues


def check_duplicate_paths(conn: sqlite3.Connection) -> list[str]:
    issues: list[str] = []
    dups = conn.execute("SELECT path, COUNT(*) as cnt FROM kg_nodes GROUP BY path HAVING cnt > 1").fetchall()
    for d in dups:
        issues.append(f"KE102|Path duplicado: '{d['path']}' aparece {d['cnt']} veces")
    return issues


def check_repeated_hashes(conn: sqlite3.Connection) -> list[str]:
    issues: list[str] = []
    rows = conn.execute(
        "SELECT content_sha256, GROUP_CONCAT(id) as ids, COUNT(*) as cnt "
        "FROM kg_nodes GROUP BY content_sha256 HAVING cnt > 1"
    ).fetchall()
    for r in rows:
        issues.append(f"KE103|Hash repetido '{r['content_sha256'][:12]}' en {r['cnt']} docs: {r['ids']}")
    return issues


def check_referential_integrity(conn: sqlite3.Connection) -> list[str]:
    issues: list[str] = []
    node_ids = {r["id"] for r in conn.execute("SELECT id FROM kg_nodes").fetchall()}
    for row in conn.execute("SELECT src, dst, relation FROM kg_edges").fetchall():
        if row["src"] not in node_ids:
            issues.append(f"KE105|kg_edges.src '{row['src']}' no existe en kg_nodes")
        if row["dst"] not in node_ids:
            issues.append(f"KE106|kg_edges.dst '{row['dst']}' no existe en kg_nodes")
    onto_ids = {r["id"] for r in conn.execute("SELECT id FROM kg_ontology_nodes").fetchall()}
    for row in conn.execute("SELECT src, dst FROM kg_ontology_edges").fetchall():
        if row["src"] not in onto_ids:
            issues.append(f"KE105|kg_ontology_edges.src '{row['src']}' no existe")
        if row["dst"] not in onto_ids:
            issues.append(f"KE106|kg_ontology_edges.dst '{row['dst']}' no existe")
    return issues


def check_orphans(conn: sqlite3.Connection) -> list[str]:
    issues: list[str] = []
    orphans = conn.execute(
        "SELECT id FROM kg_nodes WHERE id NOT IN (SELECT src FROM kg_edges UNION SELECT dst FROM kg_edges)"
    ).fetchall()
    if orphans:
        ids = [r["id"] for r in orphans[:10]]
        issues.append(f"KE104|Nodos sin aristas: {len(orphans)} (id: {ids})")
    return issues


def check_cycles(conn: sqlite3.Connection) -> list[str]:
    issues: list[str] = []
    edges = conn.execute("SELECT src, dst FROM kg_edges").fetchall()
    adj: dict[str, list[str]] = {}
    for e in edges:
        adj.setdefault(e["src"], []).append(e["dst"])
    visited: set[str] = set()
    rec_stack: set[str] = set()

    def dfs(node: str) -> bool:
        visited.add(node)
        rec_stack.add(node)
        for neighbor in adj.get(node, []):
            if neighbor not in visited:
                if dfs(neighbor):
                    return True
            elif neighbor in rec_stack:
                issues.append(f"KE008|Ciclo detectado: {node} -> {neighbor}")
                return True
        rec_stack.discard(node)
        return False

    for node in adj:
        if node not in visited:
            dfs(node)
    return issues


def check_ontology(conn: sqlite3.Connection) -> list[str]:
    issues: list[str] = []
    parents = {r["id"] for r in conn.execute("SELECT id FROM kg_ontology_nodes").fetchall()}
    for row in conn.execute("SELECT id, name, parent_id FROM kg_ontology_nodes WHERE parent_id IS NOT NULL").fetchall():
        if row["parent_id"] not in parents:
            issues.append(
                f"KE107|Ontología '{row['name']}' (id={row['id']}) tiene parent_id '{row['parent_id']}' que no existe"
            )

    orphan_onto = conn.execute(
        "SELECT id, name FROM kg_ontology_nodes WHERE id NOT IN "
        "(SELECT src FROM kg_ontology_edges UNION SELECT dst FROM kg_ontology_edges) "
        "AND id NOT IN (SELECT parent_id FROM kg_ontology_nodes WHERE parent_id IS NOT NULL)"
    ).fetchall()
    if orphan_onto and len(parents) > 1:
        ids = [f"{r['name']}({r['id']})" for r in orphan_onto[:5]]
        issues.append(f"KE108|Nodos de ontología sin conexiones: {ids}")
    return issues


def verify_hashes(conn: sqlite3.Connection, source_dir: Path | None = None) -> list[str]:
    issues: list[str] = []
    if source_dir is None:
        source_dir = Path(__file__).resolve().parent.parent.parent / "source"
    for row in conn.execute("SELECT id, path, content_sha256 FROM kg_nodes").fetchall():
        doc_path = source_dir / row["path"]
        if not doc_path.exists():
            issues.append(f"Documento no encontrado: {row['path']} (id={row['id']})")
            continue
        actual_hash = hashlib.sha256(doc_path.read_bytes()).hexdigest()
        if actual_hash != row["content_sha256"]:
            exp = row["content_sha256"][:12]
            issues.append(f"Hash no coincide: {row['path']} (esperado={exp}, actual={actual_hash[:12]})")
    return issues
