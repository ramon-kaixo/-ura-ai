"""Tests de infraestructura — Docker, scripts, configuración."""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


class TestDockerfile:
    def test_exists(self):
        assert (ROOT / "Dockerfile").exists()

    def test_uses_slim_image(self):
        content = (ROOT / "Dockerfile").read_text()
        assert "python:3.12-slim" in content

    def test_non_root_user(self):
        content = (ROOT / "Dockerfile").read_text()
        assert "useradd" in content or "adduser" in content or "USER" in content

    def has_healthcheck(self):
        content = (ROOT / "Dockerfile").read_text()
        assert "HEALTHCHECK" in content

    def test_entrypoint_defined(self):
        content = (ROOT / "Dockerfile").read_text()
        assert "ENTRYPOINT" in content

    def test_environment_vars(self):
        content = (ROOT / "Dockerfile").read_text()
        assert "URA_OLLAMA_URL" in content
        assert "URA_QDRANT_URL" in content


class TestDockerIgnore:
    def test_exists(self):
        assert (ROOT / ".dockerignore").exists()

    def test_excludes_venv(self):
        content = (ROOT / ".dockerignore").read_text()
        assert ".venv" in content or "venv" in content

    def test_excludes_pycache(self):
        content = (ROOT / ".dockerignore").read_text()
        assert "__pycache__" in content


class TestDockerCompose:
    def test_exists(self):
        assert (ROOT / "docker-compose.yml").exists()

    def test_has_ura_service(self):
        import yaml
        with open(ROOT / "docker-compose.yml") as f:
            cfg = yaml.safe_load(f)
        assert "ura" in cfg.get("services", {})

    def test_has_qdrant(self):
        import yaml
        with open(ROOT / "docker-compose.yml") as f:
            cfg = yaml.safe_load(f)
        assert "qdrant" in cfg.get("services", {})

    def test_has_ollama_profile(self):
        import yaml
        with open(ROOT / "docker-compose.yml") as f:
            cfg = yaml.safe_load(f)
        ollama = cfg.get("services", {}).get("ollama", {})
        assert ollama.get("profiles") == ["ollama"]

    def test_persistent_volumes(self):
        import yaml
        with open(ROOT / "docker-compose.yml") as f:
            cfg = yaml.safe_load(f)
        volumes = cfg.get("volumes", {})
        assert "qdrant_data" in volumes
        assert "ura_data" in volumes

    def test_network_defined(self):
        import yaml
        with open(ROOT / "docker-compose.yml") as f:
            cfg = yaml.safe_load(f)
        assert "ura_net" in cfg.get("networks", {})

    def test_healthcheck_qdrant(self):
        import yaml
        with open(ROOT / "docker-compose.yml") as f:
            cfg = yaml.safe_load(f)
        qdrant = cfg["services"]["qdrant"]
        assert "healthcheck" in qdrant

    def test_env_vars_structured(self):
        import yaml
        with open(ROOT / "docker-compose.yml") as f:
            cfg = yaml.safe_load(f)
        ura = cfg["services"]["ura"]
        env = ura.get("environment", {}) or {}
        assert "URA_OLLAMA_URL" in str(env) or any("OLLAMA" in str(e) for e in (env if isinstance(env, list) else [env]))


class TestEnvExample:
    def test_exists(self):
        assert (ROOT / ".env.example").exists()

    def test_has_key_vars(self):
        content = (ROOT / ".env.example").read_text()
        assert "URA_PORT" in content
        assert "URA_OLLAMA_URL" in content
        assert "URA_QDRANT_URL" in content

    def test_gpu_flag(self):
        content = (ROOT / ".env.example").read_text()
        assert "GPU" in content


class TestInstallScript:
    def test_exists(self):
        assert (ROOT / "install.sh").exists()

    def test_is_executable(self):
        st = os.stat(ROOT / "install.sh")
        assert st.st_mode & stat.S_IXUSR

    def test_has_shebang(self):
        content = (ROOT / "install.sh").read_text()
        assert content.startswith("#!/usr/bin/env bash")

    def test_idempotent_comment(self):
        content = (ROOT / "install.sh").read_text()
        assert "idempotent" in content.lower()

    def test_checks_python(self):
        content = (ROOT / "install.sh").read_text()
        assert "python" in content.lower()

    def test_creates_venv(self):
        content = (ROOT / "install.sh").read_text()
        assert "venv" in content

    def test_generates_env(self):
        content = (ROOT / "install.sh").read_text()
        assert ".env" in content

    def test_no_absolute_paths(self):
        content = (ROOT / "install.sh").read_text()
        for line in content.splitlines():
            if line.strip().startswith("/") and not line.strip().startswith("#!/"):
                assert False, f"Absolute path found: {line.strip()}"


class TestEntrypointScript:
    def test_exists(self):
        assert (ROOT / "entrypoint.sh").exists()

    def test_is_executable(self):
        st = os.stat(ROOT / "entrypoint.sh")
        assert st.st_mode & stat.S_IXUSR

    def test_has_shebang(self):
        content = (ROOT / "entrypoint.sh").read_text()
        assert content.startswith("#!/usr/bin/env bash")

    def test_waits_for_qdrant(self):
        content = (ROOT / "entrypoint.sh").read_text()
        assert "Qdrant" in content

    def test_handles_sigterm(self):
        content = (ROOT / "entrypoint.sh").read_text()
        assert "SIGTERM" in content or "cleanup" in content

    def test_checks_ollama_optionally(self):
        content = (ROOT / "entrypoint.sh").read_text()
        assert "Ollama" in content

    def test_configurable_host_port(self):
        content = (ROOT / "entrypoint.sh").read_text()
        assert "URA_HOST" in content
        assert "URA_PORT" in content

    def test_no_hardcoded_credentials(self):
        content = (ROOT / "entrypoint.sh").read_text()
        assert "password" not in content.lower()
        assert "secret" not in content.lower()


class TestBootstrap:
    def test_hardware_portability(self):
        """Verify no GPU/CUDA assumptions in Docker or compose."""
        compose = (ROOT / "docker-compose.yml").read_text()
        assert "nvidia" not in compose or "reservations" in compose
        dockerfile = (ROOT / "Dockerfile").read_text()
        assert "cuda" not in dockerfile.lower()
        assert "nvidia" not in dockerfile.lower()
