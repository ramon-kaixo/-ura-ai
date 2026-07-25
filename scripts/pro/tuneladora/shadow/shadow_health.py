"""Shadow Health — orquestador multi-capa de health checks para el pipeline."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import logging
import subprocess
import sys
import time
from dataclasses import dataclass, field
from typing import Any

from scripts.pro.tuneladora.config import Configuration
from scripts.pro.tuneladora.memory.short_term import ShortTermMemory
from scripts.pro.tuneladora.shadow.layer0_env import run as run_layer0
from scripts.pro.tuneladora.shadow.layer3_shadow import run as run_layer3

log = logging.getLogger("shadow.health")


@dataclass
class LayerResult:
    layer: int
    name: str
    status: str
    checks: list[Any] = field(default_factory=list)
    duration_ms: float = 0.0
    error: str = ""

ROLLBACK_RULES: dict[int, str] = {
    0: "none",
    1: "full",
    2: "full",
    3: "none",
    4: "full",
    5: "none",
    6: "none",
    7: "full",
}


class ShadowHealth:
    def __init__(self, cfg: Configuration, layers: list[int] | None = None, fail_fast: bool = True) -> None:
        self.cfg = cfg
        self.layers = layers or list(range(8))
        self.fail_fast = fail_fast
        self.cache = ShortTermMemory(max_size=100, default_ttl=300.0)
        self._results: list[LayerResult] = []
        self._start = 0.0
        self._diff_hash: str = ""
        self._diff_files: list[str] = []
        self._duration_ms: float = 0.0
        self._runner: Any = None
        self._ensure_diff_cache()

    def _ensure_diff_cache(self) -> None:
        try:
            r = subprocess.run(
                ["git", "diff", "--name-only", "HEAD"], capture_output=True, text=True,
                timeout=10, check=False, cwd=str(self.cfg.ura_root),
            )
            self._diff_files = [
                f.strip() for f in (r.stdout or "").split("\n")
                if f.strip().endswith(".py")
            ]
            r2 = subprocess.run(
                ["git", "rev-parse", "HEAD"], capture_output=True, text=True,
                timeout=5, check=False, cwd=str(self.cfg.ura_root),
            )
            head = r2.stdout.strip() if r2.returncode == 0 else ""
            content = r.stdout or ""
            self._diff_hash = hashlib.md5(
                f"{head}:{content}".encode(), usedforsecurity=False
            ).hexdigest()[:12]
        except Exception as exc:
            log.debug("git diff cache failed: %s", exc)
            self._diff_files = []
            self._diff_hash = ""

    def _cache_key(self, layer: int) -> str:
        return f"shadow_l{layer}:{self._diff_hash}"

    def _get_or_create_runner(self):
        if self._runner is None:
            from scripts.pro.tuneladora.pipeline.runner import PipelineRunner
            self._runner = PipelineRunner(self.cfg, mode="check", files=self._diff_files)
        return self._runner

    def _verdict(self) -> str:
        for v in ("ABORT", "FAIL", "WARN"):
            if any(r.status == v for r in self._results):
                return v
        return "OK"

    def _should_rollback(self) -> bool:
        for r in self._results:
            rule = ROLLBACK_RULES.get(r.layer, "none")
            if r.status in ("FAIL", "ABORT") and rule == "full":
                return True
        return False

    def run_layer(self, layer: int) -> LayerResult:
        t0 = time.monotonic()
        cache_key = self._cache_key(layer)
        cached = self.cache.get(cache_key)
        if cached is not None:
            return copy.deepcopy(cached)

        handlers = {
            0: self._layer0_env,
            1: self._layer1_static,
            2: self._layer2_runtime,
            3: self._layer3_shadow,
            4: self._layer4_chaos,
            5: self._layer5_regression,
            6: self._layer6_trend,
            7: self._layer7_promotion,
        }
        handler = handlers.get(layer)
        if handler is None:
            return LayerResult(layer, f"layer{layer}", "SKIP", error="Unknown layer")

        try:
            result = handler()
            result.duration_ms = (time.monotonic() - t0) * 1000
            if result.status == "OK":
                self.cache.set(cache_key, copy.deepcopy(result))
            return result
        except Exception as e:
            log.error("Layer %d failed: %s", layer, e)
            result = LayerResult(layer, f"layer{layer}", "FAIL", error=str(e))
            result.duration_ms = (time.monotonic() - t0) * 1000
            return result

    def run_all(self) -> list[LayerResult]:
        self._start = time.monotonic()
        self._results = []
        fail_layers = {0, 1, 2} if self.fail_fast else set()
        for layer in sorted(self.layers):
            if layer < 0 or layer > 7:
                log.warning("Skipping invalid layer %d", layer)
                continue
            lr = self.run_layer(layer)
            self._results.append(lr)
            log.info("Layer %d (%s): %s in %.0fms", layer, lr.name, lr.status, lr.duration_ms)
            if self.fail_fast and layer in fail_layers and lr.status in ("FAIL", "ABORT"):
                remaining = [l for l in self.layers if l > layer]
                log.warning("Layer %d failed (%s) — aborting remaining: %s", layer, lr.status, remaining)
                break
        self._duration_ms = (time.monotonic() - self._start) * 1000
        return self._results

    def render_json(self) -> str:
        return json.dumps({
            "verdict": self._verdict(),
            "rollback": self._should_rollback(),
            "duration_ms": self._duration_ms,
            "layers": [
                {"layer": r.layer, "name": r.name, "status": r.status,
                 "duration_ms": r.duration_ms, "error": r.error}
                for r in self._results
            ],
        }, indent=2, ensure_ascii=False)

    def render_text(self) -> str:
        lines = [f"Shadow Health — {self._verdict()}"]
        lines.append(f"Duration: {self._duration_ms:.0f}ms")
        lines.append("")
        for r in self._results:
            icon = {"OK": "✓", "WARN": "⚠", "FAIL": "✗", "SKIP": "→", "ABORT": "■"}
            lines.append(f"  {icon.get(r.status, '?')} Layer {r.layer} ({r.name}): {r.status}")
            if r.error:
                lines.append(f"     {r.error}")
        lines.append("")
        if self._should_rollback():
            lines.append("  → Rollback required")
        return "\n".join(lines)

    def _layer0_env(self) -> LayerResult:
        checks = run_layer0(self.cfg.ura_root, self.cfg.ollama_url)
        status = "FAIL" if any(c.status == "FAIL" for c in checks) else \
                 "WARN" if any(c.status == "WARN" for c in checks) else "OK"
        return LayerResult(0, "env", status, checks=[vars(c) for c in checks])

    def _layer1_static(self) -> LayerResult:
        from scripts.pro.tuneladora.pipeline.tools.base import Status as S
        if not self._diff_files:
            return LayerResult(1, "static", "SKIP", error="No changed files")
        runner = self._get_or_create_runner()
        results = runner.phase_static()
        statuses = [r.status for r in results]
        status = "FAIL" if any(s == S.FAIL for s in statuses) else \
                 "WARN" if any(s == S.WARN for s in statuses) else "OK"
        return LayerResult(1, "static", status, checks=[vars(r) for r in results])

    def _layer2_runtime(self) -> LayerResult:
        from scripts.pro.tuneladora.pipeline.tools.base import Status as S
        if not self._diff_files:
            return LayerResult(2, "runtime", "SKIP", error="No changed files")
        runner = self._get_or_create_runner()
        results = runner.phase_dynamic()
        statuses = [r.status for r in results]
        status = "FAIL" if any(s == S.FAIL for s in statuses) else \
                 "WARN" if any(s == S.WARN for s in statuses) else "OK"
        return LayerResult(2, "runtime", status, checks=[vars(r) for r in results])

    def _layer3_shadow(self) -> LayerResult:
        if not self._diff_files:
            return LayerResult(3, "shadow", "OK", checks=[], error="No changed files")
        shadow_results = run_layer3(self._diff_files, self.cfg.ura_root)
        status = "FAIL" if any(r.status == "FAIL" for r in shadow_results) else \
                 "WARN" if any(r.status == "WARN" for r in shadow_results) else "OK"
        return LayerResult(3, "shadow", status, checks=[vars(r) for r in shadow_results])

    def _layer4_chaos(self) -> LayerResult:
        test_path = self.cfg.test_target.rstrip("/") + "/test_tuneladora_pipeline_chaos.py"
        try:
            r = subprocess.run(
                [sys.executable, "-m", "pytest", test_path,
                 "--no-cov", "-q"],
                capture_output=True, text=True, timeout=120, check=False,
                cwd=str(self.cfg.ura_root),
            )
            if r.returncode == 0:
                return LayerResult(4, "chaos", "OK", checks=[{"summary": r.stdout.strip()[:200]}])
            return LayerResult(4, "chaos", "FAIL", checks=[{"output": r.stdout[-500:], "errors": r.stderr[-500:]}])
        except subprocess.TimeoutExpired:
            return LayerResult(4, "chaos", "FAIL", error="Timeout after 120s")
        except Exception as e:
            return LayerResult(4, "chaos", "FAIL", error=str(e))

    def _layer5_regression(self) -> LayerResult:
        return LayerResult(5, "regression", "SKIP", error="Baseline data required")

    def _layer6_trend(self) -> LayerResult:
        return LayerResult(6, "trend", "SKIP", error="Historical data required")

    def _layer7_promotion(self) -> LayerResult:
        v = self._verdict()
        if v == "OK":
            return LayerResult(7, "promotion", "OK", checks=[{"action": "promote"}])
        if v == "WARN":
            return LayerResult(7, "promotion", "WARN", checks=[{"action": "promote_with_caution"}])
        return LayerResult(7, "promotion", "FAIL", checks=[{"action": "block", "reason": v}])


def main() -> None:
    parser = argparse.ArgumentParser(description="Shadow Health Checks")
    parser.add_argument("--layer", type=str, default="all",
                        help="Layers to run: 0, 1-4, all")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--no-fail-fast", action="store_true", help="Run all layers regardless")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    if args.layer == "all":
        layers = list(range(8))
    elif "-" in args.layer:
        parts = args.layer.split("-")
        layers = list(range(int(parts[0]), int(parts[1]) + 1))
    else:
        layers = [int(x) for x in args.layer.split(",")]

    cfg = Configuration()
    sh = ShadowHealth(cfg, layers=layers, fail_fast=not args.no_fail_fast)
    sh.run_all()

    if args.json:
        print(sh.render_json())
    else:
        print(sh.render_text())

    sys.exit(0 if sh._verdict() in ("OK", "WARN") else 1)


if __name__ == "__main__":
    main()
