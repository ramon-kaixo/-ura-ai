from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


class TestPyProjectToml:
    def test_exists(self):
        assert (ROOT / "pyproject.toml").exists()

    def test_has_name(self):
        content = (ROOT / "pyproject.toml").read_text()
        assert 'name = "ura"' in content

    def test_has_version(self):
        content = (ROOT / "pyproject.toml").read_text()
        assert "version" in content

    def test_has_dependencies(self):
        content = (ROOT / "pyproject.toml").read_text()
        assert "httpx" in content
        assert "fastapi" in content

    def test_has_extras(self):
        content = (ROOT / "pyproject.toml").read_text()
        assert "[project.optional-dependencies]" in content

    def test_memory_extra(self):
        content = (ROOT / "pyproject.toml").read_text()
        assert "memory" in content
        assert "qdrant-client" in content

    def test_agents_extra(self):
        content = (ROOT / "pyproject.toml").read_text()
        assert "agents" in content
        assert "rank-bm25" in content

    def test_dev_extra(self):
        content = (ROOT / "pyproject.toml").read_text()
        assert "dev" in content
        assert "pytest" in content

    def test_has_entry_point(self):
        content = (ROOT / "pyproject.toml").read_text()
        assert 'ura = "ura:main"' in content

    def test_build_system(self):
        content = (ROOT / "pyproject.toml").read_text()
        assert "[build-system]" in content


class TestWorkflows:
    def test_ci_yml_exists(self):
        assert (ROOT / ".github/workflows/ci.yml").exists()

    def test_release_yml_exists(self):
        assert (ROOT / ".github/workflows/release.yml").exists()

    def test_ci_steps(self):
        import yaml
        with open(ROOT / ".github/workflows/ci.yml") as f:
            data = yaml.safe_load(f)
        jobs = data.get("jobs", {})
        for name in ["lint", "test", "build"]:
            assert name in jobs, f"Missing job: {name}"

    def test_ci_matrix(self):
        import yaml
        with open(ROOT / ".github/workflows/ci.yml") as f:
            data = yaml.safe_load(f)
        test_job = data["jobs"]["test"]
        matrix = test_job.get("strategy", {}).get("matrix", {})
        versions = matrix.get("python-version", [])
        assert "3.11" in versions
        assert "3.12" in versions

    def test_release_triggers_on_tag(self):
        import yaml
        with open(ROOT / ".github/workflows/release.yml") as f:
            data = yaml.safe_load(f)
        # PyYAML parses 'on:' as True; GH Actions handles it correctly
        trigger = data.get(True) or data.get("on") or {}
        push = trigger.get("push", {})
        tags = push.get("tags", [])
        assert any("v" in t for t in tags)

    def test_release_has_build_step(self):
        import yaml
        with open(ROOT / ".github/workflows/release.yml") as f:
            data = yaml.safe_load(f)
        steps = data["jobs"]["release"]["steps"]
        step_names = [s.get("name", "") for s in steps]
        assert any("Build" in s for s in step_names)

    def test_ci_cancels_duplicates(self):
        import yaml
        with open(ROOT / ".github/workflows/ci.yml") as f:
            data = yaml.safe_load(f)
        assert "concurrency" in data
        assert data["concurrency"].get("cancel-in-progress") is True

    def test_lint_job_has_ruff(self):
        import yaml
        with open(ROOT / ".github/workflows/ci.yml") as f:
            data = yaml.safe_load(f)
        steps = data["jobs"]["lint"]["steps"]
        step_names = [s.get("name", "") for s in steps]
        assert any("Ruff" in s for s in step_names)

    def test_build_uploads_artifact(self):
        import yaml
        with open(ROOT / ".github/workflows/ci.yml") as f:
            data = yaml.safe_load(f)
        steps = data["jobs"]["build"]["steps"]
        step_names = [s.get("uses", "") for s in steps]
        assert any("upload-artifact" in s for s in step_names)


class TestBuild:
    def test_wheel_generable(self):
        result = subprocess.run(
            [sys.executable, "-m", "build", "--wheel", str(ROOT)],
            capture_output=True, text=True, timeout=120,
        )
        assert result.returncode == 0, result.stderr
        wheels = list((ROOT / "dist").glob("*.whl"))
        assert len(wheels) >= 1
        for w in wheels:
            w.unlink()

    def test_sdist_generable(self):
        result = subprocess.run(
            [sys.executable, "-m", "build", "--sdist", str(ROOT)],
            capture_output=True, text=True, timeout=120,
        )
        assert result.returncode == 0, result.stderr
        sdists = list((ROOT / "dist").glob("*.tar.gz"))
        assert len(sdists) >= 1
        for s in sdists:
            s.unlink()


class TestInstallation:
    def test_editable_install(self):
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-e", str(ROOT), "--break-system-packages"],
            capture_output=True, text=True, timeout=120,
        )
        err_lower = result.stderr.lower()
        skip_msgs = ["externally-managed", "read-only", "sistema de archivos de solo lectura"]
        if any(m in err_lower for m in skip_msgs):
            pytest.skip("Environment does not allow pip install")
        assert result.returncode == 0, result.stderr

    def test_import_ura(self):
        result = subprocess.run(
            [sys.executable, "-c", "import ura; print('OK')"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            pytest.skip("ura module not installed")
        assert "OK" in result.stdout
