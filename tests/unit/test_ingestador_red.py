"""Tests para core/ingestador_red.py."""
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest import mock

import pytest

import core.ingestador_red as ir


@pytest.fixture
def inventario(tmp_path) -> dict:
    ir.INVENTARIO_PATH = tmp_path / "dispositivos.json"
    ir.INVENTARIO_PATH.write_text(
        json.dumps(
            {
                "dispositivos": {
                    "gx10-64c3": {"nombre_dns": "gx10-64c3", "rol": "servidor_principal", "estado": "online", "tipo": "gpu", "ram_gb": 128},
                    "mac-mini-de-ramon": {"nombre_dns": "mac-mini-de-ramon", "rol": "cliente_dev", "estado": "online", "tipo": "mac", "ram_gb": 16},
                    "iphone-ramon": {"nombre_dns": "iphone", "rol": "cliente", "estado": "online", "tipo": "ios", "ram_gb": 6},
                }
            }
        )
    )
    return ir.cargar_inventario()


class TestCargarInventario:
    def test_sin_archivo(self, tmp_path) -> None:
        ir.INVENTARIO_PATH = tmp_path / "nope.json"
        assert ir.cargar_inventario() == {"dispositivos": {}}

    def test_archivo_corrupto(self, tmp_path) -> None:
        f = tmp_path / "d.json"
        f.write_text("no json")
        ir.INVENTARIO_PATH = f
        assert ir.cargar_inventario() == {"dispositivos": {}}


class TestTailscaleSSH:
    def test_ok(self, monkeypatch) -> None:
        res = SimpleNamespace(returncode=0, stdout="out", stderr="")
        monkeypatch.setattr(ir.subprocess, "run", mock.Mock(return_value=res))
        code, out, err = ir.tailscale_ssh("host", "cmd")
        assert (code, out, err) == (0, "out", "")

    def test_timeout(self, monkeypatch) -> None:
        monkeypatch.setattr(ir.subprocess, "run", mock.Mock(side_effect=__import__("subprocess").TimeoutExpired("ssh", 30)))
        code, out, err = ir.tailscale_ssh("host", "cmd")
        assert (code, out, err) == (-1, "", "timeout")

    def test_excepcion(self, monkeypatch) -> None:
        monkeypatch.setattr(ir.subprocess, "run", mock.Mock(side_effect=OSError("no ssh")))
        code, out, err = ir.tailscale_ssh("host", "cmd")
        assert code == -1
        assert "no ssh" in err


class TestDistribuirTarea:
    def test_pesada_asus(self, inventario, monkeypatch) -> None:
        monkeypatch.setattr(ir, "tailscale_ssh", mock.Mock(return_value=(0, "ok", "")))
        r = ir.distribuir_tarea("refactorizar", "main.py")
        assert r["asignado_a"] == "gx10-64c3"
        assert r["rol"] == "servidor_principal"
        assert r["ok"] is True
        assert "pipeline_supremo.py" in r["comando"]

    def test_media_mac(self, inventario, monkeypatch) -> None:
        monkeypatch.setattr(ir, "tailscale_ssh", mock.Mock(return_value=(0, "ok", "")))
        r = ir.distribuir_tarea("analizar")
        assert r["asignado_a"] == "mac-mini-de-ramon"

    def test_ligera_primero_no_ios(self, inventario, monkeypatch) -> None:
        monkeypatch.setattr(ir, "tailscale_ssh", mock.Mock(return_value=(0, "ok", "")))
        r = ir.distribuir_tarea("monitorear")
        assert r["asignado_a"] == "gx10-64c3"  # primer online no-ios

    def test_sin_candidato_fallback_localhost(self, monkeypatch) -> None:
        monkeypatch.setattr(ir, "cargar_inventario", mock.Mock(return_value={"dispositivos": {}}))
        r = ir.distribuir_tarea("analizar")
        assert r == {"asignado_a": "localhost", "tarea": "analizar", "ok": True, "metodo": "local_fallback"}

    def test_comando_ping(self, inventario, monkeypatch) -> None:
        monkeypatch.setattr(ir, "tailscale_ssh", mock.Mock(return_value=(0, "pong", "")))
        r = ir.distribuir_tarea("ping")
        assert "pong" in r["comando"] or r["comando"] == "echo 'pong'"

    def test_comando_desconocido(self, inventario, monkeypatch) -> None:
        monkeypatch.setattr(ir, "tailscale_ssh", mock.Mock(return_value=(1, "", "error")))
        r = ir.distribuir_tarea("tarea_extraña")
        assert r["ok"] is False
        assert "Tarea tarea_extraña" in r["comando"]


class TestEstadoDispositivos:
    def test_mixto(self, inventario, monkeypatch) -> None:
        def fake_ssh(host, cmd, timeout=30):
            if host == "gx10-64c3":
                return 0, "ok", ""
            return 1, "", "offline"

        monkeypatch.setattr(ir, "tailscale_ssh", mock.Mock(side_effect=fake_ssh))
        estado = ir.estado_dispositivos()
        assert estado["total"] == 3
        assert estado["online"] == 1
        assert estado["offline"] == 2
        assert estado["dispositivos"]["gx10-64c3"]["online"] is True
        assert estado["dispositivos"]["iphone-ramon"]["online"] is False


class TestMain:
    def test_ssh(self, monkeypatch) -> None:
        monkeypatch.setattr("sys.argv", ["ingestador_red.py", "--ssh", "host"])
        monkeypatch.setattr(ir, "tailscale_ssh", mock.Mock(return_value=(0, "out", "")))
        with pytest.raises(SystemExit) as e:
            ir.main()
        assert e.value.code == 0

    def test_enviar(self, monkeypatch) -> None:
        monkeypatch.setattr("sys.argv", ["ingestador_red.py", "--enviar", "backup", "gx10-64c3"])
        monkeypatch.setattr(ir, "tailscale_ssh", mock.Mock(return_value=(0, "ok", "")))
        with pytest.raises(SystemExit) as e:
            ir.main()
        assert e.value.code == 0

    def test_distribuir_ok(self, monkeypatch) -> None:
        monkeypatch.setattr("sys.argv", ["ingestador_red.py", "--distribuir", "ping", "--json"])
        monkeypatch.setattr(ir, "distribuir_tarea", mock.Mock(return_value={"ok": True}))
        with pytest.raises(SystemExit) as e:
            ir.main()
        assert e.value.code == 0

    def test_distribuir_fail(self, monkeypatch) -> None:
        monkeypatch.setattr("sys.argv", ["ingestador_red.py", "--distribuir", "ping"])
        monkeypatch.setattr(ir, "distribuir_tarea", mock.Mock(return_value={"ok": False}))
        with pytest.raises(SystemExit) as e:
            ir.main()
        assert e.value.code == 1

    def test_status(self, monkeypatch) -> None:
        monkeypatch.setattr("sys.argv", ["ingestador_red.py", "--status"])
        monkeypatch.setattr(ir, "estado_dispositivos", mock.Mock(return_value={"dispositivos": {"a": {"online": True, "ip_cable": "1", "ip_tailscale": "2"}}}))
        ir.main()  # no debe lanzar
