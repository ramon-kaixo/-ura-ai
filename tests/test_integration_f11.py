from __future__ import annotations

from typing import TYPE_CHECKING

from motor.core.state import DegradedMode
from motor.events.bus import EventBus
from motor.events.compat import check_api_compatibility, check_plugin_dependency
from motor.events.event import EventPayload
from motor.events.hooks import HookManager
from motor.events.topics import HOOK_PREFIX
from motor.plugin.registry_v2 import PluginRegistryV2

if TYPE_CHECKING:
    from pathlib import Path


def _make_plugin_with_hooks(base: Path, name: str, hook_names: list[str]) -> Path:
    d = base / name
    d.mkdir()
    yaml_lines = [
        f"name: {name}",
        "version: '1.0.0'",
        "api_version: '1.0.0'",
        "entry_point: 'MyPlugin'",
    ]
    if hook_names:
        yaml_lines.append("hooks:")
        for h in hook_names:
            yaml_lines.append(f"  - {h}")
    (d / "plugin.yaml").write_text("\n".join(yaml_lines) + "\n")
    hook_impl = ""
    for h in hook_names:
        hook_impl += f"    def on_{h}(self, event):\n        self.{h}_calls += 1\n        return event\n"
    init_content = (
        "from motor.plugin.base import PluginBase\n"
        "class MyPlugin(PluginBase):\n"
        f"    def __init__(self):\n"
        f"        super().__init__()\n"
        f"        self.pre_ingest_calls = 0\n"
        f"        self.post_search_calls = 0\n"
        f"        self.pre_search_calls = 0\n"
        f"    def execute(self, context):\n"
        f"        return {{'name': '{name}'}}\n" + hook_impl
    )
    (d / "__init__.py").write_text(init_content)
    return d


class TestEventBusCompat:
    def test_api_compatibility_ok(self):
        assert check_api_compatibility("1.0.0", "1.0.0") is True
        assert check_api_compatibility("1.0.0", "1.1.0") is True
        assert check_api_compatibility("1.5.0", "1.0.0") is False

    def test_api_compatibility_legacy(self):
        assert check_api_compatibility("", "1.0.0", allow_legacy=True) is True

    def test_plugin_dependency_exact(self):
        assert check_plugin_dependency("dep", "==1.0.0", "1.0.0") is True
        assert check_plugin_dependency("dep", "==1.0.0", "1.0.1") is False

    def test_plugin_dependency_range(self):
        assert check_plugin_dependency("dep", ">=1.0.0", "1.5.0") is True
        assert check_plugin_dependency("dep", ">=2.0.0", "1.5.0") is False
        assert check_plugin_dependency("dep", ">=1.0.0 <2.0.0", "1.5.0") is True
        assert check_plugin_dependency("dep", ">=1.0.0 <2.0.0", "2.0.0") is False


class TestIntegrationEventBusHookManager:
    def test_hook_integration(self, tmp_path: Path):
        bus = EventBus()
        dm = DegradedMode.instancia()
        hm = HookManager(bus, dm)
        registry = PluginRegistryV2(eventbus=bus, hook_manager=hm)
        _make_plugin_with_hooks(tmp_path, "hook_integration", ["pre_ingest"])
        registry.discover([str(tmp_path)])
        registry.get("hook_integration")
        responses = bus.emit_sync(f"{HOOK_PREFIX}pre_ingest", EventPayload())
        assert len(responses) >= 1


class TestIntegrationEventBusDegradedMode:
    def test_degraded_mode_after_bad_hook(self, tmp_path: Path):
        bus = EventBus()
        dm = DegradedMode()
        hm = HookManager(bus, dm)
        registry = PluginRegistryV2(eventbus=bus, hook_manager=hm)

        d = tmp_path / "bad_hook_plugin"
        d.mkdir()
        (d / "plugin.yaml").write_text(
            "name: bad_hook\nversion: '1.0.0'\napi_version: '1.0.0'\nentry_point: 'MyPlugin'\nhooks:\n  - pre_ingest\n",
        )
        init_content = (
            "from motor.plugin.base import PluginBase\n"
            "class MyPlugin(PluginBase):\n"
            "    def execute(self, context):\n"
            "        return {}\n"
            "    def on_pre_ingest(self, event):\n"
            "        raise RuntimeError('bad hook')\n"
        )
        (d / "__init__.py").write_text(init_content)

        registry.discover([str(tmp_path)])
        registry.get("bad_hook")
        bus.emit_sync(f"{HOOK_PREFIX}pre_ingest", EventPayload())
        assert dm.is_degraded("hook:bad_hook:pre_ingest")
        dm.mark_healthy("hook:bad_hook:pre_ingest")


class TestIntegrationRegistryWithExecutor:
    def test_registry_plugin_uses_executor(self, tmp_path: Path):
        registry = PluginRegistryV2()
        d = tmp_path / "exec_plugin"
        d.mkdir()
        (d / "plugin.yaml").write_text(
            "name: exec_plugin\nversion: '1.0.0'\napi_version: '1.0.0'\nentry_point: 'MyPlugin'\n",
        )
        (d / "__init__.py").write_text(
            "from motor.plugin.base import PluginBase\n"
            "from motor.core.executor import SubprocessExecutor\n"
            "class MyPlugin(PluginBase):\n"
            "    def execute(self, context):\n"
            "        exe = SubprocessExecutor()\n"
            "        r = exe.run(['echo', 'hello_from_plugin'])\n"
            "        return {'stdout': r.stdout.strip()}\n",
        )
        registry.discover([str(tmp_path)])
        results = registry.run_phase("always")
        assert len(results) == 1
        assert results[0].ok is True
        assert results[0].data["stdout"] == "hello_from_plugin"


class TestIntegrationFullCycle:
    def test_full_cycle(self, tmp_path: Path):
        bus = EventBus()
        dm = DegradedMode.instancia()
        hm = HookManager(bus, dm)
        registry = PluginRegistryV2(eventbus=bus, hook_manager=hm)

        _make_plugin_with_hooks(tmp_path, "full_cycle", ["pre_ingest"])
        registry.discover([str(tmp_path)])

        assert registry.count() == 1
        assert not dm.is_degraded("plugin:full_cycle")

        plugin = registry.get("full_cycle")
        assert plugin is not None
        assert "full_cycle" in registry.loaded

        results = registry.run_phase("always")
        assert len(results) == 1
        assert results[0].ok is True

        responses = bus.emit_sync(f"{HOOK_PREFIX}pre_ingest", EventPayload())
        assert len(responses) == 1

        registry.unload("full_cycle")
        assert "full_cycle" not in registry.loaded

        responses2 = bus.emit_sync(f"{HOOK_PREFIX}pre_ingest", EventPayload())
        assert len(responses2) == 0  # hook unsubscribed
