"""CLI main — parser, entry point, shared helpers."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

DEFAULT_DB_PATH = Path.home() / "URA" / "ura_ia_1972" / "knowledge" / "knowledge.db"
SCHEMA_FILE = Path(__file__).resolve().parent.parent.parent.parent / "schemas" / "knowledge_graph.sql"


def _resolve_db_path(args) -> Path:
    if hasattr(args, "db_path") and args.db_path:
        return Path(args.db_path)
    env = os.environ.get("URA_KNOWLEDGE_DB")
    if env:
        return Path(env)
    return DEFAULT_DB_PATH


def _get_conn(db_path: Path):
    from knowledge.engine.connection import open_db

    db_path.parent.mkdir(parents=True, exist_ok=True)
    return open_db(db_path)


def build_parser() -> argparse.ArgumentParser:
    """Construye el árbol de subcomandos CLI."""
    # Imports diferidos para evitar ciclos y acelerar startup
    from knowledge.engine.cli.agent import cmd_agent_list, cmd_agent_run
    from knowledge.engine.cli.api import cmd_api
    from knowledge.engine.cli.archive import (
        cmd_archive_list,
        cmd_archive_restore,
        cmd_archive_source,
        cmd_archive_verify,
    )
    from knowledge.engine.cli.audit import cmd_audit_db, cmd_vacuum
    from knowledge.engine.cli.compile import cmd_compile, cmd_compile_incremental, cmd_init, cmd_status, cmd_verify
    from knowledge.engine.cli.docs import cmd_docs_generate
    from knowledge.engine.cli.doctor import cmd_doctor
    from knowledge.engine.cli.feedback import cmd_feedback_rate, cmd_feedback_top
    from knowledge.engine.cli.jobs import cmd_job_process
    from knowledge.engine.cli.metadata import (
        cmd_memory_create,
        cmd_memory_link,
        cmd_memory_list,
        cmd_memory_search,
        cmd_memory_show,
        cmd_metadata_context,
        cmd_metadata_lineage,
        cmd_metadata_policy,
        cmd_metadata_retrieve,
    )
    from knowledge.engine.cli.notify import cmd_notify_test
    from knowledge.engine.cli.pipeline import cmd_pipeline_run
    from knowledge.engine.cli.rules import cmd_deduce, cmd_rules_eval, cmd_rules_list
    from knowledge.engine.cli.search import cmd_read, cmd_related, cmd_search

    parser = argparse.ArgumentParser(description="URA Knowledge Engine")
    parser.add_argument("--db-path", help="Override knowledge.db path (env: URA_KNOWLEDGE_DB)")
    parser.set_defaults(func=lambda _: parser.print_help() or 1)

    sub = parser.add_subparsers()

    p_init = sub.add_parser("init", help="Create/reset knowledge.db")
    p_init.set_defaults(func=cmd_init)

    p_verify = sub.add_parser("verify", help="Full graph integrity check")
    p_verify.add_argument("--source-dir", help="Path to source/ for hash verification")
    p_verify.set_defaults(func=cmd_verify)

    p_status = sub.add_parser("status", help="Show graph stats")
    p_status.set_defaults(func=cmd_status)

    p_compile = sub.add_parser("compile", help="Compile source/ → knowledge.db")
    p_compile.add_argument("--source-dir", help="Source directory (default: project source/)")
    p_compile.set_defaults(func=cmd_compile)

    p_read = sub.add_parser("read", help="Show document by ID")
    p_read.add_argument("doc_id", help="Document ID")
    p_read.set_defaults(func=cmd_read)

    p_search = sub.add_parser("search", help="Full-text search documents")
    p_search.add_argument("query", help="FTS5 query string")
    p_search.add_argument(
        "--mode", default="lexical", choices=["lexical", "hybrid"], help="Search mode (default: lexical)"
    )
    p_search.add_argument("--type", help="Filter by doc type")
    p_search.add_argument("--limit", type=int, default=10, help="Max results (default: 10)")
    p_search.set_defaults(func=cmd_search)

    p_rel = sub.add_parser("related", help="Show related documents")
    p_rel.add_argument("doc_id", help="Document ID")
    p_rel.add_argument("--relation", help="Filter by relation type")
    p_rel.add_argument("--depth", type=int, default=2, help="Traversal depth (default: 2)")
    p_rel.set_defaults(func=cmd_related)

    p_doc = sub.add_parser("doctor", help="Health check integral")
    p_doc.set_defaults(func=cmd_doctor)

    p_jobs = sub.add_parser("job-process", help="Process pending op_jobs (compile + archive)")
    p_jobs.add_argument("--source-dir", help="Source directory for compile jobs")
    p_jobs.set_defaults(func=cmd_job_process)

    p_vacuum = sub.add_parser("vacuum", help="VACUUM database (reclaim space)")
    p_vacuum.set_defaults(func=cmd_vacuum)

    p_audit = sub.add_parser("audit-db", help="Audit database invariants")
    p_audit.set_defaults(func=cmd_audit_db)

    # rules
    p_rules = sub.add_parser("rules", help="Rule evaluation")
    rules_sub = p_rules.add_subparsers(dest="rules_cmd", required=True)
    p_rules_list = rules_sub.add_parser("list", help="List all rules")
    p_rules_list.set_defaults(func=cmd_rules_list)
    p_rules_eval = rules_sub.add_parser("eval", help="Evaluate rules against documents")
    p_rules_eval.add_argument("doc_id", nargs="?", help="Document ID or path (optional)")
    p_rules_eval.set_defaults(func=cmd_rules_eval)

    p_deduce = sub.add_parser("deduce", help="Run StateDeductor")
    p_deduce.set_defaults(func=cmd_deduce)

    p_compile_inc = sub.add_parser("compile-incremental", help="Incremental compile (only changed files)")
    p_compile_inc.add_argument("--source-dir", help="Source directory")
    p_compile_inc.set_defaults(func=cmd_compile_incremental)

    # pipeline
    p_pipeline = sub.add_parser("pipeline", help="Pipeline DAG (compile → verify → rules)")
    p_pipeline.add_argument("--source-dir", help="Source directory")
    p_pipeline.add_argument("--archive-dir", help="Archive directory")
    p_pipeline.set_defaults(func=cmd_pipeline_run)

    # agent
    p_agent = sub.add_parser("agent", help="Knowledge agents")
    agent_sub = p_agent.add_subparsers(dest="agent_cmd", required=True)
    p_agent_list = agent_sub.add_parser("list", help="List available agents")
    p_agent_list.set_defaults(func=cmd_agent_list)
    p_agent_run = agent_sub.add_parser("run", help="Run an agent")
    p_agent_run.add_argument("agent_id", help="Agent ID")
    p_agent_run.add_argument("--kind", default="audit", help="Goal kind (audit/coverage/consistency)")
    p_agent_run.set_defaults(func=cmd_agent_run)

    # feedback
    p_feedback = sub.add_parser("feedback", help="Document feedback and ratings")
    fb_sub = p_feedback.add_subparsers(dest="feedback_cmd", required=True)
    p_fb_rate = fb_sub.add_parser("rate", help="Rate a document (1-5)")
    p_fb_rate.add_argument("doc_id", help="Document ID")
    p_fb_rate.add_argument("rating", type=int, help="Rating (1-5)")
    p_fb_rate.set_defaults(func=cmd_feedback_rate)
    p_fb_top = fb_sub.add_parser("top", help="Top rated documents")
    p_fb_top.add_argument("--limit", type=int, default=10, help="Max results (default: 10)")
    p_fb_top.set_defaults(func=cmd_feedback_top)

    # api
    p_api = sub.add_parser("api", help="Start API server (FastAPI port 4097)")
    p_api.add_argument("--port", type=int, default=4097, help="Port (default: 4097)")
    p_api.add_argument("--host", default="127.0.0.1", help="Host (default: 127.0.0.1)")
    p_api.add_argument("--auth", help="API Key for Bearer authentication (default: URA_API_KEY env)")
    p_api.set_defaults(func=cmd_api)

    # archive
    p_archive = sub.add_parser("archive", help="Source archival operations")
    arch_sub = p_archive.add_subparsers(dest="archive_cmd", required=True)

    p_arch_source = arch_sub.add_parser("source", help="Create source archive (git bundle)")
    p_arch_source.add_argument("--source-dir", help="Source directory to archive")
    p_arch_source.add_argument("--archive-dir", help="Output archive directory")
    p_arch_source.add_argument("--retention-days", type=int, help="Override retention policy")
    p_arch_source.set_defaults(func=cmd_archive_source)

    p_arch_list = arch_sub.add_parser("list", help="List available archives")
    p_arch_list.add_argument("--archive-dir", help="Archive directory to scan")
    p_arch_list.set_defaults(func=cmd_archive_list)

    p_arch_verify = arch_sub.add_parser("verify", help="Verify archive integrity")
    p_arch_verify.add_argument("manifest", help="Path to .manifest.json file")
    p_arch_verify.add_argument("--archive-dir", help="Allowed archive directory")
    p_arch_verify.set_defaults(func=cmd_archive_verify)

    p_arch_restore = arch_sub.add_parser("restore", help="Restore source from archive")
    p_arch_restore.add_argument("manifest", help="Path to .manifest.json file")
    p_arch_restore.add_argument("--dest", help="Restore destination directory")
    p_arch_restore.add_argument("--archive-dir", help="Allowed archive directory")
    p_arch_restore.set_defaults(func=cmd_archive_restore)

    # docs
    p_docs = sub.add_parser("docs", help="Generate knowledge base (MkDocs)")
    docs_sub = p_docs.add_subparsers(dest="docs_cmd", required=True)
    p_docs_gen = docs_sub.add_parser("generate", help="Generate MkDocs from graph")
    p_docs_gen.add_argument("--output", help="Output directory (default: docs/knowledge)")
    p_docs_gen.set_defaults(func=cmd_docs_generate)

    # notify
    p_notify = sub.add_parser("notify", help="Test notification channels")
    p_notify.add_argument("--webhook", help="Webhook URL to test")
    p_notify.add_argument("--slack", help="Slack webhook URL to test")
    p_notify.set_defaults(func=cmd_notify_test)

    # metadata
    p_meta = sub.add_parser("metadata", help="Metadata operations (lineage, governance)")
    meta_sub = p_meta.add_subparsers(dest="metadata_cmd", required=True)
    p_meta_lineage = meta_sub.add_parser("lineage", help="Show lineage for an asset")
    p_meta_lineage.add_argument("asset_id", help="Asset ID")
    p_meta_lineage.set_defaults(func=cmd_metadata_lineage)
    p_meta_policy = meta_sub.add_parser("policy", help="Show governance policies")
    p_meta_policy.add_argument("asset_id", nargs="?", help="Asset ID (optional)")
    p_meta_policy.set_defaults(func=cmd_metadata_policy)

    # memory subcommands
    p_mem = meta_sub.add_parser("memory", help="Memory operations (conversations, decisions, incidents)")
    mem_sub = p_mem.add_subparsers(dest="memory_cmd", required=True)
    p_mem_create = mem_sub.add_parser("create", help="Create a memory record")
    p_mem_create.add_argument(
        "kind", choices=["conversation", "decision", "incident", "learning", "note"], help="Memory kind"
    )
    p_mem_create.add_argument("title", help="Title")
    p_mem_create.add_argument("content", help="Content")
    p_mem_create.add_argument("--tags", help="Comma-separated tags")
    p_mem_create.set_defaults(func=cmd_memory_create)
    p_mem_list = mem_sub.add_parser("list", help="List memories")
    p_mem_list.add_argument(
        "--kind", choices=["conversation", "decision", "incident", "learning", "note"], help="Filter by kind"
    )
    p_mem_list.add_argument("--limit", type=int, default=100, help="Max results")
    p_mem_list.set_defaults(func=cmd_memory_list)
    p_mem_show = mem_sub.add_parser("show", help="Show a memory record")
    p_mem_show.add_argument("memory_id", help="Memory ID")
    p_mem_show.set_defaults(func=cmd_memory_show)
    p_mem_search = mem_sub.add_parser("search", help="Search memories")
    p_mem_search.add_argument("query", help="Search query")
    p_mem_search.add_argument(
        "--kind", choices=["conversation", "decision", "incident", "learning", "note"], help="Filter by kind"
    )
    p_mem_search.add_argument("--limit", type=int, default=10, help="Max results")
    p_mem_search.set_defaults(func=cmd_memory_search)
    p_mem_link = mem_sub.add_parser("link", help="Link an asset to a memory")
    p_mem_link.add_argument("memory_id", help="Memory ID")
    p_mem_link.add_argument("asset_id", help="Asset ID to link")
    p_mem_link.set_defaults(func=cmd_memory_link)

    # graphrag subcommands (under metadata)
    p_meta_retrieve = meta_sub.add_parser("retrieve", help="Retrieve context from Knowledge Graph")
    p_meta_retrieve.add_argument("query", help="Search query")
    p_meta_retrieve.add_argument("--limit", type=int, default=10, help="Max results")
    p_meta_retrieve.set_defaults(func=cmd_metadata_retrieve)
    p_meta_context = meta_sub.add_parser("context", help="Build detailed context bundle")
    p_meta_context.add_argument("query", help="Search query")
    p_meta_context.set_defaults(func=cmd_metadata_context)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
