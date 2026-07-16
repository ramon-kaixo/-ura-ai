from __future__ import annotations

from pathlib import Path


from motor.plugin.base import PluginBase
from motor.plugin.manifest import PluginManifest
from motor.plugin.registry_v2 import PluginRegistryV2


def _make_legacy_plugin(path: Path, name: str) -> Path:
    f = path / f"{name}.py"
    f.write_text(
        f'__plugin__ = {{"name": "{name}", "phase": "pre"}}\n'
        f"from motor.plugin.base import PluginBase\n"
        f"class _P(PluginBase):\n"
        f"    def execute(self, context):\n"
        f'        return {{"name": "{name}"}}\n'
    )
    return f


def _make_v2_plugin(base: Path, name: str, version: str = "1.0.0", extra_hooks: list | None = None) -> Path:
    d = base / name
    d.mkdir()
    yaml_lines = [
        f"name: {name}",
        f"version: '{version}'",
        "api_version: '1.0.0'",
        "entry_point: 'MyPlugin'",
    ]
    if extra_hooks:
        yaml_lines.append("hooks:")
        for h in extra_hooks:
            yaml_lines.append(f"  - {h}")
    (d / "plugin.yaml").write_text("\n".join(yaml_lines) + "\n")
    init_content = (
        "from motor.plugin.base import PluginBase\n"
        "class MyPlugin(PluginBase):\n"
        f"    def execute(self, context):\n"
        f"        return {{'name': '{name}', 'version': '{version}'}}\n"
    )
    (d / "__init__.py").write_text(init_content)
    return d


class TestRegistryV2Discovery:
    def test_discover_legacy_py_files(self, tmp_path: Path):
        registry = PluginRegistryV2()
        _make_legacy_plugin(tmp_path, "legacy_a")
        _make_legacy_plugin(tmp_path, "legacy_b")
        count = registry.discover([str(tmp_path)])
        assert count == 2
        assert registry.count() == 2

    def test_discover_v2_plugin(self, tmp_path: Path):
        registry = PluginRegistryV2()
        _make_v2_plugin(tmp_path, "v2_test")
        count = registry.discover([str(tmp_path)])
        assert count == 1
        assert registry.count() == 1

    def test_discover_ignores_init(self, tmp_path: Path):
        registry = PluginRegistryV2()
        (tmp_path / "__init__.py").write_text("")
        _make_legacy_plugin(tmp_path, "real")
        count = registry.discover([str(tmp_path)])
        assert count == 1

    def test_discover_empty_path(self):
        registry = PluginRegistryV2()
        count = registry.discover(["/nonexistent_path_f11"])
        assert count == 0


class TestRegistryV2GetManifest:
    def test_get_manifest_v2(self, tmp_path: Path):
        registry = PluginRegistryV2()
        _make_v2_plugin(tmp_path, "manifest_test")
        registry.discover([str(tmp_path)])
        manifest = registry.get_manifest("manifest_test")
        assert manifest is not None
        assert isinstance(manifest, PluginManifest)
        assert manifest.name == "manifest_test"
        assert manifest.version == "1.0.0"

    def test_get_manifest_nonexistent(self):
        registry = PluginRegistryV2()
        assert registry.get_manifest("no_such") is None


class TestRegistryV2Load:
    def test_load_v2_plugin(self, tmp_path: Path):
        registry = PluginRegistryV2()
        _make_v2_plugin(tmp_path, "load_test")
        registry.discover([str(tmp_path)])
        plugin = registry.get("load_test")
        assert plugin is not None
        assert isinstance(plugin, PluginBase)
        assert "load_test" in registry.loaded

    def test_load_legacy_plugin(self, tmp_path: Path):
        registry = PluginRegistryV2()
        _make_legacy_plugin(tmp_path, "legacy_load")
        registry.discover([str(tmp_path)])
        plugin = registry.get("legacy_load")
        assert plugin is not None
        assert isinstance(plugin, PluginBase)

    def test_get_nonexistent_returns_none(self):
        registry = PluginRegistryV2()
        assert registry.get("no_such") is None

    def test_get_caches_instance(self, tmp_path: Path):
        registry = PluginRegistryV2()
        _make_v2_plugin(tmp_path, "cache_test")
        registry.discover([str(tmp_path)])
        p1 = registry.get("cache_test")
        p2 = registry.get("cache_test")
        assert p1 is p2

    def test_loaded_property_empty(self):
        registry = PluginRegistryV2()
        assert registry.loaded == []

    def test_loaded_after_get(self, tmp_path: Path):
        registry = PluginRegistryV2()
        _make_v2_plugin(tmp_path, "loaded_test")
        registry.discover([str(tmp_path)])
        assert "loaded_test" not in registry.loaded
        registry.get("loaded_test")
        assert "loaded_test" in registry.loaded


class TestRegistryV2RunPhase:
    def test_run_phase_v2(self, tmp_path: Path):
        registry = PluginRegistryV2()
        _make_v2_plugin(tmp_path, "phase_test")
        registry.discover([str(tmp_path)])
        results = registry.run_phase("always")
        assert len(results) == 1
        assert results[0].ok is True
        assert results[0].data["name"] == "phase_test"

    def test_run_phase_legacy(self, tmp_path: Path):
        registry = PluginRegistryV2()
        _make_legacy_plugin(tmp_path, "legacy_phase")
        registry.discover([str(tmp_path)])
        results = registry.run_phase("pre")
        assert len(results) == 1
        assert results[0].ok is True

    def test_run_one(self, tmp_path: Path):
        registry = PluginRegistryV2()
        _make_v2_plugin(tmp_path, "run_one_test")
        registry.discover([str(tmp_path)])
        result = registry.run_one("run_one_test")
        assert result is not None
        assert result.ok is True

    def test_run_one_nonexistent(self):
        registry = PluginRegistryV2()
        result = registry.run_one("no_such")
        assert result is None


class TestRegistryV2Duplicates:
    def test_duplicate_name_legacy(self, tmp_path: Path):
        registry = PluginRegistryV2()
        d = tmp_path / "sub"
        d.mkdir()
        _make_legacy_plugin(tmp_path, "dup_legacy")
        _make_legacy_plugin(d, "dup_legacy")
        registry.discover([str(tmp_path), str(d)])
        assert registry.count() == 1  # sobrescrito

    def test_duplicate_v2_and_legacy(self, tmp_path: Path):
        registry = PluginRegistryV2()
        _make_v2_plugin(tmp_path, "shared_name")
        registry.discover([str(tmp_path)])
        assert registry.count() == 1


class TestRegistryV2Unload:
    def test_unload_removes_instance(self, tmp_path: Path):
        registry = PluginRegistryV2()
        _make_v2_plugin(tmp_path, "unload_test")
        registry.discover([str(tmp_path)])
        registry.get("unload_test")
        assert "unload_test" in registry.loaded
        result = registry.unload("unload_test")
        assert result is True
        assert "unload_test" not in registry.loaded

    def test_unload_nonexistent_returns_false(self):
        registry = PluginRegistryV2()
        assert registry.unload("no_such") is False


class TestRegistryV2Compatibility:
    def test_incompatible_api_version(self, tmp_path: Path):
        registry = PluginRegistryV2()
        d = tmp_path / "bad_api"
        d.mkdir()
        (d / "plugin.yaml").write_text("name: bad_api\napi_version: '99.0.0'\nentry_point: 'MyPlugin'\n")
        (d / "__init__.py").write_text(
            "from motor.plugin.base import PluginBase\n"
            "class MyPlugin(PluginBase):\n"
            "    def execute(self, context):\n"
            "        return {}\n"
        )
        registry.discover([str(tmp_path)])
        plugin = registry.get("bad_api")
        assert plugin is None

    def test_legacy_plugin_always_accepted(self, tmp_path: Path):
        registry = PluginRegistryV2()
        _make_legacy_plugin(tmp_path, "legacy_compat")
        registry.discover([str(tmp_path)])
        plugin = registry.get("legacy_compat")
        assert plugin is not None
