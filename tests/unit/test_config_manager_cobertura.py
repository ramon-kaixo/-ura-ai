"""Cobertura 100x100 de motor/core/config_manager.py (TASK-20260815-003).

Cubre el Config Manager completo: detección de perfil por SO/hostname,
expansión de paths (~ y resolve), carga y merge de perfiles (global_defaults
+ perfil), errores de perfil faltante, acceso de solo lectura, validación de
directorios y permisos, validación de esquema (secciones/keys/roles) y la
validación JSON Schema con los 4 caminos (sin jsonschema, schema ausente,
errores de validación, JSON inválido, excepción genérica).

Lo externo (fs, platform, jsonschema) se aísla con monkeypatch: el archivo de
config se escribe en tmp_path y se apunta vía _CONFIG_PATH/_URA_ROOT; el
comportamiento lógico (merge, defaults, ramas de error) es el real del módulo.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

import motor.core.config_manager as cm


def _set_config(monkeypatch: pytest.MonkeyPatch, config: dict[str, Any]) -> None:
    """Sustituye CONFIG del módulo por una config sintética."""
    monkeypatch.setattr(cm, "CONFIG", config)


def _valid_config() -> dict[str, Any]:
    """Config sintética que pasa validate_schema() sin errores."""
    return {
        "ollama": {"host": "localhost", "port": 11434},
        "router": {"host": "127.0.0.1", "port": 8000},
        "paths": {"data": "/opt/ura/data", "logs": "/opt/ura/logs", "maintenance_logs": "/opt/ura/mt-logs"},
        "maintenance": {
            "thresholds": {"cpu": 0.9},
            "exclude_patterns": ["*.lock"],
            "allowed_temp_dirs": ["/tmp/ura-tmp"],
            "allowed_log_dirs": ["/tmp/ura-logs"],
        },
        "models": {"razonamiento": "m1", "codigo_complejo": "m2", "codigo_rapido": "m3", "respuesta_rapida": "m4"},
        "fallback_model": "respuesta_rapida",
        "cache_ttl": 60,
        "llm": {"provider": "ollama"},
        "_raw_profiles": {"linux_asus": {}, "darwin_mac": {}, "linux_terminal": {}},
        "patrones_clasificacion": {"clave": "valor"},
        "hostname": "gx10-64c3",
        "role": "server",
    }


def _write_raw(tmp_path: Path, raw: dict[str, Any]) -> Path:
    """Escribe un archivo system_config.json sintético en tmp_path."""
    cfg_file = tmp_path / "system_config.json"
    cfg_file.write_text(json.dumps(raw), encoding="utf-8")
    return cfg_file


class TestDetectProfileKey:
    """_detect_profile_key: selección de perfil por SO y hostname."""

    def test_darwin(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(cm.platform, "system", lambda: "Darwin")
        assert cm._detect_profile_key() == "darwin_mac"

    def test_linux_asus(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(cm.platform, "system", lambda: "Linux")
        monkeypatch.setattr(cm.platform, "node", lambda: "GX10-64C3")
        assert cm._detect_profile_key() == "linux_asus"

    def test_linux_terminal(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(cm.platform, "system", lambda: "Linux")
        monkeypatch.setattr(cm.platform, "node", lambda: "macbook-pro")
        assert cm._detect_profile_key() == "linux_terminal"

    def test_sistema_no_soportado(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(cm.platform, "system", lambda: "Windows")
        with pytest.raises(RuntimeError, match="no soportado"):
            cm._detect_profile_key()


class TestExpandPaths:
    """_expand_paths: expansión de ~ en paths, swarm y allowed_log_dirs."""

    def test_expande_paths_swarm_y_logs(self, tmp_path: Path) -> None:
        base = tmp_path / "ura"
        cfg: dict[str, Any] = {
            "paths": {"data": str(base / "data")},
            "swarm": {"devices_path": "~/devices"},
            "maintenance": {"allowed_log_dirs": ["~/a", str(base / "b")]},
        }
        out = cm._expand_paths(cfg)
        assert out["paths"]["data"] == str(base.joinpath("data").resolve())
        assert out["swarm"]["devices_path"].startswith(str(Path.home()))
        assert out["maintenance"]["allowed_log_dirs"][0].startswith(str(Path.home()))
        assert out["maintenance"]["allowed_log_dirs"][1] == str(base.joinpath("b").resolve())

    def test_sin_swarm_ni_allowed_log_dirs(self) -> None:
        cfg: dict[str, Any] = {"paths": {"data": "/x"}}
        out = cm._expand_paths(cfg)
        assert out == {"paths": {"data": str(Path("/x").resolve())}}


class TestLoadRawConfig:
    """_load_raw_config: carga del JSON desde _CONFIG_PATH."""

    def test_carga_json(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        cfg_file = _write_raw(tmp_path, {"global_defaults": {"g": 1}})
        monkeypatch.setattr(cm, "_CONFIG_PATH", cfg_file)
        assert cm._load_raw_config() == {"global_defaults": {"g": 1}}


class TestLoadConfig:
    """load_config: merge global_defaults + perfil, _raw_profiles y errores."""

    def test_merge_y_expansion(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        raw = {
            "global_defaults": {"g": 1, "shared": "global", "hostname": "default"},
            "profiles": {
                "linux_asus": {"p": 2, "shared": "perfil", "paths": {"data": "~/ura"}},
                "darwin_mac": {},
                "linux_terminal": {},
            },
        }
        cfg_file = _write_raw(tmp_path, raw)
        monkeypatch.setattr(cm, "_CONFIG_PATH", cfg_file)
        monkeypatch.setattr(cm, "_detect_profile_key", lambda: "linux_asus")

        cfg = cm.load_config()
        assert cfg["g"] == 1
        assert cfg["p"] == 2
        assert cfg["shared"] == "perfil"
        assert cfg["hostname"] == "default"
        assert set(cfg["_raw_profiles"]) == {"linux_asus", "darwin_mac", "linux_terminal"}
        assert cfg["paths"]["data"] == str(Path("~/ura").expanduser().resolve())

    def test_perfil_faltante(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        cfg_file = _write_raw(tmp_path, {"global_defaults": {}, "profiles": {"linux_asus": {}}})
        monkeypatch.setattr(cm, "_CONFIG_PATH", cfg_file)
        monkeypatch.setattr(cm, "_detect_profile_key", lambda: "no_existe")
        with pytest.raises(RuntimeError, match="no encontrado"):
            cm.load_config()


class TestAccessors:
    """Accesores de solo lectura sobre CONFIG con defaults."""

    def test_get_base_dir(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _set_config(monkeypatch, {"paths": {"data": "/opt/ura/data"}})
        assert cm.get_base_dir() == Path("/opt/ura")

    def test_get_ollama_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _set_config(monkeypatch, {"ollama": {"host": "10.0.0.1", "port": 12345}})
        assert cm.get_ollama_url() == "http://10.0.0.1:12345"

    def test_get_ollama_urls_completas(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _set_config(monkeypatch, {"ollama": {"host": "h", "port": 1, "remote_host": "r"}})
        assert cm.get_ollama_urls() == {"primary": "http://h:1", "fallback": "http://r:1"}

    def test_get_ollama_urls_sin_remote_host(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _set_config(monkeypatch, {"ollama": {"host": "h", "port": 1}})
        assert cm.get_ollama_urls() == {"primary": "http://h:1", "fallback": "http://h:1"}

    def test_get_ollama_urls_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _set_config(monkeypatch, {})
        assert cm.get_ollama_urls() == {"primary": "http://localhost:11434", "fallback": "http://localhost:11434"}

    def test_get_role(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _set_config(monkeypatch, {"role": "server"})
        assert cm.get_role() == "server"

    def test_get_role_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _set_config(monkeypatch, {})
        assert cm.get_role() == "unknown"

    def test_get_hostname(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _set_config(monkeypatch, {"hostname": "gx10-64c3"})
        assert cm.get_hostname() == "gx10-64c3"

    def test_get_hostname_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _set_config(monkeypatch, {})
        assert cm.get_hostname() == "unknown"


class TestValidateConfig:
    """validate_config: existencia y permisos de escritura de directorios."""

    def test_todo_ok(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        data = tmp_path / "data"
        logs = tmp_path / "logs"
        data.mkdir()
        logs.mkdir()
        cfg = _valid_config()
        cfg["paths"] = {"data": str(data), "logs": str(logs), "maintenance_logs": str(logs)}
        cfg["maintenance"] = {
            "allowed_temp_dirs": [str(data)],
            "allowed_log_dirs": [str(logs)],
        }
        _set_config(monkeypatch, cfg)
        assert cm.validate_config() == []

    def test_directorios_no_existen(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        cfg = _valid_config()
        cfg["paths"] = {
            "data": str(tmp_path / "no-data"),
            "logs": str(tmp_path / "no-logs"),
            "maintenance_logs": str(tmp_path / "no-mt"),
        }
        cfg["maintenance"] = {
            "allowed_temp_dirs": [str(tmp_path / "no-tmp")],
            "allowed_log_dirs": [str(tmp_path / "no-log")],
        }
        _set_config(monkeypatch, cfg)
        warnings = cm.validate_config()
        assert set(warnings) == {
            f"Directorio no existe: {tmp_path / 'no-data'}",
            f"Directorio no existe: {tmp_path / 'no-logs'}",
            f"Directorio no existe: {tmp_path / 'no-mt'}",
            f"Directorio temp no existe: {tmp_path / 'no-tmp'}",
            f"Directorio log no existe: {tmp_path / 'no-log'}",
        }

    def test_sin_permisos_escritura(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        data = tmp_path / "data"
        logs = tmp_path / "logs"
        data.mkdir()
        logs.mkdir()
        real_access = cm.os.access
        monkeypatch.setattr(
            cm.os,
            "access",
            lambda path, mode: False if Path(path) == data else real_access(path, mode),
        )
        cfg = _valid_config()
        cfg["paths"] = {"data": str(data), "logs": str(logs), "maintenance_logs": str(logs)}
        cfg["maintenance"] = {"allowed_temp_dirs": [str(data)], "allowed_log_dirs": [str(logs)]}
        _set_config(monkeypatch, cfg)
        assert cm.validate_config() == [f"Sin permisos de escritura: {data}"]

    def test_path_key_faltante(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        data = tmp_path / "data"
        data.mkdir()
        cfg = _valid_config()
        cfg["paths"] = {"data": str(data), "logs": str(data)}
        cfg["maintenance"] = {"allowed_temp_dirs": [str(data)], "allowed_log_dirs": [str(data)]}
        _set_config(monkeypatch, cfg)
        assert cm.validate_config() == []


class TestValidateSchema:
    """validate_schema: secciones, keys, perfiles raw y patrones."""

    def test_valido(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _set_config(monkeypatch, _valid_config())
        assert cm.validate_schema() == []

    def test_falta_seccion(self, monkeypatch: pytest.MonkeyPatch) -> None:
        cfg = _valid_config()
        del cfg["ollama"]
        _set_config(monkeypatch, cfg)
        assert cm.validate_schema() == ["Falta seccion requerida: 'ollama'"]

    def test_faltan_keys_y_secciones_escalares(self, monkeypatch: pytest.MonkeyPatch) -> None:
        cfg = _valid_config()
        del cfg["router"]["port"]
        del cfg["fallback_model"]
        del cfg["cache_ttl"]
        _set_config(monkeypatch, cfg)
        assert cm.validate_schema() == [
            "Falta key 'port' en seccion 'router'",
            "Falta seccion requerida: 'fallback_model'",
            "Falta seccion requerida: 'cache_ttl'",
        ]

    def test_perfiles_y_patrones_faltantes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        cfg = _valid_config()
        cfg["_raw_profiles"] = {"linux_asus": {}}
        del cfg["patrones_clasificacion"]
        _set_config(monkeypatch, cfg)
        assert cm.validate_schema() == [
            "Perfil 'darwin_mac' no encontrado en system_config.json",
            "Perfil 'linux_terminal' no encontrado en system_config.json",
            "Falta 'patrones_clasificacion' en global_defaults",
        ]


class TestValidateSchemaJson:
    """validate_schema_json: los 4 caminos de jsonschema + errores JSON."""

    @staticmethod
    def _write_conf(tmp_path: Path, schema: str, raw_config: str) -> None:
        conf_dir = tmp_path / "config"
        conf_dir.mkdir(parents=True)
        (conf_dir / "schema.json").write_text(schema, encoding="utf-8")
        (conf_dir / "system_config.json").write_text(raw_config, encoding="utf-8")

    def test_sin_jsonschema(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setitem(sys.modules, "jsonschema", None)
        assert cm.validate_schema_json() == []

    def test_schema_no_encontrado(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(cm, "_URA_ROOT", tmp_path)
        assert cm.validate_schema_json() == ["Schema file not found: config/schema.json"]

    def test_errores_de_validacion(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        self._write_conf(
            tmp_path,
            json.dumps({"type": "object", "properties": {"foo": {"type": "string"}}}),
            json.dumps({"foo": 42}),
        )
        monkeypatch.setattr(cm, "_URA_ROOT", tmp_path)
        assert cm.validate_schema_json() == ["foo: 42 is not of type 'string'"]

    def test_json_invalido(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        self._write_conf(
            tmp_path,
            json.dumps({"type": "object"}),
            '{"foo": ',
        )
        monkeypatch.setattr(cm, "_URA_ROOT", tmp_path)
        assert cm.validate_schema_json()[0].startswith("JSON invalido:")

    def test_excepcion_generica(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        self._write_conf(
            tmp_path,
            json.dumps({"type": "object"}),
            json.dumps({"foo": 1}),
        )
        jsonschema_mod = sys.modules.get("jsonschema")
        if jsonschema_mod is None:
            pytest.skip("jsonschema no instalado: la rama except genérico no es alcanzable")
        monkeypatch.setattr(cm, "_URA_ROOT", tmp_path)
        monkeypatch.setattr(jsonschema_mod, "Draft202012Validator", _BoomValidator)
        assert cm.validate_schema_json() == ["boom"]


class _BoomValidator:
    """Validador que falla en construcción para cubrir el except genérico."""

    def __init__(self, schema: Any) -> None:
        raise RuntimeError("boom")
