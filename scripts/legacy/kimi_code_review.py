#!/usr/bin/env python3
"""
kimi_code_review.py — Revisión de código con Kimi-Dev-72B desde el Mac.
Envía archivos Python al GX10 (puerto 8088) para revisión con Kimi-Dev.

Uso:
    python3 kimi_code_review.py [--dir ~/URA] [--max-lines 800]
"""

import argparse
import json
import os
import re
import time
import urllib.request
from pathlib import Path

API_URL = "http://gx10-ts:8088/v1/chat/completions"
MODEL_NAME = "kimi-dev"
MAX_LINES_PER_CHUNK = 800
MAX_TOKENS_RESPONSE = 1500
REQUEST_TIMEOUT = 300
DELAY_BETWEEN = 3

SYSTEM_PROMPT = (
    "Eres un revisor de codigo senior. Analiza este codigo Python y reporta:\n"
    "1. Bugs o errores logicos\n"
    "2. Problemas de seguridad\n"
    "3. Problemas de rendimiento\n"
    "4. Codigo muerto o no usado\n"
    "5. Violaciones de estilo (PEP8)\n"
    "Se conciso. Si no hay problemas, di 'OK'.\n"
)


def find_function_breaks(lines: list[str]) -> list[int]:
    breaks = []
    for i, line in enumerate(lines):
        stripped = line.lstrip()
        if re.match(r"^(def |class |async def )", stripped):
            if not line.startswith((" ", "\t")):
                breaks.append(i)
    return breaks


def split_by_functions(
    filepath: Path, max_lines: int = MAX_LINES_PER_CHUNK
) -> list[tuple[int, int, str]]:
    lines = filepath.read_text(encoding="utf-8", errors="replace").split("\n")
    total = len(lines)

    if total <= max_lines:
        return [(1, total, "\n".join(lines))]

    breaks = find_function_breaks(lines)
    chunks = []
    start = 0

    for brk in breaks:
        chunk_size = brk - start
        if chunk_size >= max_lines * 0.5:
            chunk_text = "\n".join(lines[start:brk])
            chunks.append((start + 1, brk, chunk_text))
            start = brk

    remaining = "\n".join(lines[start:])
    if remaining.strip():
        chunks.append((start + 1, total, remaining))

    merged = []
    current_lines = []
    current_start = None

    for start_line, end_line, text in chunks:
        chunk_lines = text.split("\n")
        if current_start is None:
            current_start = start_line
        current_lines.extend(chunk_lines)

        if len(current_lines) >= max_lines:
            merged.append(
                (current_start, start_line + len(chunk_lines) - 1, "\n".join(current_lines))
            )
            current_lines = []
            current_start = None

    if current_lines:
        merged.append((current_start, total, "\n".join(current_lines)))

    return merged if merged else [(1, total, "\n".join(lines))]


def send_review(code: str, filename: str, start: int, end: int) -> dict:
    prompt = f"Archivo: {filename} (lineas {start}-{end})\n\n```python\n{code[:30000]}\n```"

    payload = json.dumps(
        {
            "model": MODEL_NAME,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": MAX_TOKENS_RESPONSE,
            "temperature": 0.2,
        }
    ).encode("utf-8")

    req = urllib.request.Request(
        API_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:  # nosec B310
            data = json.loads(resp.read())
            content = data["choices"][0]["message"]["content"]
            tokens = data.get("usage", {}).get("total_tokens", 0)
            return {
                "ok": True,
                "content": content,
                "tokens": tokens,
                "filename": filename,
                "lines": f"{start}-{end}",
            }
    except Exception as e:
        return {"ok": False, "error": str(e), "filename": filename, "lines": f"{start}-{end}"}


def review_directory(root_dir: str, output_path: str, max_lines: int) -> dict:
    root = Path(root_dir)
    py_files = sorted(
        [
            f
            for f in root.rglob("*.py")
            if ".venv" not in str(f)
            and "__pycache__" not in str(f)
            and "archive" not in str(f)
            and "backup" not in str(f)
            and "node_modules" not in str(f)
        ]
    )

    stats = {"total_files": len(py_files), "total_chunks": 0, "reviewed": 0, "errors": 0}

    print("=== Kimi Code Review ===")
    print(f"Directorio: {root_dir}")
    print(f"Archivos Python: {len(py_files)}")
    print(f"Max lineas por bloque: {max_lines}")
    print(f"Output: {output_path}")
    print()

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    header = f"# Kimi-Dev Code Review — {time.strftime('%Y-%m-%d %H:%M')}\n\n"
    out.write_text(header, encoding="utf-8")

    for i, filepath in enumerate(py_files, 1):
        try:
            size_kb = filepath.stat().st_size / 1024
            chunks = split_by_functions(filepath, max_lines)
            stats["total_chunks"] += len(chunks)

            rel = filepath.relative_to(root)
            status = f"[{i}/{len(py_files)}] {rel} ({size_kb:.0f}KB, {len(chunks)} bloques)"
            print(status)

            with open(output_path, "a", encoding="utf-8") as outf:
                outf.write(f"\n## {rel}\n\n")

            for start, end, code in chunks:
                result = send_review(code, str(rel), start, end)

                with open(output_path, "a", encoding="utf-8") as outf:
                    if result["ok"]:
                        outf.write(f"### L{start}-{end}\n\n{result['content']}\n\n")
                        stats["reviewed"] += 1
                    else:
                        outf.write(f"### L{start}-{end} — ERROR: {result['error']}\n\n")
                        stats["errors"] += 1

                time.sleep(DELAY_BETWEEN)

        except Exception as e:
            print(f"  ERROR: {e}")

    summary = (
        f"\n---\nReview completada. {stats['reviewed']} bloques OK, {stats['errors']} errores.\n"
    )
    with open(output_path, "a", encoding="utf-8") as outf:
        outf.write(summary)

    return stats


def main():
    parser = argparse.ArgumentParser(description="Kimi-Dev Code Review (desde Mac)")
    parser.add_argument(
        "--dir", default=os.path.expanduser("~/URA/ura_ia_1972"), help="Directorio a revisar"
    )
    parser.add_argument(
        "--max-lines", type=int, default=MAX_LINES_PER_CHUNK, help="Max lineas por bloque"
    )
    parser.add_argument("--output", default="", help="Archivo de salida (default: auto)")
    args = parser.parse_args()

    ts = time.strftime("%Y%m%d_%H%M")
    output = args.output or os.path.expanduser(f"~/URA/ura_ia_1972/logs/kimi_review_{ts}.md")

    stats = review_directory(args.dir, output, args.max_lines)

    print()
    print("=== Completado ===")
    print(f"  {stats['reviewed']} bloques OK, {stats['errors']} errores")
    print(f"  Resultado: {output}")


if __name__ == "__main__":
    main()
