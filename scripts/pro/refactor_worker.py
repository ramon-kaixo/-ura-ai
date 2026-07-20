"""RefactorWorker — worker individual de refactorización.

Ejecuta refactor_large_functions_v2.py con un ID de worker.
Puede ejecutarse como proceso independiente.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


class RefactorWorker:
    """Worker individual que ejecuta refactorización sobre un lote de archivos."""

    def __init__(
        self,
        worker_id: int,
        total_workers: int = 4,
        model: str = "qwen2.5-coder:14b",
        threshold: int = 80,
        max_tokens: int = 6500,
        overhead: int = 800,
        ura_root: str = "",
        venv_python: str = "",
    ) -> None:
        self.worker_id = worker_id
        self.total_workers = total_workers
        self.model = model
        self.threshold = threshold
        self.max_tokens = max_tokens
        self.overhead = overhead
        self.ura_root = ura_root or str(Path.home() / "URA" / "ura_ia_1972")
        self.venv_python = venv_python or str(Path(self.ura_root) / ".venv" / "bin" / "python3")

    def run(self, timeout: int = 3600) -> subprocess.CompletedProcess:
        """Ejecuta el worker de refactorización."""
        env = os.environ.copy()
        env.update(
            {
                "REFACTOR_WORKER_ID": str(self.worker_id),
                "REFACTOR_WORKER_TOTAL": str(self.total_workers),
                "REFACTOR_MODEL": self.model,
                "MONSTER_THRESHOLD": str(self.threshold),
                "MAX_BATCH_TOKENS": str(self.max_tokens),
                "PROMPT_OVERHEAD_TOKENS": str(self.overhead),
                "URA_ROOT": self.ura_root,
            }
        )
        return subprocess.run(
            [self.venv_python, "-u", "scripts/pro/refactor_large_functions_v2.py"],
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            cwd=self.ura_root,
        )


def main() -> None:
    """Punto de entrada para ejecución como proceso independiente."""
    import argparse  # noqa: PLC0415

    parser = argparse.ArgumentParser(description="RefactorWorker")
    parser.add_argument("--id", type=int, default=1, dest="worker_id")
    parser.add_argument("--total", type=int, default=4)
    parser.add_argument("--model", default="qwen2.5-coder:14b")
    parser.add_argument("--timeout", type=int, default=3600)
    args = parser.parse_args()

    worker = RefactorWorker(
        worker_id=args.worker_id,
        total_workers=args.total,
        model=args.model,
    )
    result = worker.run(timeout=args.timeout)
    print(result.stdout[-500:] if result.stdout else "")
    print(result.stderr[-200:] if result.stderr else "", file=sys.stderr)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
