"""Tests para core/resolver_red.py."""
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest import mock

import pytest

import core.resolver_red as rr


@pytest.fixture
def inventario(tmp_path) -> dict:
    rr.INVENTARIO_PATH = tmp_path / "dispositivos.json"
    rr.INVENTARIO_PATH.write_text(
        json.dumps(
            {
                "dispositivos": {
                    "gx10": {"nombre_dns": "gx10-64c3", "ip_cable": "10.164.1.99", "ip_tailscale": "100.72.103.12", "rol": "servidor", "tipo": "gpu", "tareas_asignables": ["refactor"]},
                    "mac": {"nombre_dns": "mac-mini", "ip_cable": "10.164.1.26", "ip_tailscale": "100.123.81.101", "rol": "dev"},
                }
            }
        )
    )
    return rr.cargar_inventario()


class TestCargarInventario:
    def test_sin_archivo(self, tmp_path) -> None:
        rr.INVENTARIO_PATH = tmp_path / "nope.json"
        assert rr.cargar_inventario() == {"dispositivos": {}}

    def test_archivo_corrupto(self, tmp_path) -> None:
        f = tmp_path / "d.json"
        f.write_text("no json")
        rr.INVENTARIO_PATH = f
        assert rr.cargar_inventario() == {"dispositivos": {}}

    def test_ok(self, inventario) -> None:
        assert "gx10" in inventario["dispositivos"]


class TestResolverDns:
    def test_dns_local_ok(self, monkeypatch) -> None:
        sock = mock.Mock()
        sock.gethostbyname.return_value = "10.1.2.3"
        monkeypatch.setattr("socket.gethostbyname", lambda h: "10.1.2.3")
        assert rr.resolver_dns("host") == "10.1.2.3"

    def test_dns_local_127_ignorado(self, monkeypatch) -> None:
        monkeypatch.setattr("socket.gethostbyname", lambda h: "127.0.0.1")
        monkeypatch.setattr(rr.subprocess, "run", mock.Mock(return_value=SimpleNamespace(returncode=1, stdout="")))
        monkeypatch.setattr(rr, "cargar_inventario", mock.Mock(return_value={"dispositivos": {}}))
        assert rr.resolver_dns("host") is None

    def test_tailscale_fallback(self, monkeypatch) -> None:
        monkeypatch.setattr("socket.gethostbyname", mock.Mock(side_effect=__import__("socket").gaierror("nxdomain")))
        data = {"Peer": {"p1": {"DNSName": "mac-mini-de-ramon.", "TailscaleIPs": ["100.1.2.3"]}}}
        res = SimpleNamespace(returncode=0, stdout=json.dumps(data))
        monkeypatch.setattr(rr.subprocess, "run", mock.Mock(return_value=res))
        assert rr.resolver_dns("mac-mini") == "100.1.2.3"

    def test_inventario_fallback(self, monkeypatch, inventario) -> None:
        monkeypatch.setattr("socket.gethostbyname", mock.Mock(side_effect=__import__("socket").gaierror("nxdomain")))
        res = SimpleNamespace(returncode=1, stdout="")
        monkeypatch.setattr(rr.subprocess, "run", mock.Mock(return_value=res))
        assert rr.resolver_dns("gx10") == "10.164.1.99"

    def test_no_encontrado(self, monkeypatch, inventario) -> None:
        monkeypatch.setattr("socket.gethostbyname", mock.Mock(side_effect=__import__("socket").gaierror("nxdomain")))
        res = SimpleNamespace(returncode=1, stdout="")
        monkeypatch.setattr(rr.subprocess, "run", mock.Mock(return_value=res))
        assert rr.resolver_dns("desconocido") is None

    def test_tailscale_error(self, monkeypatch) -> None:
        monkeypatch.setattr("socket.gethostbyname", mock.Mock(side_effect=__import__("socket").gaierror("nxdomain")))
        monkeypatch.setattr(rr.subprocess, "run", mock.Mock(side_effect=OSError("no tailscale")))
        monkeypatch.setattr(rr, "cargar_inventario", mock.Mock(return_value={"dispositivos": {}}))
        assert rr.resolver_dns("x") is None


class TestPingLatencia:
    def test_ok(self, monkeypatch) -> None:
        out = "64 bytes from 10.0.0.1: icmp_seq=1 ttl=64 time=1.23 ms\n"
        res = SimpleNamespace(returncode=0, stdout=out)
        monkeypatch.setattr(rr.subprocess, "run", mock.Mock(return_value=res))
        ok, lat = rr.ping_latencia("10.0.0.1")
        assert ok is True
        assert lat == 1.23

    def test_fail(self, monkeypatch) -> None:
        res = SimpleNamespace(returncode=1, stdout="")
        monkeypatch.setattr(rr.subprocess, "run", mock.Mock(return_value=res))
        ok, lat = rr.ping_latencia("10.0.0.1")
        assert ok is False
        assert lat == 999

    def test_sin_time_en_output(self, monkeypatch) -> None:
        res = SimpleNamespace(returncode=0, stdout="sin time aqui\n")
        monkeypatch.setattr(rr.subprocess, "run", mock.Mock(return_value=res))
        ok, lat = rr.ping_latencia("10.0.0.1")
        assert ok is False

    def test_excepcion(self, monkeypatch) -> None:
        monkeypatch.setattr(rr.subprocess, "run", mock.Mock(side_effect=OSError("no ping")))
        ok, lat = rr.ping_latencia("10.0.0.1")
        assert ok is False


class TestSeleccionarRuta:
    def test_no_encontrado(self, inventario) -> None:
        r = rr.seleccionar_ruta("inexistente", inventario)
        assert r == {"ruta": "desconocido", "ip": None, "latencia_ms": 999, "metodo": "no_encontrado", "ok": False}

    def test_cable_ok(self, inventario, monkeypatch) -> None:
        monkeypatch.setattr(rr, "ping_latencia", mock.Mock(return_value=(True, 0.5)))
        r = rr.seleccionar_ruta("gx10", inventario)
        assert r == {"ruta": "cable", "ip": "10.164.1.99", "latencia_ms": 0.5, "metodo": "directo_fisico", "ok": True}

    def test_cable_lento_conmuta_tailscale(self, inventario, monkeypatch) -> None:
        monkeypatch.setattr(rr, "ping_latencia", mock.Mock(side_effect=[(True, 8.0), (True, 20.0)]))
        r = rr.seleccionar_ruta("gx10", inventario)
        assert r["ruta"] == "tailscale"
        assert r["ip"] == "100.72.103.12"

    def test_cable_down_tailscale_ok(self, inventario, monkeypatch) -> None:
        monkeypatch.setattr(rr, "ping_latencia", mock.Mock(side_effect=[(False, 999), (True, 10.0)]))
        r = rr.seleccionar_ruta("gx10", inventario)
        assert r["ruta"] == "tailscale"

    def test_todo_down(self, inventario, monkeypatch) -> None:
        monkeypatch.setattr(rr, "ping_latencia", mock.Mock(return_value=(False, 999)))
        r = rr.seleccionar_ruta("gx10", inventario)
        assert r["ruta"] == "down"
        assert r["ok"] is False

    def test_tailscale_lento_down(self, inventario, monkeypatch) -> None:
        monkeypatch.setattr(rr, "ping_latencia", mock.Mock(side_effect=[(False, 999), (True, 60.0)]))
        r = rr.seleccionar_ruta("gx10", inventario)
        assert r["ruta"] == "down"

    def test_sin_ip_cable_solo_tailscale(self, inventario, monkeypatch) -> None:
        inv = {"dispositivos": {"solo_ts": {"ip_tailscale": "100.1.1.1"}}}
        monkeypatch.setattr(rr, "ping_latencia", mock.Mock(return_value=(True, 5.0)))
        r = rr.seleccionar_ruta("solo_ts", inv)
        assert r["ruta"] == "tailscale"


class TestEstadoRed:
    def test_completo(self, inventario, monkeypatch) -> None:
        monkeypatch.setattr(rr, "ping_latencia", mock.Mock(return_value=(True, 1.0)))
        estado = rr.estado_red()
        assert estado["total"] == 2
        assert estado["online"] == 2
        assert estado["offline"] == 0
        assert estado["por_ruta"]["cable"] == 2
        assert estado["dispositivos"]["gx10"]["rol"] == "servidor"
        assert estado["dispositivos"]["mac"]["tipo"] == "?"

    def test_mixto(self, inventario, monkeypatch) -> None:
        def fake_ping(ip, timeout=2.0):
            if ip == "10.164.1.99":
                return True, 1.0
            return False, 999

        monkeypatch.setattr(rr, "ping_latencia", mock.Mock(side_effect=fake_ping))
        estado = rr.estado_red()
        assert estado["online"] == 1
        assert estado["offline"] == 1


class TestMain:
    def test_resolver_ok(self, monkeypatch) -> None:
        monkeypatch.setattr(rr.sys, "argv", ["resolver_red.py", "--resolver", "gx10"]) if hasattr(rr, "sys") else None
        monkeypatch.setattr("sys.argv", ["resolver_red.py", "--resolver", "gx10"])
        monkeypatch.setattr(rr, "resolver_dns", mock.Mock(return_value="1.2.3.4"))
        rr.main()  # no debe lanzar

    def test_resolver_error(self, monkeypatch) -> None:
        monkeypatch.setattr("sys.argv", ["resolver_red.py", "--resolver", "nope"])
        monkeypatch.setattr(rr, "resolver_dns", mock.Mock(return_value=None))
        with pytest.raises(RuntimeError, match="No se pudo resolver"):
            rr.main()

    def test_ping(self, monkeypatch) -> None:
        monkeypatch.setattr("sys.argv", ["resolver_red.py", "--ping", "gx10", "--json"])
        monkeypatch.setattr(rr, "seleccionar_ruta", mock.Mock(return_value={"ok": True}))
        rr.main()  # no debe lanzar

    def test_status(self, monkeypatch) -> None:
        monkeypatch.setattr("sys.argv", ["resolver_red.py", "--status"])
        monkeypatch.setattr(rr, "estado_red", mock.Mock(return_value={"dispositivos": {"a": {"ok": True, "ip": "1", "latencia_ms": 1}}}))
        rr.main()  # no debe lanzar
