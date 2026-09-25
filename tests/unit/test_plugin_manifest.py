from __future__ import annotations
import pytest

from typing import TYPE_CHECKING

from motor.plugin.manifest import (
    PluginManifest,
    find_manifest,
    parse_manifest,
)

if TYPE_CHECKING:
    from pathlib import Path


class TestParseManifest:
    @pytest.mark.unit
    def test_parse_valid_yaml(self, tmp_path: Path):
        f = tmp_path / "plugin.yaml"
        f.write_text("name: test-plugin\nversion: '1.0.0'\napi_version: '1.0.0'\n")
        manifest = parse_manifest(f)
        assert manifest is not None
        assert manifest.name == "test-plugin"
        assert manifest.version == "1.0.0"
        assert manifest.api_version == "1.0.0"

    @pytest.mark.unit
    def test_parse_valid_json(self, tmp_path: Path):
        f = tmp_path / "plugin.json"
        f.write_text('{"name": "json-plugin", "version": "2.0.0", "api_version": "1.0.0"}')
        manifest = parse_manifest(f)
        assert manifest is not None
        assert manifest.name == "json-plugin"
        assert manifest.version == "2.0.0"

    @pytest.mark.unit
    def test_parse_missing_file(self, tmp_path: Path):
        manifest = parse_manifest(tmp_path / "nonexistent.yaml")
        assert manifest is None

    @pytest.mark.unit
    def test_parse_empty_yaml(self, tmp_path: Path):
        f = tmp_path / "plugin.yaml"
        f.write_text("")
        manifest = parse_manifest(f)
        assert manifest is None  # YAML vacío no produce dict válido

    @pytest.mark.unit
    def test_parse_with_defaults(self, tmp_path: Path):
        f = tmp_path / "plugin.yaml"
        f.write_text("name: defaults-test\n")
        manifest = parse_manifest(f)
        assert manifest is not None
        assert manifest.api_version == "1.0.0"
        assert manifest.version == "0.1.0"
        assert manifest.phases == ["always"]
        assert manifest.hooks == []
        assert manifest.tags == []

    @pytest.mark.unit
    def test_parse_with_hooks(self, tmp_path: Path):
        f = tmp_path / "plugin.yaml"
        f.write_text("name: hook-test\nhooks:\n  - pre_ingest\n  - post_search\n")
        manifest = parse_manifest(f)
        assert manifest is not None
        assert "pre_ingest" in manifest.hooks
        assert "post_search" in manifest.hooks

    @pytest.mark.unit
    def test_parse_with_dependencies(self, tmp_path: Path):
        f = tmp_path / "plugin.yaml"
        f.write_text(
            "name: dep-test\ndependencies:\n  plugins:\n    - name: base\n      version: '>=1.0.0'\n  python:\n    - 'requests>=2.28'\n",
        )
        manifest = parse_manifest(f)
        assert manifest is not None
        assert manifest.dependencies["plugins"][0]["name"] == "base"
        assert "requests" in manifest.dependencies["python"][0]

    @pytest.mark.unit
    def test_parse_invalid_yaml(self, tmp_path: Path):
        f = tmp_path / "plugin.yaml"
        f.write_text("name: [invalid\n")
        manifest = parse_manifest(f)
        assert manifest is None

    @pytest.mark.unit
    def test_parse_unsupported_format(self, tmp_path: Path):
        f = tmp_path / "plugin.toml"
        f.write_text("[plugin]\nname = 'test'\n")
        manifest = parse_manifest(f)
        assert manifest is None


class TestFindManifest:
    @pytest.mark.unit
    def test_find_yaml(self, tmp_path: Path):
        f = tmp_path / "plugin.yaml"
        f.write_text("name: test\n")
        found = find_manifest(tmp_path)
        assert found == f

    @pytest.mark.unit
    def test_find_yml(self, tmp_path: Path):
        f = tmp_path / "plugin.yml"
        f.write_text("name: test\n")
        found = find_manifest(tmp_path)
        assert found == f

    @pytest.mark.unit
    def test_find_json(self, tmp_path: Path):
        f = tmp_path / "plugin.json"
        f.write_text('{"name": "test"}')
        found = find_manifest(tmp_path)
        assert found == f

    @pytest.mark.unit
    def test_find_prioritizes_yaml(self, tmp_path: Path):
        yaml_f = tmp_path / "plugin.yaml"
        json_f = tmp_path / "plugin.json"
        yaml_f.write_text("name: yaml\n")
        json_f.write_text('{"name": "json"}')
        found = find_manifest(tmp_path)
        assert found == yaml_f

    @pytest.mark.unit
    def test_find_nonexistent(self, tmp_path: Path):
        found = find_manifest(tmp_path)
        assert found is None


class TestPluginManifestDefaults:
    @pytest.mark.unit
    def test_default_manifest(self):
        m = PluginManifest(name="test")
        assert m.api_version == "1.0.0"
        assert m.version == "0.1.0"
        assert m.description == ""
        assert m.author == {}
        assert m.dependencies == {"plugins": [], "python": []}
        assert m.hooks == []
        assert m.phases == ["always"]
        assert m.tags == []
