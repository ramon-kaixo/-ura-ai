#!/usr/bin/env python3
"""Code Indexer — AST-based code indexer with ChromaDB for URA."""

import ast, hashlib, json, logging, sys, time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

log = logging.getLogger(__name__)
REPO_ROOT = Path(__file__).parent.parent.resolve()
DATA_DIR = REPO_ROOT / "core" / "modules" / "data"
CHROMA_DIR = DATA_DIR / "chroma_db_code"
MANIFEST_PATH = DATA_DIR / ".code_index_manifest.json"
WIKI_DIR = REPO_ROOT / "knowledge" / "code-wiki"
EXCLUDE_DIRS = {".git", "__pycache__", "node_modules", ".nervioso", ".venv", "venv", ".mypy_cache", ".ruff_cache"}
EXCLUDE_FILES = {"*.pyc", "*.pyo", "*.so", "*.dll", "*.dylib", "*.bin", "*.exe", "*.jpg", "*.png", "*.gif", "*.svg", "*.lock", "package-lock.json", "yarn.lock"}
MAX_FILE_SIZE = 512 * 1024
COLLECTION_NAME = "ura_code"
TOP_K = 5
SIMILARITY_THRESHOLD = 0.6
EXTENSIONS_LANGUAGE = {".py": "python", ".sh": "bash", ".toml": "toml", ".jsonc": "jsonc", ".json": "json", ".yml": "yaml", ".yaml": "yaml", ".md": "markdown", ".cfg": "ini", ".ini": "ini", ".txt": "text", ".css": "css", ".js": "javascript", ".ts": "typescript", ".jsx": "jsx", ".tsx": "tsx", ".html": "html", ".sql": "sql"}

def _sha256(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()

def _should_exclude(path: Path, repo_root: Path) -> bool:
    rel = path.relative_to(repo_root)
    for part in rel.parts:
        if part in EXCLUDE_DIRS:
            return True
    suffix = path.suffix.lower()
    for pattern in EXCLUDE_FILES:
        if pattern.startswith("*") and suffix == pattern[1:]:
            return True
        if path.name == pattern:
            return True
    if path.stat().st_size > MAX_FILE_SIZE:
        return True
    return False

def _chromadb_available() -> bool:
    import importlib.util
    return importlib.util.find_spec("chromadb") is not None

def _get_collection():
    import chromadb
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return client.get_or_create_collection(name=COLLECTION_NAME, metadata={"hnsw:space": "cosine"})

class _PythonParser:
    def __init__(self, filepath: Path, rel_path: str):
        self.filepath = filepath
        self.rel_path = rel_path
        self.source = filepath.read_text(encoding="utf-8", errors="replace")
        self.tree = ast.parse(self.source, filename=str(filepath))
        self.chunks: list[dict] = []
    def parse(self) -> list[dict]:
        self._module_docstring(); self._classes(); self._functions(); self._imports()
        return self.chunks
    def _module_docstring(self):
        doc = ast.get_docstring(self.tree)
        if doc:
            self.chunks.append({"content": doc, "metadata": {"type": "module_docstring", "symbol": self.rel_path, "language": "python"}})
    def _classes(self):
        for node in ast.walk(self.tree):
            if isinstance(node, ast.ClassDef):
                doc = ast.get_docstring(node) or ""
                methods = [n.name for n in ast.walk(node) if isinstance(n, ast.FunctionDef)]
                parts = [f"class {node.name}:"]
                if doc: parts.append(doc)
                if methods: parts.append(f"Methods: {', '.join(methods)}")
                meta: dict[str, Any] = {"type": "class", "symbol": node.name, "lineno": node.lineno, "language": "python"}
                if methods: meta["methods"] = ", ".join(methods)
                self.chunks.append({"content": "\n".join(parts), "metadata": meta})
    def _functions(self):
        for node in ast.iter_child_nodes(self.tree):
            if isinstance(node, ast.FunctionDef):
                doc = ast.get_docstring(node) or ""
                args = ", ".join(a.arg for a in node.args.args)
                self.chunks.append({"content": f"def {node.name}({args}):\n{doc}".strip(), "metadata": {"type": "function", "symbol": node.name, "lineno": node.lineno, "language": "python"}})
    def _imports(self):
        imps = []
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Import):
                for a in node.names: imps.append(a.name)
            elif isinstance(node, ast.ImportFrom):
                m = node.module or ""
                for a in node.names: imps.append(f"{m}.{a.name}")
        if imps:
            self.chunks.append({"content": "\n".join(sorted(set(imps))), "metadata": {"type": "imports", "symbol": f"{self.rel_path}::imports", "language": "python"}})

class _GenericParser:
    CHUNK_SIZE, CHUNK_OVERLAP = 300, 50
    def __init__(self, filepath: Path, rel_path: str, language: str):
        self.filepath = filepath; self.rel_path = rel_path; self.language = language
        self.source = filepath.read_text(encoding="utf-8", errors="replace")
    def parse(self) -> list[dict]:
        words = self.source.split()
        if not words: return []
        chunks, start = [], 0
        while start < len(words):
            end = min(start + self.CHUNK_SIZE, len(words))
            t = " ".join(words[start:end])
            if t.strip():
                chunks.append({"content": t, "metadata": {"type": "chunk", "symbol": f"{self.rel_path}:L{start}", "language": self.language}})
            start += self.CHUNK_SIZE - self.CHUNK_OVERLAP
        return chunks

def _load_manifest() -> dict:
    if MANIFEST_PATH.exists():
        try: return json.loads(MANIFEST_PATH.read_text())
        except Exception: pass
    return {"indexed_at": None, "total_files": 0, "total_chunks": 0, "files": {}}

def _save_manifest(manifest: dict):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, sort_keys=True))

def _collect_files(root: Path) -> dict[str, Path]:
    files = {}
    for f in sorted(root.rglob("*")):
        if not f.is_file() or _should_exclude(f, root) or f.suffix.lower() not in EXTENSIONS_LANGUAGE:
            continue
        files[str(f.relative_to(root))] = f
    return files

def _extract_chunks(rel_path: str, filepath: Path) -> list[dict]:
    lang = EXTENSIONS_LANGUAGE.get(filepath.suffix.lower(), "text")
    if lang == "python":
        try: return _PythonParser(filepath, rel_path).parse()
        except SyntaxError:
            return _GenericParser(filepath, rel_path, lang).parse()
    return _GenericParser(filepath, rel_path, lang).parse()

def index_code(force: bool = False) -> dict:
    if not _chromadb_available(): return {"error": "chromadb no instalado"}
    import contextlib
    manifest = _load_manifest() if not force else {"indexed_at": None, "total_files": 0, "total_chunks": 0, "files": {}}
    collection = _get_collection()
    current_files = _collect_files(REPO_ROOT)
    stats = {"new": 0, "modified": 0, "unchanged": 0, "deleted": 0, "chunks_added": 0}
    for rel_path in list(manifest.get("files", {}).keys()):
        if rel_path not in current_files:
            try: collection.delete(where={"source": rel_path}); del manifest["files"][rel_path]; stats["deleted"] += 1
            except Exception as e: log.warning("Error eliminando %s: %s", rel_path, e)
    for rel_path, filepath in current_files.items():
        file_hash = _sha256(filepath)
        existing = manifest.get("files", {}).get(rel_path, {})
        if existing.get("sha256") == file_hash and not force:
            stats["unchanged"] += 1; continue
        is_modified = rel_path in manifest.get("files", {})
        if is_modified:
            stats["modified"] += 1
            with contextlib.suppress(Exception): collection.delete(where={"source": rel_path})
        else: stats["new"] += 1
        chunks = _extract_chunks(rel_path, filepath)
        if not chunks: continue
        ids, documents, metadatas = [], [], []
        for i, chunk in enumerate(chunks):
            ids.append(f"{rel_path}_{i}"); documents.append(chunk["content"])
            meta = chunk["metadata"].copy(); meta["source"] = rel_path; meta["chunk_index"] = i; meta["sha256"] = file_hash; meta["indexed_at"] = datetime.now().isoformat()
            metadatas.append(meta)
        try: collection.add(documents=documents, ids=ids, metadatas=metadatas); stats["chunks_added"] += len(chunks)
        except Exception as e: log.error("Error indexando %s: %s", rel_path, e); continue
        manifest["files"][rel_path] = {"sha256": file_hash, "chunks": len(chunks), "indexed_at": datetime.now().isoformat()}
    manifest["indexed_at"] = datetime.now().isoformat()
    manifest["total_files"] = len(manifest["files"]); manifest["total_chunks"] = stats["chunks_added"]
    _save_manifest(manifest); return stats

def query_code(question: str, top_k: int = TOP_K) -> list[dict]:
    if not _chromadb_available(): return []
    try:
        results = _get_collection().query(query_texts=[question], n_results=min(top_k, 20))
    except Exception as e: log.error("Error consultando ChromaDB: %s", e); return []
    if not results or not results.get("documents") or not results["documents"][0]: return []
    output = []
    for i, doc in enumerate(results["documents"][0]):
        meta = (results["metadatas"][0] if results.get("metadatas") else [])[i] if i < len(results.get("metadatas", [[]])[0]) else {}
        dist = (results.get("distances", [[]])[0])[i] if i < len(results.get("distances", [[]])[0]) else 0
        similarity = 1.0 / (1.0 + dist) if dist > 0 else 1.0
        if similarity < SIMILARITY_THRESHOLD: continue
        output.append({"content": doc, "source": meta.get("source", "unknown"), "symbol": meta.get("symbol", ""), "type": meta.get("type", "chunk"), "language": meta.get("language", ""), "similarity": round(similarity, 4)})
    return output

def get_symbol_info(symbol: str) -> list[dict]:
    if not _chromadb_available(): return []
    try:
        results = _get_collection().get(where={"symbol": symbol})
    except Exception: return []
    if not results or not results.get("documents"): return []
    return [{"content": doc, "source": (results["metadatas"][i] if results.get("metadatas") else {}).get("source", "unknown"), "symbol": (results["metadatas"][i] if results.get("metadatas") else {}).get("symbol", ""), "type": (results["metadatas"][i] if results.get("metadatas") else {}).get("type", ""), "lineno": (results["metadatas"][i] if results.get("metadatas") else {}).get("lineno", 0), "language": (results["metadatas"][i] if results.get("metadatas") else {}).get("language", "")} for i, doc in enumerate(results["documents"])]

def generate_wiki(output_dir: Optional[Path] = None) -> dict:
    if not _chromadb_available(): return {"error": "chromadb no instalado"}
    out = Path(output_dir or WIKI_DIR); out.mkdir(parents=True, exist_ok=True)
    try: all_data = _get_collection().get()
    except Exception as e: return {"error": str(e)}
    if not all_data or not all_data.get("documents"): return {"files": 0}
    files_map: dict[str, list[dict]] = {}
    for i, doc in enumerate(all_data["documents"]):
        meta = (all_data["metadatas"][i] if all_data.get("metadatas") else {})
        src = meta.get("source", "unknown")
        files_map.setdefault(src, []).append({"content": doc, "type": meta.get("type", "chunk"), "symbol": meta.get("symbol", ""), "lineno": meta.get("lineno", ""), "language": meta.get("language", "")})
    stats = {"files": 0, "pages": 0}
    for src, chunks in sorted(files_map.items()):
        page_path = out / f"{src}.md"; page_path.parent.mkdir(parents=True, exist_ok=True)
        lang = chunks[0]["language"] if chunks else ""
        lines = [f"# `{src}`", "", f"- **Language:** {lang}", f"- **Chunks:** {len(chunks)}", "", "## Symbols", ""]
        for c in chunks:
            if c["type"] in ("class", "function"):
                lines.append(f"### {c['type']}: `{c['symbol']}`")
                if c.get("lineno"): lines.append(f"- Line: {c['lineno']}")
                lines.extend(["", c["content"], ""])
        for c in chunks:
            if c["type"] == "module_docstring": lines.extend(["## Module Overview", "", c["content"], ""])
        for c in chunks:
            if c["type"] == "imports": lines.extend(["## Imports", "", "```", c["content"], "```", ""])
        page_path.write_text("\n".join(lines)); stats["pages"] += 1
    index_lines = ["# Code Wiki — URA v3.1", "", f"Generated: {datetime.now().isoformat()}", f"Total files: {len(files_map)}", f"Total pages: {stats['pages']}", "", "## Index", ""]
    for src in sorted(files_map): index_lines.append(f"- [{src}]({src}.md)")
    (out / "INDEX.md").write_text("\n".join(index_lines)); stats["files"] = len(files_map)
    return stats

def cli_main():
    import argparse
    logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(message)s")
    parser = argparse.ArgumentParser(prog="ura-code-index")
    parser.add_argument("--quiet", action="store_true"); parser.add_argument("--force", action="store_true")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("index", help="Indexar código en ChromaDB")
    ask_p = sub.add_parser("ask", help="Preguntar sobre el código"); ask_p.add_argument("question", nargs="*")
    wiki_p = sub.add_parser("wiki", help="Generar wiki markdown"); wiki_p.add_argument("--output", "-o", type=Path, default=None)
    info_p = sub.add_parser("info", help="Buscar símbolo"); info_p.add_argument("symbol")
    args = parser.parse_args()
    if args.quiet: logging.getLogger().setLevel(logging.WARNING)

    if args.command == "index" or not args.command:
        t0 = time.time(); stats = index_code(force=args.force)
        if "error" in stats: print(f"❌ {stats['error']}"); sys.exit(1)
        print(f"✅ Indexado en {time.time()-t0:.1f}s: {stats}"); return
    if args.command == "ask":
        q = " ".join(args.question) if args.question else sys.stdin.read().strip()
        if not q: print("❌ Debes proporcionar una pregunta"); sys.exit(1)
        results = query_code(q)
        if not results: print("📭 No se encontraron resultados"); return
        print(f"\n📚 Top {len(results)} resultados para: {q}\n")
        for r in results:
            print(f"  [{r['similarity']:.2f}] {r['source']}  ({r['type']}: {r.get('symbol', '?')})")
            print(f"      {r['content'][:150].replace(chr(10), ' ')}...\n")
    if args.command == "wiki":
        stats = generate_wiki(args.output)
        if "error" in stats: print(f"❌ {stats['error']}"); sys.exit(1)
        print(f"✅ Wiki generada: {stats['pages']} páginas en {stats['files']} archivos")
    if args.command == "info":
        results = get_symbol_info(args.symbol)
        if not results: print(f"📭 Símbolo '{args.symbol}' no encontrado"); return
        print(f"\n🔍 {args.symbol} — {len(results)} ocurrencias:\n")
        for r in results: print(f"  📄 {r['source']}:{r.get('lineno', '?')}\n     {r['content'][:200].replace(chr(10), ' ')}\n")

if __name__ == "__main__":
    cli_main()
