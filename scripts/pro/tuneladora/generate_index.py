"""generate_index — indexa el código fuente en memoria semántica + repo_index.json."""

from __future__ import annotations

import ast
import json
import logging
import subprocess
import time
from pathlib import Path
from typing import Any

from scripts.pro.tuneladora.config import Configuration
from scripts.pro.tuneladora.memory.semantic import Concept, Relation, SemanticMemory

log = logging.getLogger("tuneladora.generate_index")


def extract_functions(source: Path) -> list[dict[str, Any]]:
    try:
        tree = ast.parse(source.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return []
    funcs: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            funcs.append(
                {
                    "name": node.name,
                    "type": "function",
                    "lineno": node.lineno,
                    "source": str(source),
                }
            )
        elif isinstance(node, ast.ClassDef):
            funcs.append(
                {
                    "name": node.name,
                    "type": "class",
                    "lineno": node.lineno,
                    "source": str(source),
                }
            )
    return funcs


def extract_calls(source: Path) -> list[tuple[str, str]]:
    try:
        tree = ast.parse(source.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return []
    calls: list[tuple[str, str]] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
        ):
            calls.append((node.func.value.id, node.func.attr))
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            calls.append(("module", node.func.id))
    return calls


def build_index(cfg: Configuration, changed_files: list[Path] | None = None) -> dict[str, Any]:
    semantic = SemanticMemory(cfg.knowledge_db)
    index: dict[str, Any] = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "stats": {"functions": 0, "classes": 0, "relations": 0, "files": 0},
        "sources": {},
    }

    discover_root = cfg.ura_root / "scripts" / "pro" / "tuneladora"
    py_files: list[Path] = changed_files or []
    if not py_files:
        py_files = sorted(discover_root.rglob("*.py"))

    for f in py_files:
        rel = f.relative_to(cfg.ura_root) if f.is_relative_to(cfg.ura_root) else f
        funcs = extract_functions(f)
        calls = extract_calls(f)
        for fn in funcs:
            semantic.learn_concept(
                Concept(
                    name=fn["name"],
                    context=str(rel),
                    weight=1.0,
                    tags=(fn["type"],),
                )
            )
        for caller, callee in calls:
            semantic.learn_relation(Relation(source=caller, target=callee, relation_type="calls"))
        index["sources"][str(rel)] = {"functions": funcs, "calls": calls}
        index["stats"]["files"] += 1
        index["stats"]["functions"] += len(funcs)
        index["stats"]["classes"] += sum(1 for f in funcs if f["type"] == "class")
        index["stats"]["relations"] += len(calls)

    index_path = cfg.tuneladora_dir / "repo_index.json"
    index_path.write_text(json.dumps(index, indent=2, ensure_ascii=False))
    log.info(
        "Index guardado en %s: %d funciones, %d relaciones en %d archivos",
        index_path,
        index["stats"]["functions"],
        index["stats"]["relations"],
        index["stats"]["files"],
    )
    return index


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    cfg = Configuration()
    changed: list[Path] = []
    out = subprocess.run(
        ["git", "diff", "--name-only"],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
        cwd=str(cfg.ura_root),
    )
    if out.returncode == 0 and out.stdout:
        changed = [cfg.ura_root / f.strip() for f in out.stdout.split("\n") if f.strip().endswith(".py")]
    build_index(cfg, changed or None)


if __name__ == "__main__":
    main()
