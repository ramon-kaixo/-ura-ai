from __future__ import annotations

import textwrap
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

from motor.core.state import DegradedMode
from motor.plugin.registry import PluginRegistry

PLUGIN_BOILERPLATE = """
from motor.plugin.base import PluginBase

class _P(PluginBase):
    def execute(self, context):
        return {{"plugin": "{name}"}}
"""


def _write_plugin(path: Path, name: str, phase: str = "always", extra: str = "") -> str:
    content = f'__plugin__ = {{"name": "{name}", "phase": "{phase}"}}\n'
    content += extra
    content += textwrap.dedent(PLUGIN_BOILERPLATE.format(name=name))
    path.write_text(content)
    return name


class TestPluginRegistryDiscovery:
    def test_discover_empty_path_returns_zero(self):
        registry = PluginRegistry()
        count = registry.discover(["/tmp/nonexistent_path_xyz_f10"])  # noqa: S108  -- ruta intencionalmente inexistente, no crea archivos
        assert count == 0

    def test_discover_valid_plugin(self, tmp_path: Path):
        registry = PluginRegistry()
        _write_plugin(tmp_path / "hello.py", "hello_world", "pre")
        count = registry.discover([str(tmp_path)])
        assert count == 1
        meta = registry.get_meta("hello_world")
        assert meta is not None
        assert meta.name == "hello_world"
        assert meta.phase == "pre"

    def test_discover_single_file(self, tmp_path: Path):
        registry = PluginRegistry()
        f = tmp_path / "single.py"
        _write_plugin(f, "single_plugin")
        count = registry.discover([str(f)])
        assert count == 1

    def test_discover_ignores_init_files(self, tmp_path: Path):
        registry = PluginRegistry()
        (tmp_path / "__init__.py").write_text("")
        _write_plugin(tmp_path / "real_plugin.py", "real_one")
        count = registry.discover([str(tmp_path)])
        assert count == 1

    def test_discover_non_py_file(self, tmp_path: Path):
        registry = PluginRegistry()
        (tmp_path / "readme.txt").write_text("not a plugin")
        count = registry.discover([str(tmp_path)])
        assert count == 0

    def test_discover_multiple_dirs(self, tmp_path: Path):
        registry = PluginRegistry()
        d1 = tmp_path / "d1"
        d2 = tmp_path / "d2"
        d1.mkdir()
        d2.mkdir()
        _write_plugin(d1 / "p1.py", "plugin_one")
        _write_plugin(d2 / "p2.py", "plugin_two")
        count = registry.discover([str(d1), str(d2)])
        assert count == 2

    def test_duplicate_plugin_name_overwrites(self, tmp_path: Path):
        registry = PluginRegistry()
        _write_plugin(tmp_path / "first.py", "dup_name")
        _write_plugin(tmp_path / "second.py", "dup_name")
        registry.discover([str(tmp_path)])
        assert registry.count() == 1


class TestPluginRegistryMetadata:
    def test_get_meta_nonexistent(self):
        registry = PluginRegistry()
        assert registry.get_meta("no_such_plugin") is None

    def test_get_meta_without_loading(self, tmp_path: Path):
        registry = PluginRegistry()
        _write_plugin(tmp_path / "meta_test.py", "meta_test_plugin")
        registry.discover([str(tmp_path)])
        meta = registry.get_meta("meta_test_plugin")
        assert meta is not None
        assert meta.phase == "always"
        assert "meta_test_plugin" not in registry.loaded

    def test_plugin_without_meta_fallback(self, tmp_path: Path):
        registry = PluginRegistry()
        f = tmp_path / "no_meta_plugin.py"
        f.write_text("# no __plugin__ defined\n")
        count = registry.discover([str(tmp_path)])
        assert count == 1
        meta = registry.get_meta("no_meta_plugin")
        assert meta is not None
        assert meta.name == "no_meta_plugin"

    def test_meta_not_loaded_until_get(self, tmp_path: Path):
        registry = PluginRegistry()
        _write_plugin(tmp_path / "lazy_check.py", "lazy_check")
        registry.discover([str(tmp_path)])
        assert "lazy_check" not in registry.loaded


class TestPluginRegistryLazyLoad:
    def test_get_triggers_lazy_load(self, tmp_path: Path):
        registry = PluginRegistry()
        _write_plugin(tmp_path / "lazy_load.py", "lazy_load_plugin")
        registry.discover([str(tmp_path)])
        assert "lazy_load_plugin" not in registry.loaded
        plugin = registry.get("lazy_load_plugin")
        assert plugin is not None
        assert "lazy_load_plugin" in registry.loaded

    def test_get_caches_instance(self, tmp_path: Path):
        registry = PluginRegistry()
        _write_plugin(tmp_path / "cache_check.py", "cache_check")
        registry.discover([str(tmp_path)])
        p1 = registry.get("cache_check")
        p2 = registry.get("cache_check")
        assert p1 is p2

    def test_get_nonexistent_returns_none(self):
        registry = PluginRegistry()
        assert registry.get("nonexistent_plugin_f10") is None


class TestPluginRegistryExecution:
    def test_run_phase_ok(self, tmp_path: Path):
        registry = PluginRegistry()
        _write_plugin(tmp_path / "phase_ok.py", "phase_ok_plugin", "pre")
        registry.discover([str(tmp_path)])
        results = registry.run_phase("pre")
        assert len(results) == 1
        assert results[0].ok is True
        assert results[0].plugin == "phase_ok_plugin"
        assert results[0].data["plugin"] == "phase_ok_plugin"

    def test_run_phase_always_included(self, tmp_path: Path):
        registry = PluginRegistry()
        _write_plugin(tmp_path / "always_p.py", "always_plugin", "always")
        _write_plugin(tmp_path / "pre_p.py", "pre_plugin", "pre")
        _write_plugin(tmp_path / "post_p.py", "post_plugin", "post")
        registry.discover([str(tmp_path)])
        pre_results = registry.run_phase("pre")
        assert len(pre_results) == 2
        names = {r.plugin for r in pre_results}
        assert "always_plugin" in names
        assert "pre_plugin" in names
        assert "post_plugin" not in names

    def test_run_phase_empty_phase(self, tmp_path: Path):
        registry = PluginRegistry()
        _write_plugin(tmp_path / "always_p.py", "always_only", "always")
        registry.discover([str(tmp_path)])
        results = registry.run_phase("nonexistent_phase")
        assert len(results) == 1
        assert results[0].plugin == "always_only"

    def test_run_one_nonexistent(self):
        registry = PluginRegistry()
        result = registry.run_one("no_such_plugin_f10")
        assert result is None

    def test_run_one_specific(self, tmp_path: Path):
        registry = PluginRegistry()
        _write_plugin(tmp_path / "a.py", "plugin_a", "pre")
        _write_plugin(tmp_path / "b.py", "plugin_b", "pre")
        registry.discover([str(tmp_path)])
        result = registry.run_one("plugin_a")
        assert result is not None
        assert result.plugin == "plugin_a"
        assert result.ok is True


class TestPluginRegistryDegradedModeIntegration:
    def _clean_env(self) -> tuple[PluginRegistry, DegradedMode]:
        dm = DegradedMode.instancia()
        registry = PluginRegistry()
        return registry, dm

    def test_import_failure_marks_degraded(self, tmp_path: Path):
        registry, dm = self._clean_env()
        plugin_name = "import_fail_f10"
        f = tmp_path / f"{plugin_name}.py"
        f.write_text(f'__plugin__ = {{"name": "{plugin_name}", "phase": "pre"}}\nimport nonexistent_module_xyz_f10\n')
        registry.discover([str(tmp_path)])
        results = registry.run_phase("pre")
        assert len(results) == 1
        assert results[0].ok is False
        assert dm.is_degraded(f"plugin:{plugin_name}")

    def test_execution_failure_marks_degraded(self, tmp_path: Path):
        registry, dm = self._clean_env()
        plugin_name = "exec_fail_f10"
        content = f"""
__plugin__ = {{"name": "{plugin_name}", "phase": "pre"}}
from motor.plugin.base import PluginBase
class _P(PluginBase):
    def execute(self, context):
        raise RuntimeError("intentional exec failure f10")
"""
        f = tmp_path / f"{plugin_name}.py"
        f.write_text(textwrap.dedent(content))
        registry.discover([str(tmp_path)])
        results = registry.run_phase("pre")
        assert len(results) == 1
        assert results[0].ok is False
        assert "intentional exec failure f10" in results[0].error
        assert dm.is_degraded(f"plugin:{plugin_name}")

    def test_execution_failure_recovers_after_healthy_load(self, tmp_path: Path):
        registry, dm = self._clean_env()
        good_name = "good_recovery_f10"
        content = f"""
__plugin__ = {{"name": "{good_name}", "phase": "pre"}}
from motor.plugin.base import PluginBase
class _P(PluginBase):
    def execute(self, context):
        return {{"ok": True}}
"""
        f = tmp_path / f"{good_name}.py"
        f.write_text(textwrap.dedent(content))
        registry.discover([str(tmp_path)])
        registry.run_phase("pre")
        assert not dm.is_degraded(f"plugin:{good_name}")
        # Successful load calls mark_healthy — degraded should be cleared
        assert dm.is_degraded(f"plugin:{good_name}") is False

    def test_isolated_plugin_failure(self, tmp_path: Path):
        registry, dm = self._clean_env()
        fail_name = "isolated_fail_f10"
        good_name = "isolated_good_f10"
        fail_content = f'__plugin__ = {{"name": "{fail_name}", "phase": "pre"}}\nimport nonexistent_mod_xyz_f10\n'
        good_content = f"""
__plugin__ = {{"name": "{good_name}", "phase": "pre"}}
from motor.plugin.base import PluginBase
class _P(PluginBase):
    def execute(self, context):
        return {{"ok": True}}
"""
        (tmp_path / f"{fail_name}.py").write_text(fail_content)
        (tmp_path / f"{good_name}.py").write_text(textwrap.dedent(good_content))
        registry.discover([str(tmp_path)])
        results = registry.run_phase("pre")
        assert len(results) == 2
        ok_results = [r for r in results if r.ok]
        fail_results = [r for r in results if not r.ok]
        assert len(ok_results) == 1
        assert ok_results[0].plugin == good_name
        assert len(fail_results) == 1
        assert fail_results[0].plugin == fail_name
        assert dm.is_degraded(f"plugin:{fail_name}")
        assert not dm.is_degraded(f"plugin:{good_name}")


class TestPluginRegistryEdgeCases:
    def test_no_subclass_of_pluginbase_marks_degraded(self, tmp_path: Path):
        registry = PluginRegistry()
        plugin_name = "no_subclass_f10"
        f = tmp_path / f"{plugin_name}.py"
        f.write_text(f'__plugin__ = {{"name": "{plugin_name}", "phase": "pre"}}\nclass Foo:\n    pass\n')
        registry.discover([str(tmp_path)])
        results = registry.run_phase("pre")
        assert len(results) == 1
        assert results[0].ok is False
        assert results[0].error == "Plugin load failed"
        assert DegradedMode.instancia().is_degraded(f"plugin:{plugin_name}")

    def test_exception_during_instantiation_marks_degraded(self, tmp_path: Path):
        registry = PluginRegistry()
        plugin_name = "instantiate_fail_f10"
        content = f"""
__plugin__ = {{"name": "{plugin_name}", "phase": "pre"}}
from motor.plugin.base import PluginBase
class _P(PluginBase):
    def __init__(self):
        raise ValueError("intentional init fail f10")
    def execute(self, context):
        return {{}}
"""
        f = tmp_path / f"{plugin_name}.py"
        f.write_text(textwrap.dedent(content))
        registry.discover([str(tmp_path)])
        results = registry.run_phase("pre")
        assert len(results) == 1
        assert results[0].ok is False
        assert DegradedMode.instancia().is_degraded(f"plugin:{plugin_name}")
