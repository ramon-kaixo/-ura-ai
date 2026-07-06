from __future__ import annotations

import logging
from collections.abc import Callable  # noqa: TC003  -- usado solo en type hints, con annotations future
from typing import TYPE_CHECKING, Any

from motor.events.topics import (
    ALL_HOOKS,
    HOOK_PREFIX,
)

if TYPE_CHECKING:
    from motor.core.state import DegradedMode
    from motor.events.bus import EventBus
    from motor.events.event import Event
    from motor.plugin.base import PluginBase

log = logging.getLogger("ura.hooks")

HOOK_MAX_ERRORS = 3


class HookManager:
    def __init__(self, eventbus: EventBus, degraded_mode: DegradedMode) -> None:
        self._bus = eventbus
        self._dm = degraded_mode
        self._error_counts: dict[str, int] = {}
        self._subscription_ids: dict[str, str] = {}

    def register_plugin_hooks(self, plugin_name: str, plugin: PluginBase) -> None:
        manifest = getattr(plugin, "manifest", None)
        hook_names = getattr(manifest, "hooks", None) or []
        for hook_name in hook_names:
            if hook_name not in ALL_HOOKS:
                log.warning("[hooks] %s: hook desconocido '%s' — ignorado", plugin_name, hook_name)
                continue
            method_name = f"on_{hook_name}"
            method: Callable[[Event], Any] | None = getattr(plugin, method_name, None)
            if method is None:
                log.warning("[hooks] %s: declara hook '%s' pero no implementa %s", plugin_name, hook_name, method_name)
                continue
            wrapped = self._wrap(plugin_name, hook_name, method)
            topic = f"{HOOK_PREFIX}{hook_name}"
            sub_id = self._bus.subscribe(topic, wrapped, priority=0)
            key = f"{plugin_name}:{hook_name}"
            self._subscription_ids[key] = sub_id
            log.info("[hooks] %s registrado en %s", key, topic)

    def unregister_plugin_hooks(self, plugin_name: str) -> None:
        for key, sub_id in list(self._subscription_ids.items()):
            if key.startswith(f"{plugin_name}:"):
                self._bus.unsubscribe(sub_id)
                del self._subscription_ids[key]

    def _wrap(self, plugin_name: str, hook_name: str, method: Callable) -> Callable:
        key = f"{plugin_name}:{hook_name}"

        def wrapper(event: Event) -> Any:
            if self._error_counts.get(key, 0) >= HOOK_MAX_ERRORS:
                log.warning("[hooks] %s excedió %d errores — omitido", key, HOOK_MAX_ERRORS)
                return None
            try:
                result = method(event)
                self._error_counts[key] = 0
                self._dm.mark_healthy(f"hook:{key}")
                return result
            except Exception as exc:
                count = self._error_counts.get(key, 0) + 1
                self._error_counts[key] = count
                self._dm.mark_degraded(f"hook:{key}")
                if count >= HOOK_MAX_ERRORS:
                    sub_id = self._subscription_ids.get(key)
                    if sub_id:
                        self._bus.unsubscribe(sub_id)
                        log.warning("[hooks] %s desuscrito tras %d errores: %s", key, count, exc)
                else:
                    log.warning("[hooks] %s error %d/%d: %s", key, count, HOOK_MAX_ERRORS, exc)
                return None

        return wrapper
