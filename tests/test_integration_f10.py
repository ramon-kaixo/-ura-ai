from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

from motor.core.executor import SubprocessExecutor
from motor.core.state import DegradedMode
from motor.plugin.registry import PluginRegistry


class TestDegradedModePluginRegistryIntegration:
    """PluginRegistry usa DegradedMode internamente — verificamos consistencia."""

    def _make_bad_plugin(self, tmp_path: Path, name: str) -> Path:
        f = tmp_path / f"{name}.py"
        f.write_text(f'__plugin__ = {{"name": "{name}", "phase": "pre"}}\nimport nonexistent_module_xyz_f10_int\n')
        return f

    def test_degraded_mode_reflects_plugin_failure(self, tmp_path: Path):
        dm = DegradedMode.instancia()
        registry = PluginRegistry()
        name = "plugin_fail_int_f10"
        self._make_bad_plugin(tmp_path, name)
        registry.discover([str(tmp_path)])
        assert not dm.is_degraded(f"plugin:{name}")
        registry.run_phase("pre")
        assert dm.is_degraded(f"plugin:{name}")
        s = dm.status()
        assert s["global"] is True
        assert f"plugin:{name}" in s["degraded"]

    def test_degraded_mode_recovers_after_good_plugin(self, tmp_path: Path):
        dm = DegradedMode.instancia()
        registry = PluginRegistry()
        name = "good_plugin_int_f10"
        content = f'''
__plugin__ = {{"name": "{name}", "phase": "pre"}}
from motor.plugin.base import PluginBase
class _P(PluginBase):
    def execute(self, context):
        return {{"ok": True}}
'''
        f = tmp_path / f"{name}.py"
        f.write_text(content)
        registry.discover([str(tmp_path)])
        registry.run_phase("pre")
        assert not dm.is_degraded(f"plugin:{name}")
        s = dm.status()
        assert f"plugin:{name}" not in s["degraded"]

    def test_mixed_plugin_results_reflected(self, tmp_path: Path):
        dm = DegradedMode.instancia()
        registry = PluginRegistry()
        good_name = "good_mix_f10"
        bad_name = "bad_mix_f10"
        good_content = f'''
__plugin__ = {{"name": "{good_name}", "phase": "pre"}}
from motor.plugin.base import PluginBase
class _P(PluginBase):
    def execute(self, context):
        return {{"ok": True}}
'''
        (tmp_path / f"{good_name}.py").write_text(good_content)
        self._make_bad_plugin(tmp_path, bad_name)
        registry.discover([str(tmp_path)])
        registry.run_phase("pre")
        assert dm.is_degraded(f"plugin:{bad_name}")
        assert not dm.is_degraded(f"plugin:{good_name}")
        s = dm.status()
        degraded_subsystems = s["degraded"]
        assert f"plugin:{bad_name}" in degraded_subsystems
        assert f"plugin:{good_name}" not in degraded_subsystems


class TestDegradedModeSubprocessExecutorIntegration:
    def test_executor_runs_independent_of_degraded_mode(self):
        executor = SubprocessExecutor()
        dm = DegradedMode.instancia()
        dm.mark_degraded("integration_test_f10")
        # Executor debe funcionar aunque DegradedMode tenga subsistemas degradados
        result = executor.run(["echo", "works"])
        assert result.ok is True
        assert "works" in result.stdout
        dm.mark_healthy("integration_test_f10")


class TestPluginRegistrySubprocessExecutorIntegration:
    def test_plugin_can_use_executor(self, tmp_path: Path):
        content = '''
__plugin__ = {"name": "executor_plugin_f10", "phase": "always"}
from motor.plugin.base import PluginBase
from motor.core.executor import SubprocessExecutor

class _P(PluginBase):
    def execute(self, context):
        executor = SubprocessExecutor()
        result = executor.run(["echo", "from_plugin"])
        return {"stdout": result.stdout.strip()}
'''
        f = tmp_path / "executor_plugin.py"
        f.write_text(content)
        registry = PluginRegistry()
        registry.discover([str(tmp_path)])
        results = registry.run_phase("always")
        assert len(results) == 1
        assert results[0].ok is True
        assert results[0].data["stdout"] == "from_plugin"


class TestTripleIntegration:
    """Los tres componentes trabajan juntos:
    DegradedMode monitorea subsistemas,
    PluginRegistry usa DegradedMode para trackear fallos,
    SubprocessExecutor ejecuta plugins que necesitan procesos externos."""

    def test_full_cycle(self, tmp_path: Path):
        dm = DegradedMode.instancia()
        executor = SubprocessExecutor()

        good_content = '''
__plugin__ = {"name": "good_triple_f10", "phase": "pre"}
from motor.plugin.base import PluginBase
from motor.core.executor import SubprocessExecutor

class _P(PluginBase):
    def execute(self, context):
        executor = SubprocessExecutor()
        result = executor.run(["echo", "hello_triple"])
        return {"stdout": result.stdout.strip()}
'''
        bad_content = '''__plugin__ = {"name": "bad_triple_f10", "phase": "pre"}
import nonexistent_module_xyz_triple_f10
'''
        (tmp_path / "good.py").write_text(good_content)
        (tmp_path / "bad.py").write_text(bad_content)

        # Phase 1: executor funciona independientemente
        r = executor.run(["echo", "pre_check"])
        assert r.ok is True

        # Phase 2: PluginRegistry descubre y ejecuta (un plugin carga, otro falla)
        registry = PluginRegistry()
        registry.discover([str(tmp_path)])

        assert registry.count() == 2
        assert dm.is_degraded("plugin:good_triple_f10") is False
        assert dm.is_degraded("plugin:bad_triple_f10") is False

        results = registry.run_phase("pre")
        assert len(results) == 2

        good_result = next(r for r in results if r.plugin == "good_triple_f10")
        bad_result = next(r for r in results if r.plugin == "bad_triple_f10")
        assert good_result.ok is True
        assert good_result.data["stdout"] == "hello_triple"
        assert bad_result.ok is False

        # Phase 3: DegradedMode refleja los fallos
        assert not dm.is_degraded("plugin:good_triple_f10")
        assert dm.is_degraded("plugin:bad_triple_f10")

        s = dm.status()
        assert s["global"] is True
        assert "plugin:bad_triple_f10" in s["degraded"]

        # Phase 4: Executor sigue funcionando pese al fallo de plugin
        r2 = executor.run(["echo", "post_check"])
        assert r2.ok is True
        assert "post_check" in r2.stdout
