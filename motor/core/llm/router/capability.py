"""Capability-based provider selection."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from motor.core.llm.registry import ProviderRegistry

log = logging.getLogger(__name__)


def find_providers_by_capability(
    capability: str,
    registry: ProviderRegistry,
) -> list[str]:
    result: list[str] = []
    for name in registry.list():
        try:
            prov = registry.get(name)
            if prov.supports(capability):
                result.append(name)
        except Exception:
            log.debug("find_providers_by_capability: error checking %s", name)
            continue
    return result


def select_provider_by_capability(
    capability: str,
    preferred: str | None,
    registry: ProviderRegistry,
) -> str:
    if preferred:
        try:
            prov = registry.get(preferred)
            if prov.supports(capability):
                return preferred
        except (KeyError, Exception):
            log.debug("preferred provider %s not available for %s", preferred, capability)

    capable = find_providers_by_capability(capability, registry)
    if capable:
        return capable[0]

    msg = f"No provider supports capability '{capability}'. Available: {list(registry.list())}"
    raise RuntimeError(msg)
