#!/usr/bin/env python3
import ast
import json
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

PROJECT = Path("/home/ramon/URA/ura_ia_1972")
WORKERS = 2
DEAD_MAN_S = 1800
FUNC_TIMEOUT = 300


@dataclass
class FuncInfo:
    file: str
    name: str
    lines: int
    start_line: int
    end_line: int


def find_large(min_lines=80):
    funcs = []
    exclude = [".venv", "__pycache__", "tests", "scripts/pro", ".nervioso", "backups"]
    for d in ["core", "agents", "adapters", "knowledge", "scripts"]:
        dp = PROJECT / d
        if not dp.exists():
            continue
        for pf in dp.rglob("*.py"):
            rel = str(pf.relative_to(PROJECT))
            if any(e in rel for e in exclude):
                continue
            try:
                tree = ast.parse(pf.read_text(), filename=str(pf))
            except Exception:
                continue
            for n in ast.walk(tree):
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    end = getattr(n, "end_lineno", None)
                    if end and (end - n.lineno + 1) >= min_lines:
                        funcs.append(FuncInfo(rel, n.name, end - n.lineno + 1, n.lineno, end))
    funcs.sort(key=lambda f: f.lines, reverse=True)
    return funcs


def already_done():
    rp = PROJECT / ".nervioso" / "refactor_report.json"
    if not rp.exists():
        return set()
    r = json.loads(rp.read_text())
    for b in r.get("batches", []):
        if b.get("success", 0) > 0:
            for _e in b.get("errors", []):
                pass
    return set()


def ollama_refactor(fi, model):
    lines = (PROJECT / fi.file).read_text().splitlines()
    "\n".join(lines[fi.start_line - 1 : fi.end_line])
    prompt = "Refactoriza esta funcion Python. Divide en sub-funciones si >80 lineas. Devuelve SOLO codigo refactorizado.\n\n"
    try:
        r = subprocess.run(
            ["ollama", "run", model],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=FUNC_TIMEOUT,
            check=False,
        )
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except Exception:  # noqa: S110
        pass
    return None


def apply_refactor(fi, nc) -> None:
    fp = PROJECT / fi.file
    lines = fp.read_text().splitlines()
    s = fi.start_line - 1
    while s > 0 and lines[s - 1].startswith("@"):
        s -= 1
    c = nc
    if c.startswith("```python"):
        c = c[9:]
    elif c.startswith("```"):
        c = c[3:]
    c = c.removesuffix("```")
    new = lines[:s] + c.strip().splitlines() + lines[fi.end_line :]
    fp.write_text("\n".join(new) + "\n")


def worker(bid, funcs, model):
    res = {"batch": bid, "model": model, "success": 0, "failed": 0, "errors": [], "processed": []}
    t0 = time.time()
    for _i, fi in enumerate(funcs):
        if time.time() - t0 > DEAD_MAN_S:
            res["errors"].append("Dead-man timeout")
            break
        nc = ollama_refactor(fi, model)
        if nc:
            try:
                apply_refactor(fi, nc)
                res["success"] += 1
                res["processed"].append(fi.name)
            except Exception as e:
                res["failed"] += 1
                res["errors"].append(f"{fi.name}: {e}")
        else:
            res["failed"] += 1
    res["time"] = round(time.time() - t0, 1)
    return res


def main() -> None:
    funcs = find_large(80)

    # Cargar previo
    rp = PROJECT / ".nervioso" / "refactor_report.json"
    done_names = set()
    if rp.exists():
        r = json.loads(rp.read_text())
        for b in r.get("batches", []):
            for n in b.get("processed", []):
                done_names.add(n)

    pending = [f for f in funcs if f.name not in done_names]

    if not pending:
        return

    bs = len(pending) // WORKERS + 1
    batches = [pending[i : i + bs] for i in range(0, len(pending), bs)]
    models = ["deepseek-coder:6.7b", "qwen2.5:7b"]

    for i, b in enumerate(batches):  # noqa: B007
        pass

    t0 = time.time()
    all_res = []

    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = {}
        for i, b in enumerate(batches):
            futs[ex.submit(worker, i + 1, b, models[i])] = i + 1
        for f in as_completed(futs):
            bid = futs[f]
            try:
                r = f.result(timeout=DEAD_MAN_S + 60)
                all_res.append(r)
            except Exception as e:
                all_res.append(
                    {
                        "batch": bid,
                        "success": 0,
                        "failed": len(batches[bid - 1]),
                        "errors": [str(e)],
                    },
                )

    tt = round(time.time() - t0, 1)
    ts = sum(r["success"] for r in all_res)
    tf = sum(r["failed"] for r in all_res)

    report = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "total": len(funcs),
        "done_before": len(done_names),
        "success": ts,
        "failed": tf,
        "time_s": tt,
        "batches": all_res,
    }
    (PROJECT / ".nervioso" / "refactor_v2_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
    )


if __name__ == "__main__":
    main()
