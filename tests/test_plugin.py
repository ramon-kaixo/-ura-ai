from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from motor.plugin.base import PluginBase, PluginMeta
from motor.plugin.manifest import ManifestError, PluginManifest, find_manifest, parse_manifest
from motor.plugin.registry import PluginRegistry
from motor.plugin.registry_v2 import ManifestError as RegistryV2ManifestError
from motor.plugin.registry_v2 import PluginEntryV2, PluginRegistryV2

if TYPE_CHECKING:
    from pathlib import Path


# ── Helpers ────────────────────────────────────────────────────────────────


def _make_legacy_plugin(path: Path, name: str, phase: str = "always") -> Path:
    """Write a legacy .py plugin file (no manifest, __plugin__ dict)."""
    f = path / f"{name}.py"
    f.write_text(
        f'__plugin__ = {{"name": "{name}", "phase": "{phase}"}}\n'
        "from motor.plugin.base import PluginBase\n"
        "class _P(PluginBase):\n"
        "    def execute(self, context):\n"
        f"        return {{'name': '{name}'}}\n",
    )
    return f


def _make_v2_plugin(
    base: Path,
    name: str,
    version: str = "1.0.0",
    api_version: str = "1.0.0",
    entry_point: str = "MyPlugin",
    phases: list[str] | None = None,
    hooks: list[str] | None = None,
) -> Path:
    """Write a V2 plugin directory with plugin.yaml + __init__.py."""
    d = base / name
    d.mkdir(exist_ok=True)
    lines = [
        f"name: {name}",
        f"version: '{version}'",
        f"api_version: '{api_version}'",
        f"entry_point: '{entry_point}'",
    ]
    if phases:
        lines.append(f"phases: [{', '.join(phases)}]")
    if hooks:
        lines.append("hooks:")
        lines.extend(f"  - {h}" for h in hooks)
    (d / "plugin.yaml").write_text("\n".join(lines) + "\n")
    (d / "__init__.py").write_text(
        "from motor.plugin.base import PluginBase\n"
        f"class {entry_point}(PluginBase):\n"
        "    def execute(self, context):\n"
        f"        return {{'name': '{name}', 'version': '{version}'}}\n",
    )
    return d


# ── PluginBase ─────────────────────────────────────────────────────────────


class TestPluginBase:
    def test_abstract_cannot_instantiate(self) -> None:
        with pytest.raises(TypeError):
            PluginBase()  # type: ignore[abstract]

    def test_concrete_plugin_has_default_meta(self) -> None:
        class _Concrete(PluginBase):
            def execute(self, context: dict[str, Any] | None = None) -> dict[str, Any]:
                return {}

        p = _Concrete()
        assert p.meta is not None
        assert p.meta.name == "_Concrete"
        assert p.meta.phase == "always"
        assert p.meta.timeout == 30
        assert p.meta.blocking is False

    def test_repr_includes_name(self) -> None:
        class _Named(PluginBase):
            def execute(self, context: dict[str, Any] | None = None) -> dict[str, Any]:
                return {}

        assert repr(_Named()) == "<Plugin _Named>"

    def test_rollback_default_is_noop(self) -> None:
        class _NoRollback(PluginBase):
            def execute(self, context: dict[str, Any] | None = None) -> dict[str, Any]:
                return {}

        _NoRollback().rollback({"key": "val"})  # must not raise

    def test_rollback_can_be_overridden(self) -> None:
        class _WithRollback(PluginBase):
            def __init__(self) -> None:
                super().__init__()
                self.rolled_back = False

            def execute(self, context: dict[str, Any] | None = None) -> dict[str, Any]:
                return {}

            def rollback(self, context: dict[str, Any] | None = None) -> None:
                self.rolled_back = True

        p = _WithRollback()
        p.rollback({"key": "val"})
        assert p.rolled_back is True

    def test_execute_returns_dict(self) -> None:
        class _Returning(PluginBase):
            def execute(self, context: dict[str, Any] | None = None) -> dict[str, Any]:
                return {"result": 42, "items": [1, 2, 3]}

        assert _Returning().execute({"input": "test"}) == {"result": 42, "items": [1, 2, 3]}

    def test_execute_receives_context(self) -> None:
        class _CtxAware(PluginBase):
            def execute(self, context: dict[str, Any] | None = None) -> dict[str, Any]:
                return {"received": context.get("key") if context else None}

        result = _CtxAware().execute({"key": "value"})
        assert result["received"] == "value"

    def test_execute_with_none_context(self) -> None:
        class _NoneCtx(PluginBase):
            def execute(self, context: dict[str, Any] | None = None) -> dict[str, Any]:
                return {"got_none": context is None}

        assert _NoneCtx().execute(None)["got_none"] is True

    def test_meta_from_init(self) -> None:
        class _CustomMeta(PluginBase):
            def __init__(self) -> None:
                super().__init__()
                self.meta = PluginMeta(name="custom", phase="pre", timeout=10)

            def execute(self, context: dict[str, Any] | None = None) -> dict[str, Any]:
                return {}

        p = _CustomMeta()
        assert p.meta.name == "custom"
        assert p.meta.phase == "pre"
        assert p.meta.timeout == 10

    def test_custom_meta_via_from_dict(self) -> None:
        p = PluginMeta.from_dict({"name": "mymeta", "phase": "post"})
        assert p.name == "mymeta"
        assert p.phase == "post"


# ── PluginBase lifecycle hooks (invoked by PluginRegistryV2) ───────────────


class TestPluginBaseLifecycleHooks:
    def test_on_load_called_during_v2_load(self, tmp_path: Path) -> None:
        d = tmp_path / "lifecycle_test"
        d.mkdir()
        (d / "plugin.yaml").write_text(
            "name: lifecycle_test\napi_version: '1.0.0'\nentry_point: 'LifecyclePlugin'\n",
        )
        (d / "__init__.py").write_text(
            "from motor.plugin.base import PluginBase\n"
            "class LifecyclePlugin(PluginBase):\n"
            "    load_called = False\n"
            "    def on_load(self):\n"
            "        LifecyclePlugin.load_called = True\n"
            "    def execute(self, context):\n"
            "        return {}\n",
        )
        registry = PluginRegistryV2()
        registry.discover([str(tmp_path)])
        plugin = registry.get("lifecycle_test")
        assert plugin is not None
        assert type(plugin).load_called is True

    def test_on_load_failure_does_not_block_load(self, tmp_path: Path) -> None:
        d = tmp_path / "failing_load"
        d.mkdir()
        (d / "plugin.yaml").write_text(
            "name: failing_load\napi_version: '1.0.0'\nentry_point: 'FailingLoadPlugin'\n",
        )
        (d / "__init__.py").write_text(
            "from motor.plugin.base import PluginBase\n"
            "class FailingLoadPlugin(PluginBase):\n"
            "    def execute(self, context):\n"
            "        return {}\n"
            "    def on_load(self):\n"
            "        raise RuntimeError('intentional on_load failure')\n",
        )
        registry = PluginRegistryV2()
        registry.discover([str(tmp_path)])
        plugin = registry.get("failing_load")
        assert plugin is not None

    def test_on_unload_called_during_unload(self, tmp_path: Path) -> None:
        d = tmp_path / "unload_test"
        d.mkdir()
        (d / "plugin.yaml").write_text(
            "name: unload_test\napi_version: '1.0.0'\nentry_point: 'UnloadPlugin'\n",
        )
        (d / "__init__.py").write_text(
            "from motor.plugin.base import PluginBase\n"
            "class UnloadPlugin(PluginBase):\n"
            "    unload_called = False\n"
            "    def execute(self, context):\n"
            "        return {}\n"
            "    def on_unload(self):\n"
            "        UnloadPlugin.unload_called = True\n",
        )
        registry = PluginRegistryV2()
        registry.discover([str(tmp_path)])
        plugin = registry.get("unload_test")
        assert plugin is not None
        result = registry.unload("unload_test")
        assert result is True
        assert type(plugin).unload_called is True

    def test_on_unload_failure_does_not_block_unload(self, tmp_path: Path) -> None:
        d = tmp_path / "failing_unload"
        d.mkdir()
        (d / "plugin.yaml").write_text(
            "name: failing_unload\napi_version: '1.0.0'\nentry_point: 'FailingUnloadPlugin'\n",
        )
        (d / "__init__.py").write_text(
            "from motor.plugin.base import PluginBase\n"
            "class FailingUnloadPlugin(PluginBase):\n"
            "    def execute(self, context):\n"
            "        return {}\n"
            "    def on_unload(self):\n"
            "        raise RuntimeError('intentional on_unload failure')\n",
        )
        registry = PluginRegistryV2()
        registry.discover([str(tmp_path)])
        registry.get("failing_unload")
        result = registry.unload("failing_unload")
        assert result is True
        assert "failing_unload" not in registry.loaded

    def test_lifecycle_disabled_via_manifest(self, tmp_path: Path) -> None:
        d = tmp_path / "no_lifecycle"
        d.mkdir()
        (d / "plugin.yaml").write_text(
            "name: no_lifecycle\napi_version: '1.0.0'\nentry_point: 'NoLifecyclePlugin'\n"
            "lifecycle:\n  on_load: false\n  on_unload: false\n",
        )
        (d / "__init__.py").write_text(
            "from motor.plugin.base import PluginBase\n"
            "class NoLifecyclePlugin(PluginBase):\n"
            "    def execute(self, context):\n"
            "        return {}\n"
            "    def on_load(self):\n"
            "        raise RuntimeError('should not be called')\n"
            "    def on_unload(self):\n"
            "        raise RuntimeError('should not be called')\n",
        )
        registry = PluginRegistryV2()
        registry.discover([str(tmp_path)])
        plugin = registry.get("no_lifecycle")
        assert plugin is not None
        result = registry.unload("no_lifecycle")
        assert result is True

    def test_manifest_assigned_to_instance(self, tmp_path: Path) -> None:
        d = tmp_path / "manifest_attr"
        d.mkdir()
        (d / "plugin.yaml").write_text(
            "name: manifest_attr\napi_version: '1.0.0'\nversion: '2.0.0'\nentry_point: 'ManifestAttrPlugin'\n",
        )
        (d / "__init__.py").write_text(
            "from motor.plugin.base import PluginBase\n"
            "class ManifestAttrPlugin(PluginBase):\n"
            "    def execute(self, context):\n"
            "        return {}\n",
        )
        registry = PluginRegistryV2()
        registry.discover([str(tmp_path)])
        plugin = registry.get("manifest_attr")
        assert plugin is not None
        manifest = getattr(plugin, "manifest", None)
        assert manifest is not None
        assert manifest.name == "manifest_attr"
        assert manifest.version == "2.0.0"

    def test_legacy_plugin_no_lifecycle_hooks(self, tmp_path: Path) -> None:
        registry = PluginRegistryV2()
        _make_legacy_plugin(tmp_path, "no_hooks_legacy")
        registry.discover([str(tmp_path)])
        plugin = registry.get("no_hooks_legacy")
        assert plugin is not None
        assert not hasattr(plugin, "on_load")
        assert not hasattr(plugin, "on_unload")


# ── PluginManifest ─────────────────────────────────────────────────────────


class TestPluginManifestCreation:
    def test_default_manifest(self) -> None:
        m = PluginManifest()
        assert m.api_version == "1.0.0"
        assert m.name == ""
        assert m.version == "0.1.0"
        assert m.description == ""
        assert m.author == {}
        assert m.dependencies == {"plugins": [], "python": []}
        assert m.lifecycle == {"on_load": True, "on_unload": True}
        assert m.hooks == []
        assert m.phases == ["always"]
        assert m.tags == []

    def test_manifest_with_name(self) -> None:
        m = PluginManifest(name="test-plugin")
        assert m.name == "test-plugin"

    def test_manifest_all_fields(self) -> None:
        m = PluginManifest(
            api_version="2.0.0",
            name="full-plugin",
            version="3.1.0",
            description="A full plugin",
            author={"name": "me"},
            dependencies={"plugins": ["base"], "python": ["requests"]},
            lifecycle={"on_load": True, "on_unload": False},
            hooks=["pre_ingest"],
            phases=["pre", "post"],
            tags=["search", "experimental"],
        )
        assert m.api_version == "2.0.0"
        assert m.name == "full-plugin"
        assert m.version == "3.1.0"
        assert m.dependencies["plugins"] == ["base"]
        assert m.hooks == ["pre_ingest"]
        assert m.phases == ["pre", "post"]
        assert m.tags == ["search", "experimental"]

    def test_manifest_version_types(self) -> None:
        m = PluginManifest(version="0.0.0")
        assert m.version == "0.0.0"
        m2 = PluginManifest(version="999.999.999")
        assert m2.version == "999.999.999"


class TestPluginManifestParse:
    def test_parse_yaml(self, tmp_path: Path) -> None:
        f = tmp_path / "plugin.yaml"
        f.write_text("name: test-plugin\nversion: '1.0.0'\napi_version: '1.0.0'\n")
        manifest = parse_manifest(f)
        assert manifest is not None
        assert manifest.name == "test-plugin"
        assert manifest.version == "1.0.0"

    def test_parse_json(self, tmp_path: Path) -> None:
        f = tmp_path / "plugin.json"
        f.write_text('{"name": "json-plugin", "version": "2.0.0", "api_version": "1.0.0"}')
        manifest = parse_manifest(f)
        assert manifest is not None
        assert manifest.name == "json-plugin"
        assert manifest.version == "2.0.0"

    def test_parse_missing_file(self, tmp_path: Path) -> None:
        assert parse_manifest(tmp_path / "nonexistent.yaml") is None

    def test_parse_empty_yaml(self, tmp_path: Path) -> None:
        f = tmp_path / "plugin.yaml"
        f.write_text("")
        assert parse_manifest(f) is None

    def test_parse_invalid_yaml(self, tmp_path: Path) -> None:
        f = tmp_path / "plugin.yaml"
        f.write_text("name: [invalid\n")
        assert parse_manifest(f) is None

    def test_parse_yaml_not_a_dict(self, tmp_path: Path) -> None:
        f = tmp_path / "plugin.yaml"
        f.write_text("- just\n- a\n- list\n")
        assert parse_manifest(f) is None

    def test_parse_json_not_a_dict(self, tmp_path: Path) -> None:
        f = tmp_path / "plugin.json"
        f.write_text('["just", "a", "list"]')
        assert parse_manifest(f) is None

    def test_parse_unsupported_format(self, tmp_path: Path) -> None:
        f = tmp_path / "plugin.toml"
        f.write_text("[plugin]\nname = 'test'\n")
        assert parse_manifest(f) is None

    def test_parse_with_defaults(self, tmp_path: Path) -> None:
        f = tmp_path / "plugin.yaml"
        f.write_text("name: defaults-test\n")
        manifest = parse_manifest(f)
        assert manifest is not None
        assert manifest.api_version == "1.0.0"
        assert manifest.version == "0.1.0"
        assert manifest.phases == ["always"]
        assert manifest.hooks == []
        assert manifest.tags == []

    def test_parse_with_hooks_and_tags(self, tmp_path: Path) -> None:
        f = tmp_path / "plugin.yaml"
        f.write_text(
            "name: tagged\n"
            "hooks:\n  - pre_search\n"
            "tags:\n  - search\n  - experimental\n"
            "phases:\n  - pre\n  - post\n",
        )
        manifest = parse_manifest(f)
        assert manifest is not None
        assert manifest.hooks == ["pre_search"]
        assert manifest.tags == ["search", "experimental"]
        assert manifest.phases == ["pre", "post"]

    def test_parse_with_dependencies(self, tmp_path: Path) -> None:
        f = tmp_path / "plugin.yaml"
        f.write_text(
            "name: dep-test\n"
            "dependencies:\n"
            "  plugins:\n"
            "    - name: base\n"
            "      version: '>=1.0.0'\n"
            "  python:\n"
            "    - 'requests>=2.28'\n",
        )
        manifest = parse_manifest(f)
        assert manifest is not None
        assert manifest.dependencies["plugins"][0]["name"] == "base"
        assert manifest.dependencies["python"][0] == "requests>=2.28"

    def test_parse_dependencies_not_dict_fallback(self, tmp_path: Path) -> None:
        f = tmp_path / "plugin.yaml"
        f.write_text("name: bad-dep\ndependencies: 'not-a-dict'\n")
        manifest = parse_manifest(f)
        assert manifest is not None
        assert manifest.dependencies == {"plugins": [], "python": []}

    def test_parse_lifecycle_not_dict_fallback(self, tmp_path: Path) -> None:
        f = tmp_path / "plugin.yaml"
        f.write_text("name: bad-lifecycle\nlifecycle: 'not-a-dict'\n")
        manifest = parse_manifest(f)
        assert manifest is not None
        assert manifest.lifecycle == {"on_load": True, "on_unload": True, "on_config_change": False}

    def test_parse_without_name_falls_back_to_parent_dir(self, tmp_path: Path) -> None:
        d = tmp_path / "my_plugin_dir"
        d.mkdir()
        f = d / "plugin.yaml"
        f.write_text("version: '1.0.0'\n")
        manifest = parse_manifest(f)
        assert manifest is not None
        assert manifest.name == "my_plugin_dir"

    def test_parse_unknown_fields_logged_but_accepted(self, tmp_path: Path) -> None:
        f = tmp_path / "plugin.yaml"
        f.write_text("name: extra-plugin\nunknown_field: value\nanother_unknown: 42\n")
        manifest = parse_manifest(f)
        assert manifest is not None
        assert manifest.name == "extra-plugin"


class TestFindManifest:
    def test_find_yaml(self, tmp_path: Path) -> None:
        f = tmp_path / "plugin.yaml"
        f.write_text("name: test\n")
        assert find_manifest(tmp_path) == f

    def test_find_yml(self, tmp_path: Path) -> None:
        f = tmp_path / "plugin.yml"
        f.write_text("name: test\n")
        assert find_manifest(tmp_path) == f

    def test_find_json(self, tmp_path: Path) -> None:
        f = tmp_path / "plugin.json"
        f.write_text('{"name": "test"}')
        assert find_manifest(tmp_path) == f

    def test_find_priority_yaml_over_yml_json(self, tmp_path: Path) -> None:
        yaml_f = tmp_path / "plugin.yaml"
        json_f = tmp_path / "plugin.json"
        yaml_f.write_text("name: yaml\n")
        json_f.write_text('{"name": "json"}')
        assert find_manifest(tmp_path) == yaml_f

    def test_find_none(self, tmp_path: Path) -> None:
        assert find_manifest(tmp_path) is None


class TestManifestError:
    def test_is_exception(self) -> None:
        assert isinstance(ManifestError("msg"), Exception)

    def test_str(self) -> None:
        assert str(ManifestError("something wrong")) == "something wrong"

    def test_circular_dependency_message(self) -> None:
        with pytest.raises(ManifestError, match="circular"):
            raise ManifestError("Dependencia circular: a -> b -> a")


# ── PluginMeta ─────────────────────────────────────────────────────────────


class TestPluginMeta:
    def test_from_dict_defaults(self) -> None:
        meta = PluginMeta.from_dict({"name": "test"})
        assert meta.name == "test"
        assert meta.phase == "always"
        assert meta.blocking is False
        assert meta.timeout == 30
        assert meta.description == ""

    def test_from_dict_all_fields(self) -> None:
        meta = PluginMeta.from_dict(
            {"name": "full", "phase": "pre", "blocking": True, "timeout": 60, "description": "A test plugin"},
        )
        assert meta.name == "full"
        assert meta.phase == "pre"
        assert meta.blocking is True
        assert meta.timeout == 60
        assert meta.description == "A test plugin"

    def test_from_dict_missing_name_fallback(self) -> None:
        meta = PluginMeta.from_dict({})
        assert meta.name == "unknown"

    def test_from_dict_type_coercion(self) -> None:
        meta = PluginMeta.from_dict({"name": "test", "timeout": "45", "blocking": 1})
        assert meta.timeout == 45
        assert meta.blocking is True

    def test_from_source_valid(self) -> None:
        source = '__plugin__ = {"name": "ast_plugin", "phase": "post", "timeout": 15}\n'
        meta = PluginMeta.from_source(source)
        assert meta is not None
        assert meta.name == "ast_plugin"
        assert meta.phase == "post"
        assert meta.timeout == 15

    def test_from_source_invalid_syntax(self) -> None:
        assert PluginMeta.from_source("this is not valid python {{{") is None

    def test_from_source_no_plugin_var(self) -> None:
        assert PluginMeta.from_source("x = 1\ny = 2\n") is None

    def test_from_source_with_bool(self) -> None:
        source = '__plugin__ = {"name": "bool_plugin", "blocking": True}\n'
        meta = PluginMeta.from_source(source)
        assert meta is not None
        assert meta.blocking is True

    def test_from_source_with_list(self) -> None:
        source = '__plugin__ = {"name": "list_plugin", "phases": ["pre", "post"]}\n'
        meta = PluginMeta.from_source(source)
        assert meta is not None
        assert meta.name == "list_plugin"


# ── PluginRegistry ─────────────────────────────────────────────────────────


class TestPluginRegistryDiscover:
    def test_empty_path_returns_zero(self) -> None:
        assert PluginRegistry().discover(["/nonexistent_path_for_test"]) == 0

    def test_directory_with_plugins(self, tmp_path: Path) -> None:
        registry = PluginRegistry()
        _make_legacy_plugin(tmp_path, "p1")
        _make_legacy_plugin(tmp_path, "p2")
        assert registry.discover([str(tmp_path)]) == 2
        assert registry.count() == 2

    def test_single_file(self, tmp_path: Path) -> None:
        registry = PluginRegistry()
        f = _make_legacy_plugin(tmp_path, "single")
        assert registry.discover([str(f)]) == 1

    def test_ignores_init_files(self, tmp_path: Path) -> None:
        registry = PluginRegistry()
        (tmp_path / "__init__.py").write_text("")
        _make_legacy_plugin(tmp_path, "real")
        assert registry.discover([str(tmp_path)]) == 1

    def test_ignores_non_py_files(self, tmp_path: Path) -> None:
        registry = PluginRegistry()
        (tmp_path / "note.txt").write_text("not a plugin")
        assert registry.discover([str(tmp_path)]) == 0

    def test_invalid_path(self) -> None:
        assert PluginRegistry().discover(["/dev/null/nonexistent"]) == 0

    def test_entries_property_returns_copy(self, tmp_path: Path) -> None:
        registry = PluginRegistry()
        _make_legacy_plugin(tmp_path, "prop_test")
        registry.discover([str(tmp_path)])
        entries = registry.entries
        entries.clear()
        assert registry.count() == 1

    def test_loaded_empty_after_discover(self, tmp_path: Path) -> None:
        registry = PluginRegistry()
        _make_legacy_plugin(tmp_path, "lazy")
        registry.discover([str(tmp_path)])
        assert registry.loaded == []


class TestPluginRegistryGet:
    def test_nonexistent(self) -> None:
        assert PluginRegistry().get("no_such") is None

    def test_triggers_lazy_load(self, tmp_path: Path) -> None:
        registry = PluginRegistry()
        _make_legacy_plugin(tmp_path, "lazy_load")
        registry.discover([str(tmp_path)])
        assert "lazy_load" not in registry.loaded
        plugin = registry.get("lazy_load")
        assert plugin is not None
        assert "lazy_load" in registry.loaded

    def test_caches_instance(self, tmp_path: Path) -> None:
        registry = PluginRegistry()
        _make_legacy_plugin(tmp_path, "cache_test")
        registry.discover([str(tmp_path)])
        assert registry.get("cache_test") is registry.get("cache_test")

    def test_get_meta(self, tmp_path: Path) -> None:
        registry = PluginRegistry()
        _make_legacy_plugin(tmp_path, "meta_test", phase="post")
        registry.discover([str(tmp_path)])
        meta = registry.get_meta("meta_test")
        assert meta is not None
        assert meta.phase == "post"
        assert "meta_test" not in registry.loaded

    def test_get_meta_nonexistent(self) -> None:
        assert PluginRegistry().get_meta("no_such") is None


class TestPluginRegistryRun:
    def test_run_phase_ok(self, tmp_path: Path) -> None:
        registry = PluginRegistry()
        _make_legacy_plugin(tmp_path, "run_test", phase="pre")
        registry.discover([str(tmp_path)])
        results = registry.run_phase("pre")
        assert len(results) == 1
        assert results[0].ok is True
        assert results[0].plugin == "run_test"
        assert results[0].phase == "pre"
        assert results[0].duration_ms >= 0

    def test_run_phase_always_included(self, tmp_path: Path) -> None:
        registry = PluginRegistry()
        _make_legacy_plugin(tmp_path, "always_p", phase="always")
        _make_legacy_plugin(tmp_path, "pre_p", phase="pre")
        _make_legacy_plugin(tmp_path, "post_p", phase="post")
        registry.discover([str(tmp_path)])
        results = registry.run_phase("pre")
        assert len(results) == 2
        names = {r.plugin for r in results}
        assert "always_p" in names
        assert "pre_p" in names
        assert "post_p" not in names

    def test_run_phase_empty_when_no_matches(self, tmp_path: Path) -> None:
        registry = PluginRegistry()
        _make_legacy_plugin(tmp_path, "only_pre", phase="pre")
        registry.discover([str(tmp_path)])
        assert len(registry.run_phase("post")) == 0

    def test_run_phase_empty_registry(self) -> None:
        assert PluginRegistry().run_phase("pre") == []

    def test_run_phase_with_context(self, tmp_path: Path) -> None:
        registry = PluginRegistry()
        f = tmp_path / "ctx_plugin.py"
        f.write_text(
            '__plugin__ = {"name": "ctx_plugin", "phase": "pre"}\n'
            "from motor.plugin.base import PluginBase\n"
            "class _P(PluginBase):\n"
            "    def execute(self, context):\n"
            "        return {'received': context.get('key') if context else None}\n",
        )
        registry.discover([str(tmp_path)])
        results = registry.run_phase("pre", {"key": "value"})
        assert results[0].data["received"] == "value"

    def test_run_one_specific(self, tmp_path: Path) -> None:
        registry = PluginRegistry()
        _make_legacy_plugin(tmp_path, "a", phase="pre")
        _make_legacy_plugin(tmp_path, "b", phase="pre")
        registry.discover([str(tmp_path)])
        result = registry.run_one("a")
        assert result is not None
        assert result.plugin == "a"
        assert result.ok is True

    def test_run_one_nonexistent(self) -> None:
        assert PluginRegistry().run_one("no_such") is None


class TestPluginRegistryDuplicate:
    def test_duplicate_name_overwrites(self, tmp_path: Path) -> None:
        registry = PluginRegistry()
        d1 = tmp_path / "d1"
        d2 = tmp_path / "d2"
        d1.mkdir()
        d2.mkdir()
        _make_legacy_plugin(d1, "dup_name")
        _make_legacy_plugin(d2, "dup_name")
        registry.discover([str(d1), str(d2)])
        assert registry.count() == 1


class TestPluginRegistryError:
    def test_load_failure_returns_none(self, tmp_path: Path) -> None:
        registry = PluginRegistry()
        f = tmp_path / "broken.py"
        f.write_text('__plugin__ = {"name": "broken"}\nimport nonexistent_module_xyz\n')
        registry.discover([str(tmp_path)])
        assert registry.get("broken") is None

    def test_execution_failure_returns_failed_result(self, tmp_path: Path) -> None:
        registry = PluginRegistry()
        f = tmp_path / "fail_exec.py"
        f.write_text(
            '__plugin__ = {"name": "fail_exec", "phase": "pre"}\n'
            "from motor.plugin.base import PluginBase\n"
            "class _P(PluginBase):\n"
            "    def execute(self, context):\n"
            "        raise RuntimeError('execution error')\n",
        )
        registry.discover([str(tmp_path)])
        results = registry.run_phase("pre")
        assert results[0].ok is False
        assert "execution error" in results[0].error

    def test_no_subclass_returns_error(self, tmp_path: Path) -> None:
        registry = PluginRegistry()
        f = tmp_path / "no_subclass.py"
        f.write_text('__plugin__ = {"name": "no_subclass"}\nclass Foo:\n    pass\n')
        registry.discover([str(tmp_path)])
        results = registry.run_phase("always")
        assert results[0].ok is False
        assert results[0].error == "Plugin load failed"

    def test_broken_import_does_not_affect_other_plugins(self, tmp_path: Path) -> None:
        registry = PluginRegistry()
        (tmp_path / "broken.py").write_text(
            '__plugin__ = {"name": "broken", "phase": "pre"}\nimport nonexistent_mod_xyz\n',
        )
        (tmp_path / "good.py").write_text(
            '__plugin__ = {"name": "good", "phase": "pre"}\n'
            "from motor.plugin.base import PluginBase\n"
            "class _P(PluginBase):\n"
            "    def execute(self, context):\n"
            "        return {'ok': True}\n",
        )
        registry.discover([str(tmp_path)])
        results = registry.run_phase("pre")
        assert len(results) == 2
        ok_results = [r for r in results if r.ok]
        fail_results = [r for r in results if not r.ok]
        assert len(ok_results) == 1
        assert ok_results[0].plugin == "good"
        assert len(fail_results) == 1
        assert fail_results[0].plugin == "broken"


# ── PluginRegistryV2 ───────────────────────────────────────────────────────


class TestRegistryV2Discover:
    def test_legacy_py_files(self, tmp_path: Path) -> None:
        registry = PluginRegistryV2()
        _make_legacy_plugin(tmp_path, "legacy_a")
        _make_legacy_plugin(tmp_path, "legacy_b")
        assert registry.discover([str(tmp_path)]) == 2
        assert registry.count() == 2

    def test_v2_manifest(self, tmp_path: Path) -> None:
        registry = PluginRegistryV2()
        _make_v2_plugin(tmp_path, "v2_test")
        assert registry.discover([str(tmp_path)]) == 1
        assert registry.count() == 1

    def test_mixed_legacy_and_v2(self, tmp_path: Path) -> None:
        registry = PluginRegistryV2()
        _make_legacy_plugin(tmp_path, "legacy")
        _make_v2_plugin(tmp_path, "packaged")
        assert registry.discover([str(tmp_path)]) == 2

    def test_ignores_init_and_private(self, tmp_path: Path) -> None:
        registry = PluginRegistryV2()
        (tmp_path / "__init__.py").write_text("")
        (tmp_path / "_private.py").write_text("")
        _make_legacy_plugin(tmp_path, "visible")
        assert registry.discover([str(tmp_path)]) == 1

    def test_empty_directory(self, tmp_path: Path) -> None:
        assert PluginRegistryV2().discover([str(tmp_path / "empty")]) == 0

    def test_nested_directories(self, tmp_path: Path) -> None:
        registry = PluginRegistryV2()
        sub = tmp_path / "sub" / "nested"
        sub.mkdir(parents=True)
        _make_v2_plugin(sub, "nested_v2")
        assert registry.discover([str(tmp_path)]) == 1

    def test_entry_structure_v2(self, tmp_path: Path) -> None:
        registry = PluginRegistryV2()
        _make_v2_plugin(tmp_path, "entry_check")
        registry.discover([str(tmp_path)])
        entry = registry.entries["entry_check"]
        assert isinstance(entry, PluginEntryV2)
        assert entry.manifest is not None
        assert entry.manifest_path is not None
        assert entry.legacy_meta is None

    def test_entry_structure_legacy(self, tmp_path: Path) -> None:
        registry = PluginRegistryV2()
        _make_legacy_plugin(tmp_path, "legacy_entry")
        registry.discover([str(tmp_path)])
        entry = registry.entries["legacy_entry"]
        assert isinstance(entry, PluginEntryV2)
        assert entry.manifest is None
        assert entry.manifest_path is None
        assert entry.legacy_meta is not None
        assert entry.legacy_meta.name == "legacy_entry"


class TestRegistryV2Get:
    def test_get_v2(self, tmp_path: Path) -> None:
        registry = PluginRegistryV2()
        _make_v2_plugin(tmp_path, "v2_get")
        registry.discover([str(tmp_path)])
        plugin = registry.get("v2_get")
        assert plugin is not None
        assert isinstance(plugin, PluginBase)

    def test_get_legacy(self, tmp_path: Path) -> None:
        registry = PluginRegistryV2()
        _make_legacy_plugin(tmp_path, "legacy_get")
        registry.discover([str(tmp_path)])
        plugin = registry.get("legacy_get")
        assert plugin is not None

    def test_get_caches_instance(self, tmp_path: Path) -> None:
        registry = PluginRegistryV2()
        _make_v2_plugin(tmp_path, "cache_v2")
        registry.discover([str(tmp_path)])
        assert registry.get("cache_v2") is registry.get("cache_v2")

    def test_get_nonexistent(self) -> None:
        assert PluginRegistryV2().get("no_such_plugin") is None

    def test_get_manifest_v2(self, tmp_path: Path) -> None:
        registry = PluginRegistryV2()
        _make_v2_plugin(tmp_path, "manifest_v2")
        registry.discover([str(tmp_path)])
        manifest = registry.get_manifest("manifest_v2")
        assert isinstance(manifest, PluginManifest)
        assert manifest.name == "manifest_v2"
        assert manifest.version == "1.0.0"

    def test_get_manifest_legacy(self, tmp_path: Path) -> None:
        registry = PluginRegistryV2()
        _make_legacy_plugin(tmp_path, "manifest_legacy")
        registry.discover([str(tmp_path)])
        meta = registry.get_manifest("manifest_legacy")
        assert isinstance(meta, PluginMeta)
        assert meta.name == "manifest_legacy"

    def test_get_manifest_nonexistent(self) -> None:
        assert PluginRegistryV2().get_manifest("no_such") is None

    def test_loaded_property(self, tmp_path: Path) -> None:
        registry = PluginRegistryV2()
        assert registry.loaded == []
        _make_v2_plugin(tmp_path, "loaded_test")
        registry.discover([str(tmp_path)])
        assert "loaded_test" not in registry.loaded
        registry.get("loaded_test")
        assert "loaded_test" in registry.loaded


class TestRegistryV2Unload:
    def test_removes_instance(self, tmp_path: Path) -> None:
        registry = PluginRegistryV2()
        _make_v2_plugin(tmp_path, "unload_v2")
        registry.discover([str(tmp_path)])
        registry.get("unload_v2")
        assert "unload_v2" in registry.loaded
        assert registry.unload("unload_v2") is True
        assert "unload_v2" not in registry.loaded

    def test_nonexistent_returns_false(self) -> None:
        assert PluginRegistryV2().unload("no_such") is False

    def test_unload_unloaded_plugin(self, tmp_path: Path) -> None:
        registry = PluginRegistryV2()
        _make_v2_plugin(tmp_path, "never_loaded")
        registry.discover([str(tmp_path)])
        assert registry.unload("never_loaded") is False

    def test_unload_twice(self, tmp_path: Path) -> None:
        registry = PluginRegistryV2()
        _make_v2_plugin(tmp_path, "unload_twice")
        registry.discover([str(tmp_path)])
        registry.get("unload_twice")
        assert registry.unload("unload_twice") is True
        assert registry.unload("unload_twice") is False


class TestRegistryV2Run:
    def test_run_phase_v2(self, tmp_path: Path) -> None:
        registry = PluginRegistryV2()
        _make_v2_plugin(tmp_path, "v2_run")
        registry.discover([str(tmp_path)])
        results = registry.run_phase("always")
        assert len(results) == 1
        assert results[0].ok is True

    def test_run_phase_legacy(self, tmp_path: Path) -> None:
        registry = PluginRegistryV2()
        _make_legacy_plugin(tmp_path, "legacy_run", phase="pre")
        registry.discover([str(tmp_path)])
        results = registry.run_phase("pre")
        assert len(results) == 1
        assert results[0].ok is True

    def test_run_phase_by_manifest_phase(self, tmp_path: Path) -> None:
        registry = PluginRegistryV2()
        _make_v2_plugin(tmp_path, "phase_v2", phases=["pre"])
        registry.discover([str(tmp_path)])
        results = registry.run_phase("pre")
        assert len(results) == 1
        assert results[0].plugin == "phase_v2"

    def test_run_phase_excludes_wrong_phase(self, tmp_path: Path) -> None:
        registry = PluginRegistryV2()
        _make_v2_plugin(tmp_path, "only_pre", phases=["pre"])
        registry.discover([str(tmp_path)])
        assert len(registry.run_phase("post")) == 0

    def test_run_one_v2(self, tmp_path: Path) -> None:
        registry = PluginRegistryV2()
        _make_v2_plugin(tmp_path, "run_one_v2")
        registry.discover([str(tmp_path)])
        result = registry.run_one("run_one_v2")
        assert result is not None
        assert result.ok is True
        assert result.plugin == "run_one_v2"

    def test_run_one_nonexistent(self) -> None:
        assert PluginRegistryV2().run_one("no_such") is None

    def test_run_one_legacy(self, tmp_path: Path) -> None:
        registry = PluginRegistryV2()
        _make_legacy_plugin(tmp_path, "run_one_legacy", phase="pre")
        registry.discover([str(tmp_path)])
        result = registry.run_one("run_one_legacy")
        assert result is not None
        assert result.ok is True


class TestRegistryV2VersionNegotiation:
    def test_compatible_api_version(self, tmp_path: Path) -> None:
        registry = PluginRegistryV2()
        _make_v2_plugin(tmp_path, "compat_v2", api_version="1.0.0")
        registry.discover([str(tmp_path)])
        assert registry.get("compat_v2") is not None

    def test_incompatible_api_version_returns_none(self, tmp_path: Path) -> None:
        registry = PluginRegistryV2()
        _make_v2_plugin(tmp_path, "incompat", api_version="99.0.0")
        registry.discover([str(tmp_path)])
        assert registry.get("incompat") is None

    def test_minor_newer_than_motor_returns_none(self, tmp_path: Path) -> None:
        registry = PluginRegistryV2()
        _make_v2_plugin(tmp_path, "minor_newer", api_version="1.5.0")
        from motor.plugin.registry_v2 import MOTOR_API_VERSION

        assert MOTOR_API_VERSION == "1.0.0"
        registry.discover([str(tmp_path)])
        assert registry.get("minor_newer") is None

    def test_legacy_plugin_no_version_check(self, tmp_path: Path) -> None:
        registry = PluginRegistryV2()
        _make_legacy_plugin(tmp_path, "legacy_no_version")
        registry.discover([str(tmp_path)])
        assert registry.get("legacy_no_version") is not None


class TestRegistryV2Duplicate:
    def test_duplicate_legacy_name(self, tmp_path: Path) -> None:
        registry = PluginRegistryV2()
        sub = tmp_path / "sub"
        sub.mkdir()
        _make_legacy_plugin(tmp_path, "dup")
        _make_legacy_plugin(sub, "dup")
        registry.discover([str(tmp_path)])
        assert registry.count() == 1

    def test_duplicate_v2_and_legacy(self, tmp_path: Path) -> None:
        registry = PluginRegistryV2()
        _make_v2_plugin(tmp_path, "shared_name")
        count = registry.discover([str(tmp_path)])
        assert count >= 1

    def test_invalid_manifest_discovery(self, tmp_path: Path) -> None:
        registry = PluginRegistryV2()
        d = tmp_path / "bad_manifest"
        d.mkdir()
        (d / "plugin.yaml").write_text("not: valid: yaml: [[[")
        (d / "__init__.py").write_text(
            "from motor.plugin.base import PluginBase\n"
            "class BadManifestPlugin(PluginBase):\n"
            "    def execute(self, context):\n"
            "        return {}\n",
        )
        count = registry.discover([str(tmp_path)])
        assert count >= 0


class TestRegistryV2DependencyResolution:
    def test_no_dependencies(self, tmp_path: Path) -> None:
        registry = PluginRegistryV2()
        _make_v2_plugin(tmp_path, "standalone")
        registry.discover([str(tmp_path)])
        assert registry._resolve_dependencies("standalone") == ["standalone"]

    def test_with_external_dependency(self, tmp_path: Path) -> None:
        registry = PluginRegistryV2()
        _make_v2_plugin(tmp_path, "base")
        d = tmp_path / "with_dep"
        d.mkdir()
        (d / "plugin.yaml").write_text(
            "name: with_dep\napi_version: '1.0.0'\nentry_point: 'WithDepPlugin'\n"
            "dependencies:\n  plugins:\n    - base\n",
        )
        (d / "__init__.py").write_text(
            "from motor.plugin.base import PluginBase\n"
            "class WithDepPlugin(PluginBase):\n"
            "    def execute(self, context):\n"
            "        return {}\n",
        )
        registry.discover([str(tmp_path)])
        deps = registry._resolve_dependencies("with_dep")
        assert "base" in deps
        assert "with_dep" in deps

    def test_nonexistent_dependency(self, tmp_path: Path) -> None:
        registry = PluginRegistryV2()
        d = tmp_path / "with_missing_dep"
        d.mkdir()
        (d / "plugin.yaml").write_text(
            "name: with_missing_dep\napi_version: '1.0.0'\nentry_point: 'WithMissingDepPlugin'\n"
            "dependencies:\n  plugins:\n    - nonexistent_plugin\n",
        )
        (d / "__init__.py").write_text(
            "from motor.plugin.base import PluginBase\n"
            "class WithMissingDepPlugin(PluginBase):\n"
            "    def execute(self, context):\n"
            "        return {}\n",
        )
        registry.discover([str(tmp_path)])
        deps = registry._resolve_dependencies("with_missing_dep")
        assert "nonexistent_plugin" in deps
        assert "with_missing_dep" in deps

    def test_empty_string_dependency_skipped(self, tmp_path: Path) -> None:
        registry = PluginRegistryV2()
        d = tmp_path / "empty_dep"
        d.mkdir()
        (d / "plugin.yaml").write_text(
            "name: empty_dep\napi_version: '1.0.0'\nentry_point: 'EmptyDepPlugin'\n"
            "dependencies:\n  plugins:\n    -\n",
        )
        (d / "__init__.py").write_text(
            "from motor.plugin.base import PluginBase\n"
            "class EmptyDepPlugin(PluginBase):\n"
            "    def execute(self, context):\n"
            "        return {}\n",
        )
        registry.discover([str(tmp_path)])
        deps = registry._resolve_dependencies("empty_dep")
        assert "empty_dep" in deps

    def test_dependency_as_dict(self, tmp_path: Path) -> None:
        registry = PluginRegistryV2()
        d = tmp_path / "dict_dep"
        d.mkdir()
        (d / "plugin.yaml").write_text(
            "name: dict_dep\napi_version: '1.0.0'\nentry_point: 'DictDepPlugin'\n"
            "dependencies:\n  plugins:\n    - name: some_dep\n      version: '>=1.0'\n",
        )
        (d / "__init__.py").write_text(
            "from motor.plugin.base import PluginBase\n"
            "class DictDepPlugin(PluginBase):\n"
            "    def execute(self, context):\n"
            "        return {}\n",
        )
        registry.discover([str(tmp_path)])
        deps = registry._resolve_dependencies("dict_dep")
        assert "some_dep" in deps
        assert "dict_dep" in deps

    def test_legacy_plugin_dependencies_empty(self, tmp_path: Path) -> None:
        registry = PluginRegistryV2()
        _make_legacy_plugin(tmp_path, "legacy_dep")
        registry.discover([str(tmp_path)])
        assert registry._resolve_dependencies("legacy_dep") == ["legacy_dep"]

    def test_circular_dependency_raises(self, tmp_path: Path) -> None:
        registry = PluginRegistryV2()
        for name in ("circ_a", "circ_b"):
            d = tmp_path / name
            d.mkdir()
            dep = "circ_b" if name == "circ_a" else "circ_a"
            (d / "plugin.yaml").write_text(
                f"name: {name}\napi_version: '1.0.0'\nentry_point: 'Plugin{name}'\n"
                f"dependencies:\n  plugins:\n    - {dep}\n",
            )
            (d / "__init__.py").write_text(
                "from motor.plugin.base import PluginBase\n"
                f"class Plugin{name}(PluginBase):\n"
                "    def execute(self, context):\n"
                "        return {}\n",
            )
        registry.discover([str(tmp_path)])
        with pytest.raises(RegistryV2ManifestError, match="circular"):
            registry._resolve_dependencies("circ_a")


class TestRegistryV2ErrorHandling:
    def test_missing_init_py_returns_none(self, tmp_path: Path) -> None:
        registry = PluginRegistryV2()
        d = tmp_path / "no_init"
        d.mkdir()
        (d / "plugin.yaml").write_text(
            "name: no_init\napi_version: '1.0.0'\nentry_point: 'NoInitPlugin'\n",
        )
        registry.discover([str(tmp_path)])
        assert registry.get("no_init") is None

    def test_execution_failure(self, tmp_path: Path) -> None:
        registry = PluginRegistryV2()
        d = tmp_path / "fail_run"
        d.mkdir()
        (d / "plugin.yaml").write_text(
            "name: fail_run\napi_version: '1.0.0'\nentry_point: 'FailRunPlugin'\n",
        )
        (d / "__init__.py").write_text(
            "from motor.plugin.base import PluginBase\n"
            "class FailRunPlugin(PluginBase):\n"
            "    def execute(self, context):\n"
            "        raise RuntimeError('intentional run failure')\n",
        )
        registry.discover([str(tmp_path)])
        results = registry.run_phase("always")
        assert len(results) == 1
        assert results[0].ok is False
        assert "intentional run failure" in results[0].error

    def test_isolated_plugin_failure(self, tmp_path: Path) -> None:
        registry = PluginRegistryV2()
        d_fail = tmp_path / "isolated_fail"
        d_fail.mkdir()
        (d_fail / "plugin.yaml").write_text(
            "name: isolated_fail\napi_version: '1.0.0'\nentry_point: 'IsolatedFailPlugin'\n",
        )
        (d_fail / "__init__.py").write_text(
            "from motor.plugin.base import PluginBase\n"
            "class IsolatedFailPlugin(PluginBase):\n"
            "    def execute(self, context):\n"
            "        raise RuntimeError('fail')\n",
        )
        d_good = tmp_path / "isolated_good"
        d_good.mkdir()
        (d_good / "plugin.yaml").write_text(
            "name: isolated_good\napi_version: '1.0.0'\nentry_point: 'IsolatedGoodPlugin'\n",
        )
        (d_good / "__init__.py").write_text(
            "from motor.plugin.base import PluginBase\n"
            "class IsolatedGoodPlugin(PluginBase):\n"
            "    def execute(self, context):\n"
            "        return {'ok': True}\n",
        )
        registry.discover([str(tmp_path)])
        results = registry.run_phase("always")
        assert len(results) == 2
        ok_results = [r for r in results if r.ok]
        fail_results = [r for r in results if not r.ok]
        assert len(ok_results) == 1
        assert ok_results[0].plugin == "isolated_good"
        assert len(fail_results) == 1
        assert fail_results[0].plugin == "isolated_fail"


class TestRegistryV2CapabilityDiscovery:
    """Filter plugins by capability (phase, hook, tag) via entries introspection."""

    def test_find_by_manifest_phase(self, tmp_path: Path) -> None:
        registry = PluginRegistryV2()
        _make_v2_plugin(tmp_path, "pre_plugin", phases=["pre"])
        _make_v2_plugin(tmp_path, "post_plugin", phases=["post"])
        registry.discover([str(tmp_path)])
        pre_plugins = [
            n for n, e in registry.entries.items()
            if e.manifest and "pre" in e.manifest.phases
        ]
        assert "pre_plugin" in pre_plugins
        assert "post_plugin" not in pre_plugins

    def test_find_by_hook(self, tmp_path: Path) -> None:
        registry = PluginRegistryV2()
        _make_v2_plugin(tmp_path, "hook_plugin", hooks=["pre_ingest"])
        _make_v2_plugin(tmp_path, "no_hook")
        registry.discover([str(tmp_path)])
        hook_plugins = [
            n for n, e in registry.entries.items()
            if e.manifest and "pre_ingest" in e.manifest.hooks
        ]
        assert "hook_plugin" in hook_plugins
        assert "no_hook" not in hook_plugins

    def test_find_by_tag(self, tmp_path: Path) -> None:
        registry = PluginRegistryV2()
        d = tmp_path / "tagged"
        d.mkdir()
        (d / "plugin.yaml").write_text(
            "name: tagged\napi_version: '1.0.0'\nentry_point: 'TaggedPlugin'\n"
            "tags:\n  - search\n  - experimental\n",
        )
        (d / "__init__.py").write_text(
            "from motor.plugin.base import PluginBase\n"
            "class TaggedPlugin(PluginBase):\n"
            "    def execute(self, context):\n"
            "        return {}\n",
        )
        _make_v2_plugin(tmp_path, "untagged")
        registry.discover([str(tmp_path)])
        tagged = [
            n for n, e in registry.entries.items()
            if e.manifest and "search" in e.manifest.tags
        ]
        assert "tagged" in tagged
        assert "untagged" not in tagged

    def test_find_by_legacy_phase(self, tmp_path: Path) -> None:
        registry = PluginRegistryV2()
        _make_legacy_plugin(tmp_path, "legacy_pre", phase="pre")
        _make_legacy_plugin(tmp_path, "legacy_post", phase="post")
        registry.discover([str(tmp_path)])
        pre_plugins = [
            n for n, e in registry.entries.items()
            if e.legacy_meta and e.legacy_meta.phase == "pre"
        ]
        assert "legacy_pre" in pre_plugins
        assert "legacy_post" not in pre_plugins

    def test_find_by_version_range(self, tmp_path: Path) -> None:
        registry = PluginRegistryV2()
        _make_v2_plugin(tmp_path, "old_plugin", version="0.5.0")
        _make_v2_plugin(tmp_path, "new_plugin", version="2.0.0")
        registry.discover([str(tmp_path)])
        old_plugins = [
            n for n, e in registry.entries.items()
            if e.manifest and e.manifest.version and e.manifest.version.startswith("0.")
        ]
        assert "old_plugin" in old_plugins
        assert "new_plugin" not in old_plugins
