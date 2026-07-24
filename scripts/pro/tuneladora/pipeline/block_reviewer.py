from __future__ import annotations

import logging
import subprocess
import threading
import time
from pathlib import Path

import requests

from scripts.pro.tuneladora.config import Configuration

log = logging.getLogger("tuneladora.block_reviewer")

REVIEW_PROMPT = """Eres un revisor de código senior. Revisa el siguiente diff:

{diff}

Tests existentes:
{tests}

API diff:
{api_diff}

Genera un reporte en formato markdown con:
- Cambios de comportamiento detectados
- Tests que NO cubren el cambio
- Recomendaciones"""


def review_block(
    cfg: Configuration,
    block_name: str,
    head: str = "",
    tests: list[str] | None = None,
    api_diff: str = "",
) -> None:
    thread = threading.Thread(target=_do_review, args=(cfg, block_name, head, tests or [], api_diff), daemon=True)
    thread.start()
    log.info("Review thread started for block '%s'", block_name)


def _do_review(
    cfg: Configuration,
    block_name: str,
    head: str,
    tests: list[str],
    api_diff: str,
) -> None:
    reviews_dir = cfg.tuneladora_dir / "reviews"
    reviews_dir.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    report_path = reviews_dir / f"block_{block_name}_{ts}.md"

    diff = _get_diff(cfg.ura_root, head)
    tests_str = "\n".join(tests) if tests else "(none)"

    prompt = REVIEW_PROMPT.format(diff=diff, tests=tests_str, api_diff=api_diff)

    report = f"# Revisión bloque {block_name}\n\n"
    try:
        r = requests.post(
            f"{cfg.ollama_url}/api/generate",
            json={"model": cfg.review_model, "prompt": prompt, "stream": False},
            timeout=cfg.timeout_llm,
        )
        r.raise_for_status()
        response = r.json().get("response", "")
        report += response
    except Exception as e:
        report += f"\nError generating review: {e}\n"
        log.warning("Review LLM call failed: %s", e)

    report_path.write_text(report)
    log.info("Review saved: %s", report_path)


def _get_diff(repo_root: Path, head: str = "") -> str:
    try:
        if head:
            r = subprocess.run(
                ["git", "diff", f"HEAD..{head}"],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
                cwd=str(repo_root),
            )
        else:
            r = subprocess.run(
                ["git", "diff", "HEAD"],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
                cwd=str(repo_root),
            )
        return r.stdout[:5000] if r.stdout else "(no diff)"
    except Exception as e:
        return f"(error: {e})"
