"""Tests para scripts/pro/tuneladora/preflight_system.py."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import scripts.pro.tuneladora.preflight_system as pf


def _cp(stdout: str = "", code: int = 0) -> SimpleNamespace:
    return SimpleNamespace(stdout=stdout, returncode=code, stderr="")


class TestCheckSystemdService:
    def test_no_existe(self, monkeypatch) -> None:
        monkeypatch.setattr(pf, "_run", lambda cmd: _cp(""))
        assert pf.check_systemd_service("nope") == {"exists": False, "active": False, "scopes": []}

    def test_system_active(self, monkeypatch) -> None:
        def fake(cmd: list[str]) -> SimpleNamespace:
            if "--property=LoadState" in cmd:
                return _cp("loaded")
            return _cp("active")

        monkeypatch.setattr(pf, "_run", fake)
        result = pf.check_systemd_service("ollama")
        assert result["exists"] is True
        assert result["active"] is True
        assert "system" in result["scopes"]

    def test_user_inactivo(self, monkeypatch) -> None:
        def fake(cmd: list[str]) -> SimpleNamespace:
            if "--user" in cmd:
                return _cp("loaded") if "--property=LoadState" in cmd else _cp("inactive")
            return _cp("")

        monkeypatch.setattr(pf, "_run", fake)
        result = pf.check_systemd_service("model-router")
        assert result["exists"] is True
        assert result["active"] is False
        assert "user(inactive)" in result["scopes"]


class TestCheckPort:
    def test_libre(self, monkeypatch) -> None:
        monkeypatch.setattr(pf, "_run", lambda cmd: _cp(""))
        assert pf.check_port(9999) == {"in_use": False, "process": None}

    def test_en_uso_con_proceso(self, monkeypatch) -> None:
        ss = 'LISTEN 0 4096 0.0.0.0:6333 users:(("qdrant",pid=123,fd=7))\n'
        monkeypatch.setattr(pf, "_run", lambda cmd: _cp(ss))
        result = pf.check_port(6333)
        assert result["in_use"] is True
        assert "qdrant" in result["process"]

    def test_otro_puerto(self, monkeypatch) -> None:
        ss = 'LISTEN 0 4096 0.0.0.0:6333 users:(("qdrant",pid=123,fd=7))\n'
        monkeypatch.setattr(pf, "_run", lambda cmd: _cp(ss))
        assert pf.check_port(8000)["in_use"] is False


class TestScreen:
    def test_existe(self, monkeypatch) -> None:
        monkeypatch.setattr(pf, "_run", lambda cmd: _cp("There is a screen on: 1234.ura"))
        assert pf.check_screen_exists("ura") is True

    def test_no_existe(self, monkeypatch) -> None:
        monkeypatch.setattr(pf, "_run", lambda cmd: _cp("No Sockets found"))
        assert pf.check_screen_exists("ura") is False


class TestManifest:
    def test_load_no_existe(self, monkeypatch, tmp_path) -> None:
        monkeypatch.setattr(pf, "MANIFEST", tmp_path / "nope.json")
        assert pf.load_manifest() == {}

    def test_load_ok(self, monkeypatch, tmp_path) -> None:
        path = tmp_path / "m.json"
        path.write_text('{"services": {"system": {"ollama": {"status": "active"}}}}')
        monkeypatch.setattr(pf, "MANIFEST", path)
        data = pf.load_manifest()
        assert "ollama" in data["services"]["system"]

    def test_check_manifest_service_system(self) -> None:
        manifest = {"services": {"system": {"ollama": {"status": "active"}}, "user": {}}}
        assert pf.check_manifest_service(manifest, "ollama") == {"status": "active"}

    def test_check_manifest_service_user(self) -> None:
        manifest = {"services": {"system": {}, "user": {"m-router": {"status": "active"}}}}
        assert pf.check_manifest_service(manifest, "m-router") == {"status": "active"}

    def test_check_manifest_service_no(self) -> None:
        assert pf.check_manifest_service({"services": {"system": {}, "user": {}}}, "x") is None


class TestPreflight:
    def test_duplicado_en_manifiesto(self, monkeypatch, capsys) -> None:
        monkeypatch.setattr(
            pf,
            "load_manifest",
            lambda: {"services": {"system": {"svc": {"description": "d", "port": "80"}}, "user": {}}},
        )
        monkeypatch.setattr(pf, "check_systemd_service", lambda n: {"exists": False, "active": False, "scopes": []})
        monkeypatch.setattr(pf, "check_port", lambda p: {"in_use": False, "process": None})
        monkeypatch.setattr(pf, "check_screen_exists", lambda n: False)
        assert pf.preflight("svc") is False
        assert "Ya existe en manifiesto" in capsys.readouterr().out

    def test_servicio_systemd_existe(self, monkeypatch) -> None:
        monkeypatch.setattr(pf, "load_manifest", lambda: {"services": {"system": {}, "user": {}}})
        monkeypatch.setattr(
            pf, "check_systemd_service", lambda n: {"exists": True, "active": True, "scopes": ["system"]}
        )
        assert pf.preflight("svc") is False

    def test_puerto_ocupado(self, monkeypatch) -> None:
        monkeypatch.setattr(
            pf, "load_manifest", lambda: {"services": {"system": {}, "user": {}}, "ports": {"8080": "web"}}
        )
        monkeypatch.setattr(pf, "check_systemd_service", lambda n: {"exists": False, "active": False, "scopes": []})
        monkeypatch.setattr(pf, "check_port", lambda p: {"in_use": True, "process": "web"})
        assert pf.preflight("svc", port=8080) is False

    def test_screen_ocupado(self, monkeypatch) -> None:
        monkeypatch.setattr(pf, "load_manifest", lambda: {"services": {"system": {}, "user": {}}})
        monkeypatch.setattr(pf, "check_systemd_service", lambda n: {"exists": False, "active": False, "scopes": []})
        monkeypatch.setattr(pf, "check_screen_exists", lambda n: True)
        assert pf.preflight("svc", screen="ura") is False

    def test_ok(self, monkeypatch, capsys) -> None:
        monkeypatch.setattr(pf, "load_manifest", lambda: {"services": {"system": {}, "user": {}}})
        monkeypatch.setattr(pf, "check_systemd_service", lambda n: {"exists": False, "active": False, "scopes": []})
        monkeypatch.setattr(pf, "check_port", lambda p: {"in_use": False, "process": None})
        monkeypatch.setattr(pf, "check_screen_exists", lambda n: False)
        assert pf.preflight("svc", port=8080, screen="ura") is True
        assert "OK para instalar" in capsys.readouterr().out


class TestSsPorts:
    def test_parsea(self) -> None:
        out = "LISTEN 0 1 0.0.0.0:6333 users:x\nLISTEN 0 1 0.0.0.0:8000 users:y\n"
        ports = pf._ss_ports(out)
        assert ports[0][0] == "6333"
        assert ports[1][0] == "8000"

    def test_ignora_no_listen(self) -> None:
        assert pf._ss_ports("ESTAB 0 1 0.0.0.0:80 x\n") == []


class TestAudit:
    def test_servicio_manifiesto_no_systemd(self, monkeypatch) -> None:
        manifest = {"services": {"system": {"fantasma": {"status": "active"}}, "user": {}}, "ports": {}}
        monkeypatch.setattr(pf, "check_systemd_service", lambda n: {"exists": False, "active": False, "scopes": []})
        issues: list[str] = []
        pf._audit_services(manifest, issues)
        assert any("NO en systemd" in i for i in issues)

    def test_puerto_libre_deberia_usarse(self, monkeypatch) -> None:
        manifest = {"services": {"system": {"svc": {"status": "active", "port": "6333"}}, "user": {}}, "ports": {}}
        monkeypatch.setattr(pf, "check_systemd_service", lambda n: {"exists": True, "active": True, "scopes": []})
        monkeypatch.setattr(pf, "check_port", lambda p: {"in_use": False, "process": None})
        issues: list[str] = []
        pf._audit_services(manifest, issues)
        assert any("libre" in i for i in issues)

    def test_audit_ports_no_registrado(self, monkeypatch) -> None:
        ss = "LISTEN 0 1 0.0.0.0:9000 users:x\n"
        monkeypatch.setattr(pf, "_run", lambda cmd: _cp(ss))
        issues: list[str] = []
        pf._audit_ports({"ports": {}}, issues)
        assert any("9000" in i and "NO en manifiesto" in i for i in issues)

    def test_audit_ports_huerfanos(self, monkeypatch) -> None:
        monkeypatch.setattr(pf, "_run", lambda cmd: _cp(""))
        issues: list[str] = []
        pf._audit_ports({"ports": {"8000": "api"}}, issues)
        assert any("no escuchando" in i for i in issues)

    def test_audit_current_state_sin_manifiesto(self, monkeypatch, tmp_path) -> None:
        monkeypatch.setattr(pf, "MANIFEST", tmp_path / "nope.json")
        result = pf.audit_current_state()
        assert result == {"manifest_exists": False, "issues": []}

    def test_audit_current_state_con_issues(self, monkeypatch, tmp_path) -> None:
        path = tmp_path / "m.json"
        path.write_text('{"services": {"system": {}, "user": {}}, "ports": {"8000": "api"}}')
        monkeypatch.setattr(pf, "MANIFEST", path)
        monkeypatch.setattr(pf, "_run", lambda cmd: _cp(""))
        result = pf.audit_current_state()
        assert result["manifest_exists"] is True
        assert result["issues"]


class TestMain:
    def test_sin_args_exit_1(self, monkeypatch) -> None:
        monkeypatch.setattr(pf.sys, "argv", ["preflight_system.py"])
        with pytest.raises(SystemExit) as e:
            pf._main()
        assert e.value.code == 1

    def test_audit(self, monkeypatch) -> None:
        monkeypatch.setattr(pf.sys, "argv", ["preflight_system.py", "audit"])
        monkeypatch.setattr(pf, "audit_current_state", lambda: {"manifest_exists": True, "issues": []})
        with pytest.raises(SystemExit) as e:
            pf._main()
        assert e.value.code == 0

    def test_install_sin_nombre(self, monkeypatch) -> None:
        monkeypatch.setattr(pf.sys, "argv", ["preflight_system.py", "install"])
        with pytest.raises(SystemExit) as e:
            pf._main()
        assert e.value.code == 1

    def test_install_ok(self, monkeypatch) -> None:
        monkeypatch.setattr(pf.sys, "argv", ["preflight_system.py", "install", "svc", "8080", "ura"])
        monkeypatch.setattr(pf, "preflight", lambda *a, **k: True)
        with pytest.raises(SystemExit) as e:
            pf._main()
        assert e.value.code == 0

    def test_comando_desconocido(self, monkeypatch) -> None:
        monkeypatch.setattr(pf.sys, "argv", ["preflight_system.py", "xyz"])
        with pytest.raises(SystemExit) as e:
            pf._main()
        assert e.value.code == 1
