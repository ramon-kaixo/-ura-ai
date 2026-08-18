"""Tests de cobertura de motor/pipeline/loader.py (PipelineLoader)."""

from __future__ import annotations

import pytest

from motor.pipeline.definition import PipelineDefinition
from motor.pipeline.loader import PipelineLoader


def _registry(manifests: dict[str, object] | None = None):
    class _R:
        def get_manifest(self, name: str):
            return (manifests or {}).get(name)

    return _R()


class TestLoad:
    def test_yaml(self, tmp_path) -> None:
        p = tmp_path / "pipe.yaml"
        p.write_text("name: mi-pipe\nversion: '1.0'\nstages:\n  - name: s1\n    plugin: p1\n")
        pipe = PipelineLoader(_registry({"p1": {}})).load(p)
        assert pipe.name == "mi-pipe"
        assert len(pipe.stages) == 1
        assert pipe.stages[0].name == "s1"

    def test_yml(self, tmp_path) -> None:
        p = tmp_path / "pipe.yml"
        p.write_text("name: x\nstages: []\n")
        pipe = PipelineLoader(_registry()).load(p)
        assert pipe.name == "x"

    def test_json(self, tmp_path) -> None:
        p = tmp_path / "pipe.json"
        p.write_text('{"name": "j", "stages": [{"name": "a", "plugin": "p", "timeout": 60}]}')
        pipe = PipelineLoader(_registry({"p": {}})).load(p)
        assert pipe.name == "j"
        assert pipe.stages[0].timeout == 60

    def test_formato_no_soportado(self, tmp_path) -> None:
        p = tmp_path / "pipe.txt"
        p.write_text("x")
        with pytest.raises(ValueError, match="not supported"):
            PipelineLoader(_registry()).load(p)

    def test_no_dict(self, tmp_path) -> None:
        p = tmp_path / "pipe.yaml"
        p.write_text("- a\n- b\n")
        with pytest.raises(ValueError, match="must be a dict"):
            PipelineLoader(_registry()).load(p)


class TestFromDict:
    def test_defaults(self) -> None:
        pipe = PipelineLoader(_registry())._from_dict({"name": "n"})
        assert pipe.version == ""
        assert pipe.description == ""
        assert pipe.stages == []

    def test_stage_defaults(self) -> None:
        pipe = PipelineLoader(_registry())._from_dict(
            {"name": "n", "stages": [{"name": "s", "plugin": "p"}]}
        )
        s = pipe.stages[0]
        assert s.config == {}
        assert s.timeout == 30
        assert s.optional is False


class TestValidate:
    def test_ok(self) -> None:
        pipe = PipelineDefinition(
            name="n",
            version="1",
            description="",
            stages=[],
        )
        pipe = PipelineLoader(_registry({"p": {}}))._from_dict(
            {"name": "n", "stages": [{"name": "s", "plugin": "p"}]}
        )
        assert PipelineLoader(_registry({"p": {}})).validate(pipe) == []

    def test_sin_nombre(self) -> None:
        pipe = PipelineLoader(_registry())._from_dict({"stages": [{"name": "s", "plugin": "p"}]})
        errors = PipelineLoader(_registry({"p": {}})).validate(pipe)
        assert "Pipeline name is required" in errors

    def test_sin_stages(self) -> None:
        pipe = PipelineLoader(_registry())._from_dict({"name": "n"})
        errors = PipelineLoader(_registry()).validate(pipe)
        assert "At least one stage is required" in errors
        assert len(errors) == 1  # return temprano

    def test_stage_sin_nombre_y_plugin(self) -> None:
        pipe = PipelineLoader(_registry())._from_dict({"name": "n", "stages": [{}]})
        errors = PipelineLoader(_registry()).validate(pipe)
        assert "Stage name is required" in errors
        assert any("plugin is required" in e for e in errors)

    def test_nombres_duplicados(self) -> None:
        pipe = PipelineLoader(_registry({"p": {}}))._from_dict(
            {"name": "n", "stages": [{"name": "s", "plugin": "p"}, {"name": "s", "plugin": "p"}]}
        )
        errors = PipelineLoader(_registry({"p": {}})).validate(pipe)
        assert any("Duplicate stage name" in e for e in errors)

    def test_plugin_no_encontrado(self) -> None:
        pipe = PipelineLoader(_registry())._from_dict({"name": "n", "stages": [{"name": "s", "plugin": "ghost"}]})
        errors = PipelineLoader(_registry()).validate(pipe)
        assert any("not found in registry" in e for e in errors)
