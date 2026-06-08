#!/usr/bin/env python3
"""proxy_selector.py — Routing engine for URA hybrid proxy pool.

Loads target rules from config/target_rules.json (external config).
"""

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).parent.parent / "config" / "target_rules.json"
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


def _load_rules() -> tuple[list[tuple[re.Pattern, dict]], dict]:
    """Load rules from JSON config, return (rules, fallback)."""
    try:
        data = json.loads(CONFIG_PATH.read_text())
    except (FileNotFoundError, json.JSONDecodeError) as e:
        log.warning("Cannot load %s: %s. Using built-in defaults.", CONFIG_PATH, e)
        data = _default_config()

    rules = []
    for r in data.get("rules", []):
        try:
            rules.append((re.compile(r["pattern"]), r))
        except re.error as e:
            log.warning("Bad regex in rule %s: %s", r.get("pattern"), e)

    fallback = data.get("fallback", {})
    return rules, fallback


def _default_config() -> dict:
    """Hardcoded fallback if JSON is unavailable."""
    return {
        "cloudflare_worker": "https://ura-pool.barkaixo.workers.dev",
        "rules": [
            {"pattern": r"(^|\.)pinterest\.(com|es|fr|de|it)$", "mode": "pool", "priority": "speed", "node": "hetzner", "stealth": False, "fingerprint": "generic"},
            {"pattern": r"(^|\.)bing\.com$", "mode": "pool", "priority": "speed", "node": "hetzner", "stealth": False, "fingerprint": "generic"},
            {"pattern": r"(^|\.)fontsinuse\.com$", "mode": "pool", "priority": "speed", "node": "hetzner", "stealth": False, "fingerprint": "generic"},
            {"pattern": r"(^|\.)google\.(com|es|fr|de|it)$", "mode": "pool", "priority": "volume", "node": "hetzner", "stealth": False, "fingerprint": "generic"},
            {"pattern": r"(^|\.)behance\.net$", "mode": "stealth", "priority": "quality", "node": "gx10", "stealth": True, "fingerprint": "chrome_124_win"},
            {"pattern": r"(^|\.)youtube\.com$", "mode": "stealth", "priority": "persistence", "node": "gx10", "stealth": True, "fingerprint": "chrome_124_win"},
            {"pattern": r"(^|\.)dribbble\.com$", "mode": "stealth", "priority": "quality", "node": "gx10", "stealth": True, "fingerprint": "chrome_124_mac"},
            {"pattern": r"(^|\.)noona\.app$", "mode": "stealth", "priority": "security", "node": "gx10", "stealth": True, "fingerprint": "chrome_124_win"},
        ],
        "fallback": {"mode": "pool", "priority": "standard", "node": "hetzner", "stealth": False, "fingerprint": "generic"},
    }


# Load once at import time
_RULES, _FALLBACK = _load_rules()


def get_best_path(target: str, context: Optional[dict] = None) -> RouteDecision:
    context = context or {}
    domain = _extract_domain(target)
    rule = _match_rule(domain)

    mode_override = context.get("mode_override")
    if mode_override in ("pool", "stealth"):
        rule = dict(rule)
        rule["mode"] = mode_override
        rule["node"] = "hetzner" if mode_override == "pool" else "gx10"
        rule["stealth"] = (mode_override == "stealth")

    proxy = None if rule["mode"] == "stealth" else f"{CLOUDFLARE_WORKER_URL}/proxy?url="

    return RouteDecision(
        target=domain,
        mode=rule["mode"],
        priority=rule.get("priority", "standard"),
        node=rule["node"],
        proxy=proxy,
        fingerprint=rule.get("fingerprint", "generic"),
        stealth=rule.get("stealth", False),
        reason=f"target={domain} -> mode:{rule['mode']} node:{rule['node']}",
    )


def _extract_domain(target: str) -> str:
    target = target.strip().lower()
    target = re.sub(r"^https?://", "", target)
    target = target.split("/")[0]
    target = target.split("?")[0]
    target = target.split(":")[0]
    return target


def _match_rule(domain: str) -> dict:
    for pattern, rule in _RULES:
        if pattern.search(domain):
            return rule
    log.debug("No matching rule for %s, using fallback", domain)
    return _FALLBACK


def evaluate(target: str, context: Optional[dict] = None) -> str:
    return get_best_path(target, context).mode


def list_rules() -> list[dict]:
    result = []
    for pattern, rule in _RULES:
        result.append({"pattern": pattern.pattern, "rule": rule})
    result.append({"pattern": "* (fallback)", "rule": _FALLBACK})
    return result


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
        print(f"{t:40s} -> {d.mode:8s} | {d.node:8s} | {d.fingerprint:20s} | {d.priority}")
