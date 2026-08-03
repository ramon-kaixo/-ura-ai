"""Tests para motor.plugin.registry (PluginRegistry)."""
from __future__ import annotations

from pathlib import Path
from unittest import mock

from motor.plugin.base import PluginBase, PluginMeta, PluginResult
from motor.plugin.registry import PluginRegistry

PLUGIN_SRC = '''
from motor.plugin.base import PluginBase

__plugin__ = {"name": "demo_plugin", "phase": "pre"}


class DemoPlugin(PluginBase):
    def on_load(self) -> None:
        pass

    def on_unload(self) -> None:
        pass

    def execute(self, context):
        return {"ran": True, "ctx": context or {}}
'''

ALWAYS_SRC = '''
from motor.plugin.base import PluginBase

__plugin__ = {"name": "always_plugin", "phase": "always"}


class AlwaysPlugin(PluginBase):
    def on_load(self) -> None:
        pass

    def on_unload(self) -> None:
        pass

    def execute(self, context):
        return {"always": True}
'''

NO_META_SRC = '''
from motor.plugin.base import PluginBase


class BarePlugin(PluginBase):
    def on_load(self) -> None:
        pass

    def on_unload(self) -> None:
        pass

    def execute(self, context):
        return {"bare": True}
'''

NO_SUBCLASS_SRC = '''
not_a_plugin = 42
'''

BAD_IMPORT_SRC = '''
from motor.plugin.base import PluginBase

__plugin__ = {"name": "bad_plugin", "phase": "pre"}


class BadPlugin(PluginBase):
    def on_load(self) -> None:
        pass

    def on_unload(self) -> None:
        pass

    def execute(self, context):
        return {}
'''


def _write(tmp_path: Path, name: str, content: str) -> Path:
    pyfile = tmp_path / name
    pyfile.write_text(content, encoding="utf-8")
    return pyfile


def _fresh_registry() -> PluginRegistry:
    registry = PluginRegistry()
    dm = mock.Mock()
    registry._dm = dm
    return registry


class TestRegistryBasics:
    def test_empty_registry(self):
        registry = _fresh_registry()
        assert registry.entries == {}
        assert registry.loaded == []
        assert registry.count() == 0

    def test_discover_dir_and_file(self, tmp_path):
        _write(tmp_path, "demo_plugin.py", PLUGIN_SRC)
        _write(tmp_path, "always_plugin.py", ALWAYS_SRC)
        _write(tmp_path, "_private.py", PLUGIN_SRC.replace("demo_plugin", "private"))
        registry = _fresh_registry()
        assert registry.discover([tmp_path]) == 2
        assert registry.count() == 2
        assert set(registry.entries) == {"demo_plugin", "always_plugin"}

    def test_discover_single_file(self, tmp_path):
        pyfile = _write(tmp_path, "demo_plugin.py", PLUGIN_SRC)
        registry = _fresh_registry()
        assert registry.discover([pyfile]) == 1
        assert registry.entries["demo_plugin"].path == pyfile

    def test_discover_invalid_path_logs(self, tmp_path):
        registry = _fresh_registry()
        with mock.patch("motor.plugin.registry.log.warning") as warn:
            assert registry.discover([tmp_path / "no-existe"]) == 0
        warn.assert_called_once()

    def test_discover_duplicate_name_warns(self, tmp_path):
        _write(tmp_path, "a.py", PLUGIN_SRC)
        _write(tmp_path, "b.py", PLUGIN_SRC.replace("class DemoPlugin", "class DemoPlugin2"))
        registry = _fresh_registry()
        with mock.patch("motor.plugin.registry.log.warning") as warn:
            assert registry.discover([tmp_path]) == 2
        warn.assert_called_once()
        assert registry.count() == 1

    def test_discover_file_without_meta_uses_stem(self, tmp_path):
        pyfile = _write(tmp_path, "bare_plugin.py", NO_META_SRC)
        registry = _fresh_registry()
        assert registry.discover([pyfile]) == 1
        assert "bare_plugin" in registry.entries
        assert isinstance(registry.entries["bare_plugin"].meta, PluginMeta)

    def test_get_meta(self, tmp_path):
        _write(tmp_path, "demo_plugin.py", PLUGIN_SRC)
        registry = _fresh_registry()
        registry.discover([tmp_path])
        meta = registry.get_meta("demo_plugin")
        assert meta is not None
        assert meta.phase == "pre"
        assert registry.get_meta("nope") is None

    def test_count(self, tmp_path):
        _write(tmp_path, "demo_plugin.py", PLUGIN_SRC)
        registry = _fresh_registry()
        assert registry.count() == 0
        registry.discover([tmp_path])
        assert registry.count() == 1


class TestLoad:
    def test_load_success_caches(self, tmp_path):
        _write(tmp_path, "demo_plugin.py", PLUGIN_SRC)
        registry = _fresh_registry()
        registry.discover([tmp_path])
        plugin = registry.get("demo_plugin")
        assert isinstance(plugin, PluginBase)
        assert plugin is registry.get("demo_plugin")
        assert registry.loaded == ["demo_plugin"]
        registry._dm.mark_healthy.assert_called_once()

    def test_load_unknown_returns_none(self):
        registry = _fresh_registry()
        assert registry.get("nope") is None

    def test_load_spec_none_degrades(self, tmp_path):
        _write(tmp_path, "demo_plugin.py", PLUGIN_SRC)
        registry = _fresh_registry()
        registry.discover([tmp_path])
        with mock.patch(
            "motor.plugin.registry.importlib.util.spec_from_file_location", return_value=None
        ):
            assert registry.get("demo_plugin") is None
        registry._dm.mark_degraded.assert_called_once_with("plugin:demo_plugin")

    def test_load_exec_failure_degrades(self, tmp_path):
        pyfile = _write(tmp_path, "demo_plugin.py", PLUGIN_SRC)
        registry = _fresh_registry()
        registry.discover([pyfile])
        spec = mock.MagicMock()
        spec.loader.exec_module.side_effect = RuntimeError("boom")
        with mock.patch(
            "motor.plugin.registry.importlib.util.spec_from_file_location", return_value=spec
        ):
            assert registry.get("demo_plugin") is None
        registry._dm.mark_degraded.assert_called_once_with("plugin:demo_plugin")

    def test_load_no_subclass_degrades(self, tmp_path):
        pyfile = _write(tmp_path, "nope.py", NO_SUBCLASS_SRC)
        registry = _fresh_registry()
        registry.discover([pyfile])
        assert registry.get("nope") is None
        registry._dm.mark_degraded.assert_called_once_with("plugin:nope")

    def test_load_instantiation_error_falls_to_next_class(self, tmp_path):
        src = PLUGIN_SRC + '''

class BrokenPlugin(PluginBase):
    def __init__(self) -> None:
        raise RuntimeError("broken")

    def on_load(self) -> None:
        pass

    def on_unload(self) -> None:
        pass

    def execute(self, context):
        return {}
'''
        _write(tmp_path, "demo_plugin.py", src)
        registry = _fresh_registry()
        registry.discover([tmp_path])
        plugin = registry.get("demo_plugin")
        assert isinstance(plugin, PluginBase)
        assert plugin.__class__.__name__ == "DemoPlugin"


class TestRunPhase:
    def test_run_phase_filters_by_phase(self, tmp_path):
        _write(tmp_path, "demo_plugin.py", PLUGIN_SRC)
        registry = _fresh_registry()
        registry.discover([tmp_path])
        results = registry.run_phase("pre", {"x": 1})
        assert len(results) == 1
        assert results[0].ok is True
        assert results[0].plugin == "demo_plugin"
        assert results[0].data["ran"] is True
        assert results[0].data["ctx"] == {"x": 1}

    def test_run_phase_always_included(self, tmp_path):
        _write(tmp_path, "always_plugin.py", ALWAYS_SRC)
        registry = _fresh_registry()
        registry.discover([tmp_path])
        results = registry.run_phase("pre")
        assert len(results) == 1
        assert results[0].plugin == "always_plugin"

    def test_run_phase_context_none_becomes_empty(self, tmp_path):
        _write(tmp_path, "demo_plugin.py", PLUGIN_SRC)
        registry = _fresh_registry()
        registry.discover([tmp_path])
        results = registry.run_phase("pre")
        assert results[0].data["ctx"] == {}

    def test_run_phase_load_failure_result(self, tmp_path):
        _write(tmp_path, "demo_plugin.py", PLUGIN_SRC)
        registry = _fresh_registry()
        registry.discover([tmp_path])
        with mock.patch("motor.plugin.registry.PluginRegistry._load", return_value=None):
            results = registry.run_phase("pre")
        assert len(results) == 1
        assert results[0].ok is False
        assert results[0].error == "Plugin load failed"
        assert isinstance(results[0], PluginResult)

    def test_run_phase_execute_error_degrades(self, tmp_path):
        src = PLUGIN_SRC.replace('return {"ran": True', 'raise RuntimeError("exec boom")\n        return {"ran": True')
        _write(tmp_path, "demo_plugin.py", src)
        registry = _fresh_registry()
        registry.discover([tmp_path])
        results = registry.run_phase("pre")
        assert len(results) == 1
        assert results[0].ok is False
        assert results[0].error == "exec boom"
        registry._dm.mark_degraded.assert_called_once_with("plugin:demo_plugin")

    def test_run_phase_measures_duration(self, tmp_path):
        _write(tmp_path, "demo_plugin.py", PLUGIN_SRC)
        registry = _fresh_registry()
        registry.discover([tmp_path])
        with mock.patch("motor.plugin.registry.time.monotonic", side_effect=[1000.0, 1000.5]):
            results = registry.run_phase("pre")
        assert results[0].duration_ms == 500.0

    def test_run_phase_empty(self):
        registry = _fresh_registry()
        assert registry.run_phase("pre") == []


class TestRunOne:
    def test_run_one_unknown_returns_none(self):
        registry = _fresh_registry()
        assert registry.run_one("nope") is None

    def test_run_one_executes_target(self, tmp_path):
        _write(tmp_path, "demo_plugin.py", PLUGIN_SRC)
        registry = _fresh_registry()
        registry.discover([tmp_path])
        result = registry.run_one("demo_plugin", {"y": 2})
        assert result is not None
        assert result.ok is True
        assert result.plugin == "demo_plugin"
        assert result.data["ctx"] == {"y": 2}

    def test_run_one_phase_skips_target(self, tmp_path):
        _write(tmp_path, "demo_plugin.py", PLUGIN_SRC)
        registry = _fresh_registry()
        registry.discover([tmp_path])
        with mock.patch(
            "motor.plugin.registry.PluginRegistry.run_phase", return_value=[]
        ):
            assert registry.run_one("demo_plugin") is None
