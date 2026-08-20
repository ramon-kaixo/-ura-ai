"""Cobertura 100x100 de diagnostico + plugin + orquestador. TASK-20260820-018."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

import motor.core.agents.orquestador as orq
import motor.diagnostico.backup_knowledge as bk
from motor.core.agents.orquestador import AgenteOrquestador
from motor.diagnostico.backup_knowledge import backup_incidente
from motor.diagnostico.correlacion import DEPENDENCIAS, agrupar_incidentes, resumir_incidentes
from motor.diagnostico.pattern_matcher import (
    _calcular_costes_historicos,
    _incidentes_hardware,
    _incidentes_recursos,
    _incidentes_red,
    _incidentes_servicios,
    _incidentes_varios,
    buscar_patrones,
)
from motor.plugin.base import PluginBase, PluginEntry, PluginMeta, PluginResult, _ast_dict_to_dict
from motor.plugin.manifest import (
    MANIFEST_SCHEMA,
    REQUIRED_FIELDS,
    ManifestError,
    PluginManifest,
    find_manifest,
    parse_manifest,
)

# ── correlacion ──────────────────────────────────────────────


def test_dependencias_definidas() -> None:
    assert "docker" in DEPENDENCIAS
    assert DEPENDENCIAS["sshd"] == ["red"]


def test_agrupar_sin_incidentes() -> None:
    assert agrupar_incidentes([]) == []


def test_agrupar_con_hw_issues() -> None:
    grupos = agrupar_incidentes([], hw_ok=False, hw_issues=["dmesg error"])
    assert grupos[0]["causa_raiz"] == "hardware"
    assert "sshd" in grupos[0]["servicios_afectados"]


def test_agrupar_hw_ok_sin_issues() -> None:
    assert agrupar_incidentes([], hw_ok=False, hw_issues=None) == []


def test_agrupar_con_dependencia() -> None:
    grupos = agrupar_incidentes(["docker"])
    assert grupos[0]["causa_raiz"] == "docker"
    assert "container_searxng" in grupos[0]["servicios_afectados"]


def test_agrupar_tag_simple() -> None:
    grupos = agrupar_incidentes(["weird_tag"])
    assert grupos[0]["causa_raiz"] == "weird_tag"
    assert grupos[0]["sintomas"] == ["weird_tag detectado"]


def test_agrupar_hw_issue_no_duplica() -> None:
    grupos = agrupar_incidentes(["hw_issue", "docker"])
    causas = [g["causa_raiz"] for g in grupos]
    assert causas == ["docker"]  # hw_issue no duplica sin hw_ok=False


def test_agrupar_hw_issue_con_hw_ok_false() -> None:
    grupos = agrupar_incidentes(["hw_issue", "docker"], hw_ok=False, hw_issues=["z"])
    causas = [g["causa_raiz"] for g in grupos]
    assert causas == ["hardware", "docker"]  # hw_issue se salta en el loop (procesados)


def test_resumir_vacio() -> None:
    assert resumir_incidentes([]) == "Sin incidencias activas"


def test_resumir_con_incidentes() -> None:
    s = resumir_incidentes([{"tipo": "A", "subtipo": "x"}, {"tipo": "B"}])
    assert "2 incidencia(s)" in s
    assert "A" in s
    assert "[x]" in s


def test_resumir_sin_subtipos() -> None:
    s = resumir_incidentes([{"tipo": "A"}])
    assert "A" in s
    assert "[" not in s


# ── backup_knowledge ─────────────────────────────────────────


class _Cfg:
    def __init__(self, data_dir: str) -> None:
        self.data_dir = data_dir


def test_backup_incidente_ok(tmp_path: object) -> None:
    p = backup_incidente(_Cfg(str(tmp_path)), {"tipo": "X"})
    assert p != ""
    assert Path(p).exists()
    data = json.loads(Path(p).read_text())
    assert data["incidente"]["tipo"] == "X"
    assert "timestamp" in data


def test_backup_sin_incidente(tmp_path: object) -> None:
    p = backup_incidente(_Cfg(str(tmp_path)))
    assert p != ""
    data = json.loads(Path(p).read_text())
    assert "incidente" not in data


def test_backup_error(monkeypatch: pytest.MonkeyPatch, tmp_path: object) -> None:
    class _CfgRoto:
        data_dir = str(tmp_path / "no" / "permiso" / "dir" / "anidado")

    monkeypatch.setattr(bk.Path, "write_text", lambda self, *a, **k: (_ for _ in ()).throw(OSError("denegado")))
    assert backup_incidente(_CfgRoto()) == ""


# ── pattern_matcher ──────────────────────────────────────────


class _Scan:
    def __init__(self, **kw) -> None:
        self.timestamp = "2026-08-20T10:00:00"
        self.servicios = kw.get("servicios", {})
        self.recursos = kw.get("recursos", {})
        self.red = kw.get("red", {})
        self.hw_health = kw.get("hw_health", {})
        self.contenedores_ko = kw.get("contenedores_ko", [])
        self.duplicados = kw.get("duplicados", {})
        self.flapping = kw.get("flapping", [])
        self.diff_total = kw.get("diff_total", 0)
        self.anomalias = kw.get("anomalias", [])


def test_buscar_patrones_ok() -> None:
    scan = _Scan(servicios={"svc1": "inactive"}, recursos={"ram_pct": 95})
    incidentes, costes = buscar_patrones(scan, None, None)
    assert len(incidentes) >= 2
    assert "ServiceFailure.svc1" in costes


def test_incidentes_servicios() -> None:
    scan = _Scan(servicios={"a": "inactive", "b": "failed", "c": "active"})
    incs = _incidentes_servicios(scan)
    assert len(incs) == 2
    assert incs[0]["tipo"] == "ServiceFailure"


def test_incidentes_servicios_vacio() -> None:
    assert _incidentes_servicios(_Scan(servicios={"a": "active"})) == []


def test_incidentes_recursos() -> None:
    scan = _Scan(recursos={"ram_pct": 95, "disk_pct": 90, "load_1m": 8, "ncpu": 2})
    incs = _incidentes_recursos(scan)
    assert len(incs) == 3
    subtipos = [i["subtipo"] for i in incs]
    assert "ram" in subtipos and "disco" in subtipos and "cpu" in subtipos


def test_incidentes_recursos_ok() -> None:
    scan = _Scan(recursos={"ram_pct": 10, "disk_pct": 10, "load_1m": 1, "ncpu": 4})
    assert _incidentes_recursos(scan) == []


def test_incidentes_recursos_ncpu_cero() -> None:
    scan = _Scan(recursos={"load_1m": 99, "ncpu": 0})
    assert _incidentes_recursos(scan) == []  # ncpu=0 → no cpu check


def test_incidentes_red() -> None:
    scan = _Scan(red={"internet": False, "exit_node_online": False})
    incs = _incidentes_red(scan)
    assert len(incs) == 2


def test_incidentes_red_ok() -> None:
    assert _incidentes_red(_Scan(red={"internet": True, "exit_node_online": True})) == []


def test_incidentes_hardware_dmesg() -> None:
    scan = _Scan(hw_health={"dmesg_errors": ["e1", "e2"]})
    incs = _incidentes_hardware(scan)
    assert any(i["subtipo"] == "dmesg" for i in incs)


def test_incidentes_hardware_journal() -> None:
    scan = _Scan(hw_health={"journal_corrupt": 3})
    incs = _incidentes_hardware(scan)
    assert any(i["subtipo"] == "journal" for i in incs)


def test_incidentes_hardware_no_ok_vm() -> None:
    scan = _Scan(hw_health={"ok": False, "tipo": "vm", "issues": ["x"]})
    incs = _incidentes_hardware(scan)
    assert any(i["subtipo"] == "vm" for i in incs)


def test_incidentes_hardware_no_ok_fisico() -> None:
    scan = _Scan(hw_health={"ok": False, "issues": ["y"]})
    incs = _incidentes_hardware(scan)
    assert any(i["subtipo"] == "fisico" for i in incs)


def test_incidentes_hardware_ok() -> None:
    assert _incidentes_hardware(_Scan(hw_health={"ok": True})) == []


def test_incidentes_varios() -> None:
    scan = _Scan(
        contenedores_ko=["c1"],
        duplicados={"p1": 2},
        flapping=["svc"],
        diff_total=5,
        anomalias=["a"],
    )
    incs = _incidentes_varios(scan)
    assert len(incs) == 4


def test_incidentes_varios_vacio() -> None:
    assert _incidentes_varios(_Scan()) == []


def test_calcular_costes() -> None:
    incs = [{"tipo": "A", "subtipo": "x"}, {"tipo": "A", "subtipo": "x"}, {"tipo": "B"}]
    costes = _calcular_costes_historicos(incs)
    assert costes["A.x"]["veces"] == 2
    assert costes["B"]["veces"] == 1


# ── plugin base ──────────────────────────────────────────────


def test_plugin_meta_defaults() -> None:
    m = PluginMeta(name="p")
    assert m.phase == "always"
    assert m.blocking is False
    assert m.timeout == 30


def test_plugin_meta_from_dict() -> None:
    m = PluginMeta.from_dict({"name": "x", "phase": "pre", "blocking": True, "timeout": 5, "description": "d"})
    assert m.name == "x"
    assert m.phase == "pre"
    assert m.blocking is True
    assert m.timeout == 5


def test_plugin_meta_from_dict_defaults() -> None:
    m = PluginMeta.from_dict({})
    assert m.name == "unknown"
    assert m.phase == "always"


def test_plugin_meta_from_source_dict() -> None:
    src = '__plugin__ = {"name": "mi", "phase": "post"}'
    m = PluginMeta.from_source(src)
    assert m is not None
    assert m.name == "mi"
    assert m.phase == "post"


def test_plugin_meta_from_source_constant_dict() -> None:
    src = "__plugin__ = {'name': 'const'}"
    m = PluginMeta.from_source(src)
    assert m is not None
    assert m.name == "const"


def test_plugin_meta_from_source_sin_plugin() -> None:
    assert PluginMeta.from_source("x = 1") is None


def test_plugin_meta_from_source_syntax_error() -> None:
    assert PluginMeta.from_source("esto no es python {{{") is None


def test_plugin_meta_from_file(tmp_path: object) -> None:
    f = Path(str(tmp_path)) / "mi.py"
    f.write_text('__plugin__ = {"name": "mi"}')
    m = PluginMeta.from_file(f)
    assert m.name == "mi"


def test_plugin_meta_from_file_sin_meta(tmp_path: object) -> None:
    f = Path(str(tmp_path)) / "sin.py"
    f.write_text("x = 1")
    m = PluginMeta.from_file(f)
    assert m.name == "sin"  # fallback al stem


def test_plugin_meta_from_file_error(monkeypatch: pytest.MonkeyPatch, tmp_path: object) -> None:
    f = Path(str(tmp_path)) / "roto.py"

    def _read_roto(self, **k):
        msg = "permiso"
        raise OSError(msg)

    monkeypatch.setattr(Path, "read_text", _read_roto)
    m = PluginMeta.from_file(f)
    assert m.name == "roto"


def test_ast_dict_to_dict() -> None:
    tree = ast.parse("d = {'a': 1, 'b': 'x', 'c': [1, 2], 'd': {'e': 2}, 'f': True, 'g': not True}")
    d = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            d = _ast_dict_to_dict(node.value)
    assert d["a"] == 1
    assert d["b"] == "x"
    assert d["c"] == [1, 2]
    assert d["d"] == {"e": 2}
    assert d["f"] is True
    assert d["g"] is False


def test_ast_dict_key_no_string() -> None:
    tree = ast.parse("d = {1: 'x'}")
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            assert _ast_dict_to_dict(node.value) == {}


def test_ast_dict_value_str_legacy() -> None:
    tree = ast.parse("d = {'k': 'v'}")
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            assert _ast_dict_to_dict(node.value) == {"k": "v"}


def test_ast_dict_value_expression() -> None:
    # Tuple no se maneja (solo Constant/Str/List/Dict/Name/UnaryOp) → se ignora
    tree = ast.parse("d = {'k': ('a', 'b')}")
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            assert _ast_dict_to_dict(node.value) == {}


def test_plugin_meta_from_source_assign_multiple() -> None:
    src = "a = 1\n__plugin__ = {'name': 'multi'}"
    m = PluginMeta.from_source(src)
    assert m is not None
    assert m.name == "multi"


def test_plugin_meta_from_source_assign_sin_plugin() -> None:
    src = "a = 1\nb = 2"
    assert PluginMeta.from_source(src) is None


def test_plugin_meta_from_source_con_expr() -> None:
    # node Expr al nivel módulo (no Assign) → se salta
    src = 'funcion(1)\n__plugin__ = {"name": "con-expr"}'
    m = PluginMeta.from_source(src)
    assert m is not None
    assert m.name == "con-expr"


def test_plugin_meta_from_source_constant_no_dict() -> None:
    src = "__plugin__ = 42"
    assert PluginMeta.from_source(src) is None


def test_ast_dict_key_no_string_otro() -> None:
    # key es Name (no Constant/Str) → continue
    tree = ast.parse("k = 'x'\nd = {k: 'v'}")
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Dict):
            assert _ast_dict_to_dict(node.value) == {}


def test_ast_dict_value_str() -> None:
    # value ast.Str legacy → .s
    tree = ast.parse("d = {'k': 'valor'}")
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            assert _ast_dict_to_dict(node.value) == {"k": "valor"}


def test_ast_dict_value_name() -> None:
    tree = ast.parse("x = 1\nd = {'k': x}")
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Dict):
            assert _ast_dict_to_dict(node.value) == {"k": "x"}


def test_ast_dict_value_not_no_constant() -> None:
    # `not x` con x Name (no Constant) → no entra al if interno
    tree = ast.parse("x = 1\nd = {'k': not x}")
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Dict):
            assert _ast_dict_to_dict(node.value) == {}


def test_plugin_entry() -> None:
    e = PluginEntry(meta=PluginMeta(name="p"), path=Path("/x/p.py"))
    assert e.meta.name == "p"


def test_plugin_result() -> None:
    r = PluginResult(ok=True, plugin="p", phase="pre")
    assert r.data == {}
    assert r.error == ""
    assert r.duration_ms == 0.0


def test_plugin_base_init() -> None:
    class _P(PluginBase):
        def on_load(self) -> None:
            pass

        def on_unload(self) -> None:
            pass

        def execute(self, context: dict | None = None) -> dict:
            return {}

    p = _P()
    assert p.meta.name == "_P"
    assert p.manifest is None
    assert repr(p) == "<Plugin _P>"
    p.rollback()  # no lanza


def test_plugin_base_abstracto() -> None:
    with pytest.raises(TypeError):
        PluginBase()


# ── manifest ─────────────────────────────────────────────────


def test_manifest_schema_y_required() -> None:
    assert "name" in MANIFEST_SCHEMA
    assert {"name"} == REQUIRED_FIELDS


def test_manifest_error() -> None:
    e = ManifestError("x")
    assert str(e) == "x"


def test_manifest_defaults() -> None:
    m = PluginManifest()
    assert m.api_version == "1.0.0"
    assert m.phases == ["always"]
    assert m.hooks == []


def test_parse_manifest_no_existe() -> None:
    assert parse_manifest(Path("/no/existe/plugin.yaml")) is None


def test_parse_manifest_json(tmp_path: object) -> None:
    f = Path(str(tmp_path)) / "plugin.json"
    f.write_text(json.dumps({"name": "p1", "version": "2.0", "dependencies": {"plugins": ["x"]}, "lifecycle": {"on_load": False}}))
    m = parse_manifest(f)
    assert m.name == "p1"
    assert m.version == "2.0"
    assert m.dependencies["plugins"] == ["x"]
    assert m.lifecycle["on_load"] is False
    assert m.lifecycle["on_config_change"] is False


def test_parse_manifest_json_sin_name(tmp_path: object) -> None:
    f = Path(str(tmp_path)) / "plugin.json"
    f.write_text('{"version": "1"}')
    m = parse_manifest(f)
    assert m.name == str(tmp_path).split("/")[-1]  # stem del parent


def test_parse_manifest_json_campos_desconocidos(tmp_path: object) -> None:
    f = Path(str(tmp_path)) / "plugin.json"
    f.write_text('{"name": "p", "campo_raro": 1, "otro": 2}')
    m = parse_manifest(f)
    assert m.name == "p"  # campos desconocidos → log.debug, sin error


def test_parse_manifest_json_invalido(tmp_path: object) -> None:
    f = Path(str(tmp_path)) / "plugin.json"
    f.write_text("{roto")
    assert parse_manifest(f) is None


def test_parse_manifest_json_no_dict(tmp_path: object) -> None:
    f = Path(str(tmp_path)) / "plugin.json"
    f.write_text("[1, 2]")
    assert parse_manifest(f) is None


def test_parse_manifest_yaml(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    import sys
    import types

    f = Path(str(tmp_path)) / "plugin.yaml"
    f.write_text("name: py1\nhooks: [pre]\n")

    fake_yaml = types.ModuleType("yaml")
    fake_yaml.safe_load = lambda s: {"name": "py1", "hooks": ["pre"]}
    monkeypatch.setitem(sys.modules, "yaml", fake_yaml)
    m = parse_manifest(f)
    assert m.name == "py1"
    assert m.hooks == ["pre"]


def test_parse_manifest_yaml_sin_yaml(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    import builtins

    f = Path(str(tmp_path)) / "plugin.yaml"
    f.write_text("name: x")
    real = builtins.__import__

    def _bloq(name: str, *a, **k):
        if name == "yaml":
            msg = "no yaml"
            raise ImportError(msg)
        return real(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", _bloq)
    assert parse_manifest(f) is None


def test_parse_manifest_yaml_error(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    import sys
    import types

    f = Path(str(tmp_path)) / "plugin.yaml"
    f.write_text("name: x")

    def _roto(s: str):
        msg = "yaml roto"
        raise ValueError(msg)

    fake_yaml = types.ModuleType("yaml")
    fake_yaml.safe_load = _roto
    monkeypatch.setitem(sys.modules, "yaml", fake_yaml)
    assert parse_manifest(f) is None


def test_parse_manifest_yaml_no_dict(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    import sys
    import types

    f = Path(str(tmp_path)) / "plugin.yaml"
    f.write_text("x: 1")

    fake_yaml = types.ModuleType("yaml")
    fake_yaml.safe_load = lambda s: [1, 2]
    monkeypatch.setitem(sys.modules, "yaml", fake_yaml)
    assert parse_manifest(f) is None


def test_parse_manifest_formato_no_soportado(tmp_path: object) -> None:
    f = Path(str(tmp_path)) / "plugin.toml"
    f.write_text("x = 1")
    assert parse_manifest(f) is None


def test_parse_manifest_lifecycle_no_dict(tmp_path: object) -> None:
    f = Path(str(tmp_path)) / "plugin.json"
    f.write_text(json.dumps({"name": "p", "lifecycle": "no-dict"}))
    m = parse_manifest(f)
    assert m.lifecycle == {"on_load": True, "on_unload": True, "on_config_change": False}


def test_find_manifest(tmp_path: object) -> None:
    d = Path(str(tmp_path))
    assert find_manifest(d) is None
    (d / "plugin.yaml").write_text("name: x")
    assert find_manifest(d).name == "plugin.yaml"
    (d / "plugin.json").write_text("{}")
    assert find_manifest(d).name == "plugin.yaml"  # yaml primero


def test_find_manifest_json_solo(tmp_path: object) -> None:
    d = Path(str(tmp_path))
    (d / "plugin.json").write_text("{}")
    assert find_manifest(d).name == "plugin.json"


# ── orquestador ──────────────────────────────────────────────


def test_orquestador_ram_alta() -> None:
    o = AgenteOrquestador()
    accion, razon = o.decidir({"hardware": {"ram_pct": 90}, "f821": 0}, {})
    assert accion == "PAUSAR"
    assert "90" in razon


def test_orquestador_f821_alto() -> None:
    o = AgenteOrquestador()
    accion, razon = o.decidir({"hardware": {"ram_pct": 10}, "f821": 15}, {})
    assert accion == "REPARAR"
    assert "15" in razon


def test_orquestador_refactorizar(monkeypatch: pytest.MonkeyPatch) -> None:
    o = AgenteOrquestador()
    monkeypatch.setattr(o, "_contar_pendientes", lambda: 3)
    accion, razon = o.decidir({"hardware": {"ram_pct": 10}, "f821": 0}, {})
    assert accion == "REFACTORIZAR"
    assert "3" in razon


def test_orquestador_esperar(monkeypatch: pytest.MonkeyPatch) -> None:
    o = AgenteOrquestador()
    monkeypatch.setattr(o, "_contar_pendientes", lambda: 0)
    _accion, _razon = o.decidir({"hardware": {"ram_pct": 10}, "f821": 0}, {})
    assert _accion == "ESPERAR"


def test_orquestador_contar_pendientes(monkeypatch: pytest.MonkeyPatch) -> None:
    import tempfile

    tmp = Path(tempfile.mkdtemp())
    (tmp / "largo.py").write_text("def f():\n" + "    x = 1\n" * 90 + "\n")
    (tmp / "corto.py").write_text("def g():\n    pass\n")
    (tmp / ".venv").mkdir()
    (tmp / ".venv" / "interno.py").write_text("def h():\n" + "    y = 1\n" * 90 + "\n")
    (tmp / "sintaxis_rota.py").write_text("def roto(:\n")
    monkeypatch.setattr(orq, "URA_ROOT", tmp)
    assert AgenteOrquestador._contar_pendientes() == 1  # solo largo.py (>80 líneas)


def test_orquestador_contar_pendientes_error(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Roto:
        def rglob(self, pattern: str):
            raise OSError("permiso")

    monkeypatch.setattr(orq, "URA_ROOT", _Roto())
    assert AgenteOrquestador._contar_pendientes() == 0


def test_orquestador_modelo() -> None:
    assert orq.MODELOS["orquestador"] == AgenteOrquestador.MODELO
