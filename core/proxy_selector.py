#!/usr/bin/env python3
"""proxy_selector.py — Cerebro de enrutamiento para el Pool Híbrido URA.

Decide, para cada target, si usar Pool Residencial (Cloudflare Worker)
o Anti-Detection (GX10 GPU + Stealth). Punto único de decisión para
todos los agentes/scrapers del sistema.

Cloudflare Worker desplegado en: https://ura-pool.barkaixo.workers.dev
"""

import re
import logging
from dataclasses import dataclass
from typing import Optional

log = logging.getLogger(__name__)

CLOUDFLARE_WORKER_URL = "https://ura-pool.barkaixo.workers.dev"


@dataclass
class RouteDecision:
    target: str
    mode: str
    priority: str
    node: str
    proxy: Optional[str]
    fingerprint: str
    stealth: bool
    reason: str

    def to_dict(self) -> dict:
        return {
            "target": self.target,
            "mode": self.mode,
            "priority": self.priority,
            "node": self.node,
            "proxy": self.proxy,
            "fingerprint": self.fingerprint,
            "stealth": self.stealth,
            "reason": self.reason,
        }


@dataclass
class TargetRule:
    mode: str
    priority: str
    node: str
    fingerprint: str = "generic"
    stealth: bool = False
    proxy: Optional[str] = None


TARGET_RULES: dict[re.Pattern, TargetRule] = {
    re.compile(r"(^|\.)pinterest\.(com|es|fr|de|it)$"): TargetRule(
        mode="pool", priority="speed", node="hetzner",
        stealth=False, proxy=f"{CLOUDFLARE_WORKER_URL}/proxy?url=",
    ),
    re.compile(r"(^|\.)bing\.com$"): TargetRule(
        mode="pool", priority="speed", node="hetzner",
        stealth=False, proxy=f"{CLOUDFLARE_WORKER_URL}/proxy?url=",
    ),
    re.compile(r"(^|\.)fontsinuse\.com$"): TargetRule(
        mode="pool", priority="speed", node="hetzner",
        stealth=False, proxy=f"{CLOUDFLARE_WORKER_URL}/proxy?url=",
    ),
    re.compile(r"(^|\.)google\.(com|es|fr|de|it)$"): TargetRule(
        mode="pool", priority="volume", node="hetzner",
        stealth=False, proxy=f"{CLOUDFLARE_WORKER_URL}/proxy?url=",
    ),
    re.compile(r"(^|\.)behance\.net$"): TargetRule(
        mode="stealth", priority="quality", node="gx10",
        fingerprint="chrome_124_win", stealth=True,
    ),
    re.compile(r"(^|\.)youtube\.com$"): TargetRule(
        mode="stealth", priority="persistence", node="gx10",
        fingerprint="chrome_124_win", stealth=True,
    ),
    re.compile(r"(^|\.)dribbble\.com$"): TargetRule(
        mode="stealth", priority="quality", node="gx10",
        fingerprint="chrome_124_mac", stealth=True,
    ),
    re.compile(r"(^|\.)noona\.app$"): TargetRule(
        mode="stealth", priority="security", node="gx10",
        fingerprint="chrome_124_win", stealth=True,
    ),
}

FALLBACK_RULE = TargetRule(
    mode="pool", priority="standard", node="hetzner",
    stealth=False, proxy=f"{CLOUDFLARE_WORKER_URL}/proxy?url=",
)


def get_best_path(target: str, context: Optional[dict] = None) -> RouteDecision:
    context = context or {}
    domain = _extract_domain(target)
    rule = _match_rule(domain)

    mode_override = context.get("mode_override")
    if mode_override in ("pool", "stealth"):
        rule = TargetRule(
            mode=mode_override,
            priority=rule.priority,
            node="hetzner" if mode_override == "pool" else "gx10",
            fingerprint=rule.fingerprint,
            stealth=(mode_override == "stealth"),
            proxy=rule.proxy,
        )

    return RouteDecision(
        target=domain,
        mode=rule.mode,
        priority=rule.priority,
        node=rule.node,
        proxy=rule.proxy,
        fingerprint=rule.fingerprint,
        stealth=rule.stealth,
        reason=f"target={domain} -> mode:{rule.mode} node:{rule.node}",
    )


def _extract_domain(target: str) -> str:
    target = target.strip().lower()
    target = re.sub(r"^https?://", "", target)
    target = target.split("/")[0]
    target = target.split("?")[0]
    target = target.split(":")[0]
    return target


def _match_rule(domain: str) -> TargetRule:
    for pattern, rule in TARGET_RULES.items():
        if pattern.search(domain):
            return rule
    log.debug("No matching rule for %s, using fallback", domain)
    return FALLBACK_RULE


def evaluate(target: str, context: Optional[dict] = None) -> str:
    return get_best_path(target, context).mode


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    for t in [
        "https://pinterest.com/pin/123",
        "bing.com/search?q=test",
        "behance.net/gallery/123",
        "fontsinuse.com/uses/456",
        "youtube.com/watch?v=abc",
        "noona.app/login",
        "unknown-site.com",
    ]:
        d = get_best_path(t)
        print(f"{t:50s} -> {d.mode:8s} | {d.node:8s} | proxy={d.proxy or 'none'}")
