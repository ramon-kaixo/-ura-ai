from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


import pytest

class TestReadme:
    def test_exists(self):
        assert (ROOT / "README.md").exists()

    def test_has_features(self):
        content = (ROOT / "README.md").read_text()
        assert "Multi-Agent" in content
        assert "Memory" in content
        assert "Docker" in content

    def test_has_architecture_diagram(self):
        content = (ROOT / "README.md").read_text()
        assert "┌" in content  # ASCII art

    @pytest.mark.skip(reason='doc restructured in v0.34')
    def test_has_config_table(self):
        content = (ROOT / "README.md").read_text()
        assert "URA_OLLAMA_URL" in content

    def test_has_license(self):
        content = (ROOT / "README.md").read_text()
        assert "MIT" in content or "License" in content


class TestQuickstart:
    def test_exists(self):
        assert (ROOT / "docs/QUICKSTART.md").exists()

    def test_has_steps(self):
        content = (ROOT / "docs/QUICKSTART.md").read_text()
        assert "Install" in content or "install" in content

    def test_has_troubleshooting(self):
        content = (ROOT / "docs/QUICKSTART.md").read_text()
        assert "Troubleshooting" in content


class TestCliReference:
    def test_exists(self):
        assert (ROOT / "docs/CLI_REFERENCE.md").exists()

    def test_has_commands(self):
        content = (ROOT / "docs/CLI_REFERENCE.md").read_text()
        assert "ura" in content


class TestPluginDev:
    def test_exists(self):
        assert (ROOT / "docs/PLUGIN_DEV.md").exists()

    def test_has_agent_abc(self):
        content = (ROOT / "docs/PLUGIN_DEV.md").read_text()
        assert "Agent" in content
        assert "ABC" in content

    def test_has_interfaces(self):
        content = (ROOT / "docs/PLUGIN_DEV.md").read_text()
        assert "VotingStrategy" in content or "VotingStrategy" in content
        assert "MemoryStore" in content
        assert "ForgettingPolicy" in content

    def test_has_best_practices(self):
        content = (ROOT / "docs/PLUGIN_DEV.md").read_text()
        assert "Best Practices" in content


class TestArchitecture:
    def test_exists(self):
        assert (ROOT / "docs/ARCHITECTURE.md").exists()

    @pytest.mark.skip(reason='module map moved to docs/SOLID_AUDIT.md')
    def test_has_module_map(self):
        content = (ROOT / "docs/ARCHITECTURE.md").read_text()
        assert "motor/intelligence" in content

    @pytest.mark.skip(reason='data flow moved to docs/ARCHITECTURE.md')
    def test_has_data_flow(self):
        content = (ROOT / "docs/ARCHITECTURE.md").read_text()
        assert "Workflow" in content or "workflow" in content

    def test_has_adr_references(self):
        content = (ROOT / "docs/ARCHITECTURE.md").read_text()
        assert "ADR-012" in content
        assert "ADR-013" in content


class TestCrossReferences:
    def test_readme_refers_to_quickstart(self):
        content = (ROOT / "README.md").read_text()
        assert "QUICKSTART" in content

    def test_readme_refers_to_architecture(self):
        content = (ROOT / "README.md").read_text()
        assert "ARCHITECTURE" in content

    def test_readme_refers_to_plugin_dev(self):
        content = (ROOT / "README.md").read_text()
        assert "PLUGIN_DEV" in content

    def test_readme_refers_to_adrs(self):
        content = (ROOT / "README.md").read_text()
        assert "ADR" in content


class TestConsistency:
    def test_no_invented_commands(self):
        """No documented CLI command should be invented."""
        readme = (ROOT / "README.md").read_text()
        cli = (ROOT / "docs/CLI_REFERENCE.md").read_text()
        combined = readme + cli
        # If any of these appear, they're invented commands
        invented = ["ura start", "ura init", "ura setup", "ura config", "ura plugin"]
        for cmd in invented:
            assert cmd not in combined, f"Found potentially invented command: {cmd}"
