"""Tests para motor/plugin/registry_v2.py — registro de plugins con manifiesto."""

from pathlib import Path
from unittest import mock

import pytest

from motor.core.state import DegradedMode
from motor.plugin.base import PluginBase, PluginMeta, PluginResult
from motor.plugin.manifest import PluginManifest
from motor.plugin.registry_v2 import ManifestError, PluginEntryV2, PluginRegistryV2


class FakePlugin(PluginBase):
    def execute(self, context):
        return {"ok": True}

    def on_load(self) -> None:
        pass

    def on_unload(self) -> None:
        pass


def _manifest(name: str, **kw) -> PluginManifest:
    base = {
        "api_version": "1.0.0",
        "name": name,
        "version": "0.1.0",
        "phases": ["pre"],
        "dependencies": {"plugins": []},
        "lifecycle": {"on_load": True, "on_unload": True},
    }
    base.update(kw)
    return PluginManifest(**base)


@pytest.fixture(autouse=True)
def _clean_dm() -> None:
    yield
    dm = DegradedMode.instancia()
    dm._degraded.clear()


@pytest.fixture
def reg() -> PluginRegistryV2:
    return PluginRegistryV2()


@pytest.fixture
def plugin_dir(tmp_path: Path) -> Path:
    d = tmp_path / "mi_plugin"
    d.mkdir()
    (d / "__init__.py").write_text(
        "from motor.plugin.base import PluginBase\n"
        "class MiPlugin(PluginBase):\n"
        "    def execute(self, context):\n"
        "        return {'ok': True}\n"
        "    def on_load(self): pass\n"
        "    def on_unload(self): pass\n",
    )
    return d


class TestEntradas:
    def test_vacio(self, reg: PluginRegistryV2) -> None:
        assert reg.count() == 0
        assert reg.entries == {}
        assert reg.loaded == []

    def test_entries_copia(self, reg: PluginRegistryV2) -> None:
        reg._entries["x"] = PluginEntryV2(manifest=None, path=Path())
        copia = reg.entries
        assert "x" in copia
        copia["y"] = PluginEntryV2(manifest=None, path=Path())
        assert "y" not in reg._entries  # mutar la copia no afecta el original


class TestDiscover:
    def test_ruta_invalida(self, reg: PluginRegistryV2, tmp_path: Path) -> None:
        assert reg.discover([str(tmp_path / "no_existe")]) == 0

    def test_archivo_no_py(self, reg: PluginRegistryV2, tmp_path: Path) -> None:
        f = tmp_path / "x.txt"
        f.write_text("")
        assert reg.discover([str(f)]) == 0

    def test_dir_con_manifest(self, reg: PluginRegistryV2, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        d = tmp_path / "pkg"
        d.mkdir()
        (d / "plugin.yaml").write_text("name: pkg1\nversion: 1.0.0\n")
        monkeypatch.setattr("motor.plugin.registry_v2.parse_manifest", mock.Mock(return_value=_manifest("pkg1")))
        monkeypatch.setattr("motor.plugin.registry_v2.find_manifest", mock.Mock(return_value=d / "plugin.yaml"))
        assert reg.discover([str(d)]) == 1
        assert reg.count() == 1
        assert reg.get_manifest("pkg1").name == "pkg1"  # type: ignore[union-attr]
        assert reg.discover([str(d)]) == 1  # duplicado: sobrescribe, sigue 1

    def test_dir_manifest_invalido(self, reg: PluginRegistryV2, tmp_path: Path,
                                   monkeypatch: pytest.MonkeyPatch) -> None:
        d = tmp_path / "pkg"
        d.mkdir()
        (d / "plugin.yaml").write_text("bad: yaml: :")
        monkeypatch.setattr("motor.plugin.registry_v2.find_manifest", mock.Mock(return_value=d / "plugin.yaml"))
        monkeypatch.setattr("motor.plugin.registry_v2.parse_manifest", mock.Mock(return_value=None))
        assert reg.discover([str(d)]) == 0

    def test_dir_sin_manifest_legacy(self, reg: PluginRegistryV2, tmp_path: Path) -> None:
        d = tmp_path / "legacy_dir"
        d.mkdir()
        (d / "uno.py").write_text(
            '__plugin__ = {"name": "uno", "phase": "pre"}\n',
        )
        (d / "_privado.py").write_text(
            '__plugin__ = {"name": "priv"}\n',
        )
        assert reg.discover([str(d)]) == 1
        assert reg.get_manifest("uno").name == "uno"  # type: ignore[union-attr]

    def test_dir_anidado(self, reg: PluginRegistryV2, tmp_path: Path) -> None:
        d = tmp_path / "raiz"
        d.mkdir()
        (d / "a.py").write_text('__plugin__ = {"name": "a"}\n')
        sub = d / ".oculto"
        sub.mkdir()
        (sub / "b.py").write_text('__plugin__ = {"name": "b"}\n')
        sub2 = d / "visible"
        sub2.mkdir()
        (sub2 / "c.py").write_text('__plugin__ = {"name": "c"}\n')
        assert reg.discover([str(d)]) == 2

    def test_legacy_sin_meta(self, reg: PluginRegistryV2, tmp_path: Path) -> None:
        f = tmp_path / "x.py"
        f.write_text("print(1)\n")
        assert reg.discover([str(f)]) == 1  # from_file fallback al stem
        assert reg.get_manifest("x") is not None
        assert reg.discover([str(f)]) == 1  # duplicado: sobrescribe, sigue 1

    def test_duplicados(self, reg: PluginRegistryV2, tmp_path: Path) -> None:
        d = tmp_path / "d"
        d.mkdir()
        (d / "p.py").write_text('__plugin__ = {"name": "dup"}\n')
        (d / "q.py").write_text('__plugin__ = {"name": "dup"}\n')
        assert reg.discover([str(d)]) == 2
        assert reg.count() == 1  # sobrescribe


class TestGetManifest:
    def test_no_existe(self, reg: PluginRegistryV2) -> None:
        assert reg.get_manifest("nada") is None

    def test_v2(self, reg: PluginRegistryV2) -> None:
        m = _manifest("p")
        reg._entries["p"] = PluginEntryV2(manifest=m, path=Path())
        assert reg.get_manifest("p") is m

    def test_legacy(self, reg: PluginRegistryV2) -> None:
        meta = PluginMeta(name="l")
        reg._entries["l"] = PluginEntryV2(manifest=None, path=Path(), legacy_meta=meta)
        assert reg.get_manifest("l") is meta


class TestLoadV2:
    def test_ok(self, reg: PluginRegistryV2, plugin_dir: Path) -> None:
        m = _manifest("mi_plugin", entry_point="MiPlugin")
        reg._entries["mi_plugin"] = PluginEntryV2(manifest=m, path=plugin_dir, manifest_path=plugin_dir / "p.yaml")
        with mock.patch("motor.plugin.registry_v2.check_api_compatibility", return_value=True) if False else mock.patch(
            "motor.events.compat.check_api_compatibility", return_value=True
        ):
            plugin = reg.get("mi_plugin")
        assert plugin is not None
        assert "mi_plugin" in reg.loaded
        assert not reg._dm.is_degraded("plugin:mi_plugin")
        assert reg.get("mi_plugin") is plugin  # cache hit

    def test_manifest_nulo(self, reg: PluginRegistryV2, plugin_dir: Path) -> None:
        reg._entries["p"] = PluginEntryV2(manifest=None, path=plugin_dir)
        assert reg._load_v2(reg._entries["p"]) is None

    def test_api_incompatible(self, reg: PluginRegistryV2, plugin_dir: Path) -> None:
        m = _manifest("p", api_version="99.0.0")
        reg._entries["p"] = PluginEntryV2(manifest=m, path=plugin_dir)
        with mock.patch("motor.events.compat.check_api_compatibility", return_value=False):
            assert reg.get("p") is None
        assert reg._dm.is_degraded("plugin:p")

    def test_sin_init(self, reg: PluginRegistryV2, tmp_path: Path) -> None:
        d = tmp_path / "sin_init"
        d.mkdir()
        m = _manifest("p")
        reg._entries["p"] = PluginEntryV2(manifest=m, path=d)
        assert reg.get("p") is None

    def test_sin_clase(self, reg: PluginRegistryV2, tmp_path: Path) -> None:
        d = tmp_path / "sin_clase"
        d.mkdir()
        (d / "__init__.py").write_text("x = 1\n")
        m = _manifest("p")
        reg._entries["p"] = PluginEntryV2(manifest=m, path=d)
        assert reg.get("p") is None

    def test_error_registrar(self, reg: PluginRegistryV2, tmp_path: Path) -> None:
        d = tmp_path / "reg"
        d.mkdir()
        (d / "__init__.py").write_text(
            "from motor.plugin.base import PluginBase\n"
            "class A(PluginBase):\n"
            "    def execute(self, c): return {}\n"
            "    def on_load(self): pass\n"
            "    def on_unload(self): pass\n",
        )
        m = _manifest("r")
        reg._entries["r"] = PluginEntryV2(manifest=m, path=d)
        with mock.patch.object(reg, "_registrar_plugin", side_effect=RuntimeError("boom")):
            assert reg.get("r") is None
        assert reg._dm.is_degraded("plugin:r")

    def test_on_load_falla(self, reg: PluginRegistryV2, tmp_path: Path) -> None:
        d = tmp_path / "ol"
        d.mkdir()
        (d / "__init__.py").write_text(
            "from motor.plugin.base import PluginBase\n"
            "class A(PluginBase):\n"
            "    def execute(self, c): return {}\n"
            "    def on_load(self): raise ValueError('carga fallida')\n"
            "    def on_unload(self): pass\n",
        )
        m = _manifest("ol")
        reg._entries["ol"] = PluginEntryV2(manifest=m, path=d)
        plugin = reg.get("ol")
        assert plugin is not None  # on_load falló pero el plugin queda registrado
        assert not reg._dm.is_degraded("plugin:ol")

    def test_error_carga(self, reg: PluginRegistryV2, tmp_path: Path) -> None:
        d = tmp_path / "error"
        d.mkdir()
        (d / "__init__.py").write_text("raise RuntimeError('boom')\n")
        m = _manifest("p")
        reg._entries["p"] = PluginEntryV2(manifest=m, path=d)
        with pytest.raises(RuntimeError):
            reg.get("p")

    def test_entry_point_no_existe(self, reg: PluginRegistryV2, tmp_path: Path) -> None:
        d = tmp_path / "ep"
        d.mkdir()
        (d / "__init__.py").write_text(
            "from motor.plugin.base import PluginBase\n"
            "class A(PluginBase):\n"
            "    def execute(self, c): return {}\n"
            "    def on_load(self): pass\n"
            "    def on_unload(self): pass\n",
        )
        m = _manifest("p", entry_point="NoExiste")
        reg._entries["p"] = PluginEntryV2(manifest=m, path=d)
        with mock.patch("motor.events.compat.check_api_compatibility", return_value=True):
            plugin = reg.get("p")
        assert plugin is not None  # fallback scan dir()

    def test_spec_invalido(self, reg: PluginRegistryV2, tmp_path: Path) -> None:
        d = tmp_path / "si"
        d.mkdir()
        (d / "__init__.py").write_text("from motor.plugin.base import PluginBase\n")
        m = _manifest("si")
        reg._entries["si"] = PluginEntryV2(manifest=m, path=d)
        with mock.patch(
            "motor.plugin.registry_v2.importlib.util.spec_from_file_location",
            return_value=None,
        ):
            assert reg.get("si") is None
        assert reg._dm.is_degraded("plugin:si")

    def test_entry_point_falla_instanciar(self, reg: PluginRegistryV2, tmp_path: Path) -> None:
        d = tmp_path / "ef"
        d.mkdir()
        (d / "__init__.py").write_text(
            "from motor.plugin.base import PluginBase\n"
            "class A(PluginBase):\n"
            "    def __init__(self): raise ValueError('boom')\n"
            "    def execute(self, c): return {}\n"
            "    def on_load(self): pass\n"
            "    def on_unload(self): pass\n",
        )
        m = _manifest("ef", entry_point="A")
        reg._entries["ef"] = PluginEntryV2(manifest=m, path=d)
        with mock.patch("motor.events.compat.check_api_compatibility", return_value=True):
            assert reg.get("ef") is None  # A() falla, sin fallback: no hay otra subclase

    def test_scan_falla_instanciar(self, reg: PluginRegistryV2, tmp_path: Path) -> None:
        d = tmp_path / "sf"
        d.mkdir()
        (d / "__init__.py").write_text(
            "from motor.plugin.base import PluginBase\n"
            "class A(PluginBase):\n"
            "    def __init__(self): raise ValueError('boom')\n"
            "    def execute(self, c): return {}\n"
            "    def on_load(self): pass\n"
            "    def on_unload(self): pass\n",
        )
        m = _manifest("sf")  # sin entry_point -> scan dir()
        reg._entries["sf"] = PluginEntryV2(manifest=m, path=d)
        with mock.patch("motor.events.compat.check_api_compatibility", return_value=True):
            assert reg.get("sf") is None  # scan falla en A()

    def test_no_cargado_no_encontrado(self, reg: PluginRegistryV2) -> None:
        assert reg.get("inexistente") is None

    def test_carga_dependencias(self, reg: PluginRegistryV2, plugin_dir: Path, tmp_path: Path) -> None:
        dep_dir = tmp_path / "dep"
        dep_dir.mkdir()
        (dep_dir / "__init__.py").write_text(
            "from motor.plugin.base import PluginBase\n"
            "class Dep(PluginBase):\n"
            "    def execute(self, c): return {}\n"
            "    def on_load(self): pass\n"
            "    def on_unload(self): pass\n",
        )
        m_dep = _manifest("dep", entry_point="Dep")
        m_main = _manifest("mi_plugin", entry_point="MiPlugin",
                           dependencies={"plugins": ["dep"]})
        reg._entries["dep"] = PluginEntryV2(manifest=m_dep, path=dep_dir)
        reg._entries["mi_plugin"] = PluginEntryV2(manifest=m_main, path=plugin_dir)
        with mock.patch("motor.events.compat.check_api_compatibility", return_value=True):
            plugin = reg.get("mi_plugin")
        assert plugin is not None
        assert "dep" in reg.loaded


class TestLoadLegacy:
    def test_ok(self, reg: PluginRegistryV2, tmp_path: Path) -> None:
        f = tmp_path / "legacy.py"
        f.write_text(
            "from motor.plugin.base import PluginBase\n"
            "class L(PluginBase):\n"
            "    def execute(self, c): return {}\n"
            "    def on_load(self): pass\n"
            "    def on_unload(self): pass\n"
            "__plugin__ = {'name': 'legacy'}\n",
        )
        reg._entries["legacy"] = PluginEntryV2(manifest=None, path=f, legacy_meta=PluginMeta(name="legacy"))
        plugin = reg.get("legacy")
        assert plugin is not None
        assert "legacy" in reg.loaded

    def test_no_encontrado(self, reg: PluginRegistryV2, tmp_path: Path) -> None:
        f = tmp_path / "l.py"
        f.write_text("x=1\n")
        entry = PluginEntryV2(manifest=None, path=f, legacy_meta=PluginMeta(name="l"))
        assert reg._load_legacy(entry) is None


class TestUnload:
    def test_no_cargado(self, reg: PluginRegistryV2) -> None:
        assert reg.unload("nada") is False

    def test_ok(self, reg: PluginRegistryV2) -> None:
        plugin = FakePlugin()
        reg._instances["p"] = plugin
        plugin.manifest = _manifest("p")
        assert reg.unload("p") is True
        assert "p" not in reg.loaded

    def test_on_unload_falla(self, reg: PluginRegistryV2) -> None:
        plugin = FakePlugin()
        plugin.manifest = _manifest("p")
        plugin.on_unload = mock.Mock(side_effect=RuntimeError("x"))
        reg._instances["p"] = plugin
        assert reg.unload("p") is True

    def test_con_hooks_bus(self, reg: PluginRegistryV2) -> None:
        hooks = mock.Mock()
        bus = mock.Mock()
        reg._hooks = hooks
        reg._bus = bus
        plugin = FakePlugin()
        plugin.manifest = _manifest("p")
        reg._instances["p"] = plugin
        assert reg.unload("p") is True
        hooks.unregister_plugin_hooks.assert_called_once_with("p")
        assert bus.publish.call_count == 1


class TestRegistrar:
    def test_on_load_falla(self, reg: PluginRegistryV2) -> None:
        plugin = FakePlugin()
        plugin.on_load = mock.Mock(side_effect=RuntimeError("x"))
        plugin.manifest = _manifest("p")
        reg._instances["p"] = plugin
        reg._dm.mark_healthy("plugin:p")
        assert "p" in reg.loaded

    def test_con_bus_y_hooks(self, reg: PluginRegistryV2) -> None:
        hooks = mock.Mock()
        bus = mock.Mock()
        reg._hooks = hooks
        reg._bus = bus
        plugin = FakePlugin()
        m = _manifest("p")
        reg._registrar_plugin("p", plugin, m)
        hooks.register_plugin_hooks.assert_called_once_with("p", plugin)
        assert bus.publish.call_count == 1


class TestRunPhase:
    def test_v2_match(self, reg: PluginRegistryV2, plugin_dir: Path) -> None:
        m = _manifest("mi_plugin", entry_point="MiPlugin", phases=["pre"])
        reg._entries["mi_plugin"] = PluginEntryV2(manifest=m, path=plugin_dir)
        with mock.patch("motor.events.compat.check_api_compatibility", return_value=True):
            results = reg.run_phase("pre", {"k": 1})
        assert len(results) == 1
        assert results[0].ok is True

    def test_legacy_match(self, reg: PluginRegistryV2, tmp_path: Path) -> None:
        f = tmp_path / "l.py"
        f.write_text(
            "from motor.plugin.base import PluginBase\n"
            "class L(PluginBase):\n"
            "    def execute(self, c): return {}\n"
            "    def on_load(self): pass\n"
            "    def on_unload(self): pass\n"
            "__plugin__ = {'name': 'l', 'phase': 'post'}\n",
        )
        reg._entries["l"] = PluginEntryV2(manifest=None, path=f, legacy_meta=PluginMeta(name="l", phase="post"))
        results = reg.run_phase("post")
        assert len(results) == 1

    def test_sin_fase_match(self, reg: PluginRegistryV2) -> None:
        m = _manifest("p", phases=["pre"])
        reg._entries["p"] = PluginEntryV2(manifest=m, path=Path())
        results = reg.run_phase("post")
        assert results == []

    def test_manifest_sin_meta_always(self, reg: PluginRegistryV2, tmp_path: Path) -> None:
        f = tmp_path / "x.py"
        f.write_text("__plugin__ = {'name': 'x'}\n")
        reg._entries["x"] = PluginEntryV2(manifest=None, path=f)
        results = reg.run_phase("pre")
        assert len(results) == 1
        assert results[0].ok is False  # plugin no cargado

    def test_carga_fallida(self, reg: PluginRegistryV2, tmp_path: Path) -> None:
        m = _manifest("p")
        reg._entries["p"] = PluginEntryV2(manifest=m, path=tmp_path / "no")
        results = reg.run_phase("pre")
        assert len(results) == 1
        assert results[0].ok is False

    def test_execute_falla(self, reg: PluginRegistryV2, plugin_dir: Path) -> None:
        d = plugin_dir.parent / "explota"
        d.mkdir()
        (d / "__init__.py").write_text(
            "from motor.plugin.base import PluginBase\n"
            "class E(PluginBase):\n"
            "    def execute(self, c): raise ValueError('boom')\n"
            "    def on_load(self): pass\n"
            "    def on_unload(self): pass\n",
        )
        m = _manifest("explota", entry_point="E", phases=["pre"])
        reg._entries["explota"] = PluginEntryV2(manifest=m, path=d)
        with mock.patch("motor.events.compat.check_api_compatibility", return_value=True):
            results = reg.run_phase("pre")
        assert len(results) == 1
        assert results[0].ok is False
        assert "boom" in results[0].error


class TestRunOne:
    def test_no_existe(self, reg: PluginRegistryV2) -> None:
        assert reg.run_one("nada") is None

    def test_sin_resultado(self, reg: PluginRegistryV2, tmp_path: Path) -> None:
        d = tmp_path / "sr"
        d.mkdir()
        (d / "__init__.py").write_text(
            "from motor.plugin.base import PluginBase\n"
            "class A(PluginBase):\n"
            "    def execute(self, c): return None\n"
            "    def on_load(self): pass\n"
            "    def on_unload(self): pass\n",
        )
        m = _manifest("sr")
        reg._entries["sr"] = PluginEntryV2(manifest=m, path=d)
        otro = PluginResult(ok=True, plugin="otro", phase="pre", data=None, error="", duration_ms=1.0)
        with mock.patch.object(reg, "run_phase", return_value=[otro]):
            assert reg.run_one("sr") is None  # resultados de otro plugin -> sin resultado

    def test_ok_v2(self, reg: PluginRegistryV2, plugin_dir: Path) -> None:
        m = _manifest("mi_plugin", entry_point="MiPlugin", phases=["pre"])
        reg._entries["mi_plugin"] = PluginEntryV2(manifest=m, path=plugin_dir)
        with mock.patch("motor.events.compat.check_api_compatibility", return_value=True):
            r = reg.run_one("mi_plugin", {"a": 1})
        assert r is not None
        assert r.ok is True

    def test_ok_legacy(self, reg: PluginRegistryV2, tmp_path: Path) -> None:
        f = tmp_path / "l.py"
        f.write_text(
            "from motor.plugin.base import PluginBase\n"
            "class L(PluginBase):\n"
            "    def execute(self, c): return {}\n"
            "    def on_load(self): pass\n"
            "    def on_unload(self): pass\n"
            "__plugin__ = {'name': 'l'}\n",
        )
        reg._entries["l"] = PluginEntryV2(manifest=None, path=f, legacy_meta=PluginMeta(name="l"))
        r = reg.run_one("l")
        assert r is not None
        assert r.ok is True

    def test_sin_meta(self, reg: PluginRegistryV2) -> None:
        reg._entries["x"] = PluginEntryV2(manifest=None, path=Path())
        r = reg.run_one("x")
        assert r is not None
        assert r.ok is False


class TestDependencias:
    def test_sin_manifest(self, reg: PluginRegistryV2) -> None:
        assert reg._resolve_dependencies
        entry = PluginEntryV2(manifest=None, path=Path())
        reg._entries["x"] = entry
        assert reg._resolve_dependencies("x") == ["x"]

    def test_simple(self, reg: PluginRegistryV2) -> None:
        m = _manifest("a", dependencies={"plugins": ["b"]})
        reg._entries["a"] = PluginEntryV2(manifest=m, path=Path())
        m_b = _manifest("b")
        reg._entries["b"] = PluginEntryV2(manifest=m_b, path=Path())
        assert reg._resolve_dependencies("a") == ["b", "a"]

    def test_circular(self, reg: PluginRegistryV2) -> None:
        m_a = _manifest("a", dependencies={"plugins": ["b"]})
        m_b = _manifest("b", dependencies={"plugins": ["a"]})
        reg._entries["a"] = PluginEntryV2(manifest=m_a, path=Path())
        reg._entries["b"] = PluginEntryV2(manifest=m_b, path=Path())
        with pytest.raises(ManifestError, match="circular"):
            reg._resolve_dependencies("a")

    def test_diamante(self, reg: PluginRegistryV2) -> None:
        m_a = _manifest("a", dependencies={"plugins": ["b", "c"]})
        m_b = _manifest("b", dependencies={"plugins": ["c"]})
        m_c = _manifest("c")
        reg._entries["a"] = PluginEntryV2(manifest=m_a, path=Path())
        reg._entries["b"] = PluginEntryV2(manifest=m_b, path=Path())
        reg._entries["c"] = PluginEntryV2(manifest=m_c, path=Path())
        assert reg._resolve_dependencies("a") == ["c", "b", "a"]

    def test_self(self, reg: PluginRegistryV2) -> None:
        m = _manifest("a", dependencies={"plugins": ["a"]})
        reg._entries["a"] = PluginEntryV2(manifest=m, path=Path())
        with pytest.raises(ManifestError, match="circular"):
            reg._resolve_dependencies("a")
