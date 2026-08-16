"""Tests de cobertura para core/resolver_red.py (lineas y ramas faltantes).

Cubre las lineas 206, 211 y 219-220 de main() (ramas sin --json y ejecucion
real del modulo como __main__) y ramas no ejercitadas por test_resolver_red.py:
coincidencia inversa de nombre DNS, peers sin TailscaleIPs, timeout de ping
con float, parseo de latencia invalida, seleccionar_ruta con inventario None,
match por nombre_dns, dispositivo sin IPs, inventario vacio en estado_red y
cable ok pero lento sin fallback util.
"""

from __future__ import annotations

import json
import runpy
from types import SimpleNamespace
from unittest import mock

import core.resolver_red as rr


class TestMainSinJson:
    """Ramas de main() sin --json (lineas 206 y 213-216)."""

    def test_ping_sin_json(self, monkeypatch) -> None:
        monkeypatch.setattr("sys.argv", ["resolver_red.py", "--ping", "gx10"])
        monkeypatch.setattr(
            rr, "seleccionar_ruta", mock.Mock(return_value={"ok": False, "ip": None, "latencia_ms": 999})
        )
        rr.main()  # no debe lanzar

    def test_ping_sin_json_ok_true(self, monkeypatch) -> None:
        monkeypatch.setattr("sys.argv", ["resolver_red.py", "--ping", "gx10"])
        monkeypatch.setattr(rr, "seleccionar_ruta", mock.Mock(return_value={"ok": True, "ip": "1.2.3.4"}))
        rr.main()  # no debe lanzar

    def test_status_con_json(self, monkeypatch) -> None:
        monkeypatch.setattr("sys.argv", ["resolver_red.py", "--status", "--json"])
        monkeypatch.setattr(rr, "estado_red", mock.Mock(return_value={"dispositivos": {}}))
        rr.main()  # no debe lanzar

    def test_status_sin_json_detalle(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "sys.argv",
            ["resolver_red.py", "--status"],
        )
        monkeypatch.setattr(
            rr,
            "estado_red",
            mock.Mock(
                return_value={
                    "dispositivos": {
                        "a": {"ok": True, "ip": "1.1.1.1", "latencia_ms": 1},
                        "b": {"ok": False, "ip": None, "latencia_ms": 999},
                    }
                }
            ),
        )
        rr.main()  # no debe lanzar

    def test_sin_argumentos_usa_status(self, monkeypatch) -> None:
        monkeypatch.setattr("sys.argv", ["resolver_red.py"])
        monkeypatch.setattr(
            rr, "estado_red", mock.Mock(return_value={"dispositivos": {"a": {"ok": True, "ip": "1", "latencia_ms": 1}}})
        )
        rr.main()  # no debe lanzar


class TestMainComoScript:
    """Ejecucion real del modulo como __main__ (lineas 219-220)."""

    def test_resolver_ok(self, monkeypatch) -> None:
        monkeypatch.setattr("sys.argv", ["resolver_red.py", "--resolver", "gx10"])
        monkeypatch.setattr("socket.gethostbyname", mock.Mock(return_value="10.0.0.5"))
        runpy.run_path(str(rr.__file__), run_name="__main__")

    def test_ping_como_script(self, monkeypatch) -> None:
        monkeypatch.setattr("sys.argv", ["resolver_red.py", "--ping", "gx10"])
        monkeypatch.setattr("socket.gethostbyname", mock.Mock(side_effect=__import__("socket").gaierror("nxdomain")))
        res = SimpleNamespace(returncode=0, stdout="64 bytes ... time=0.8 ms\n")
        monkeypatch.setattr("subprocess.run", mock.Mock(return_value=res))
        runpy.run_path(str(rr.__file__), run_name="__main__")

    def test_status_como_script(self, monkeypatch) -> None:
        monkeypatch.setattr("sys.argv", ["resolver_red.py"])
        monkeypatch.setattr("socket.gethostbyname", mock.Mock(side_effect=__import__("socket").gaierror("nxdomain")))
        res = SimpleNamespace(returncode=0, stdout="64 bytes ... time=1.2 ms\n")
        monkeypatch.setattr("subprocess.run", mock.Mock(return_value=res))
        runpy.run_path(str(rr.__file__), run_name="__main__")


class TestResolverDnsRamas:
    """Ramas extra de resolver_dns no cubiertas por el test base."""

    def test_tailscale_sin_match_cae_inventario(self, monkeypatch, tmp_path) -> None:
        monkeypatch.setattr("socket.gethostbyname", mock.Mock(side_effect=__import__("socket").gaierror("nxdomain")))
        data = {"Peer": {"p1": {"DNSName": "otra-maquina.", "TailscaleIPs": ["100.9.9.9"]}}}
        res = SimpleNamespace(returncode=0, stdout=json.dumps(data))
        monkeypatch.setattr(rr.subprocess, "run", mock.Mock(return_value=res))
        inv_path = tmp_path / "dispositivos.json"
        inv_path.write_text(json.dumps({"dispositivos": {"gx10": {"ip_cable": "10.164.1.99"}}}))
        monkeypatch.setattr(rr, "INVENTARIO_PATH", inv_path)
        assert rr.resolver_dns("gx10") == "10.164.1.99"

    def test_match_inverso_hostname_contiene_nombre(self, monkeypatch) -> None:
        monkeypatch.setattr("socket.gethostbyname", mock.Mock(side_effect=__import__("socket").gaierror("nxdomain")))
        data = {"Peer": {"p1": {"DNSName": "gx10.", "TailscaleIPs": ["100.72.103.12"]}}}
        res = SimpleNamespace(returncode=0, stdout=json.dumps(data))
        monkeypatch.setattr(rr.subprocess, "run", mock.Mock(return_value=res))
        assert rr.resolver_dns("gx10-64c3") == "100.72.103.12"

    def test_peer_sin_ips_ignorado(self, monkeypatch, tmp_path) -> None:
        monkeypatch.setattr("socket.gethostbyname", mock.Mock(side_effect=__import__("socket").gaierror("nxdomain")))
        data = {"Peer": {"p1": {"DNSName": "mac-mini.", "TailscaleIPs": []}}}
        res = SimpleNamespace(returncode=0, stdout=json.dumps(data))
        monkeypatch.setattr(rr.subprocess, "run", mock.Mock(return_value=res))
        inv_path = tmp_path / "dispositivos.json"
        inv_path.write_text(json.dumps({"dispositivos": {"mac-mini": {"ip_tailscale": "100.1.1.1"}}}))
        monkeypatch.setattr(rr, "INVENTARIO_PATH", inv_path)
        assert rr.resolver_dns("mac-mini") == "100.1.1.1"

    def test_inventario_match_por_nombre_dns(self, monkeypatch, tmp_path) -> None:
        monkeypatch.setattr("socket.gethostbyname", mock.Mock(side_effect=__import__("socket").gaierror("nxdomain")))
        res = SimpleNamespace(returncode=1, stdout="")
        monkeypatch.setattr(rr.subprocess, "run", mock.Mock(return_value=res))
        inv_path = tmp_path / "dispositivos.json"
        inv_path.write_text(json.dumps({"dispositivos": {"gx10": {"nombre_dns": "gx10-64c3", "ip_cable": "10.0.0.9"}}}))
        monkeypatch.setattr(rr, "INVENTARIO_PATH", inv_path)
        assert rr.resolver_dns("gx10-64c3") == "10.0.0.9"


class TestPingLatenciaRamas:
    """Ramas extra de ping_latencia: timeout float y latencia no numerica."""

    def test_timeout_float_convierte_int(self, monkeypatch) -> None:
        res = SimpleNamespace(returncode=0, stdout="time=2.5 ms\n")
        mocked = mock.Mock(return_value=res)
        monkeypatch.setattr(rr.subprocess, "run", mocked)
        ok, lat = rr.ping_latencia("10.0.0.1", timeout=2.5)
        assert (ok, lat) == (True, 2.5)
        args = mocked.call_args.args[0]
        assert args == ["ping", "-c", "1", "-W", "2", "10.0.0.1"]

    def test_latencia_no_numerica_es_fallo(self, monkeypatch) -> None:
        res = SimpleNamespace(returncode=0, stdout="time=abc ms\n")
        monkeypatch.setattr(rr.subprocess, "run", mock.Mock(return_value=res))
        ok, lat = rr.ping_latencia("10.0.0.1")
        assert (ok, lat) == (False, 999)


class TestSeleccionarRutaRamas:
    """Ramas extra de seleccionar_ruta: inventario None y match nombre_dns."""

    def test_inventario_none_usa_cargar_inventario(self, monkeypatch) -> None:
        inv = {"dispositivos": {"gx10": {"ip_cable": "10.164.1.99"}}}
        monkeypatch.setattr(rr, "cargar_inventario", mock.Mock(return_value=inv))
        monkeypatch.setattr(rr, "ping_latencia", mock.Mock(return_value=(True, 1.0)))
        r = rr.seleccionar_ruta("gx10")
        assert r["ruta"] == "cable"

    def test_match_por_nombre_dns(self, monkeypatch) -> None:
        inv = {"dispositivos": {"gx10": {"nombre_dns": "gx10-64c3", "ip_tailscale": "100.72.103.12"}}}
        monkeypatch.setattr(rr, "ping_latencia", mock.Mock(return_value=(True, 10.0)))
        r = rr.seleccionar_ruta("gx10-64c3", inv)
        assert r["ruta"] == "tailscale"

    def test_sin_ninguna_ip_es_down(self, monkeypatch) -> None:
        inv = {"dispositivos": {"sin_ip": {"rol": "?"}}}
        r = rr.seleccionar_ruta("sin_ip", inv)
        assert r["ruta"] == "down"
        assert r["ok"] is False

    def test_cable_lento_y_tailscale_down(self, monkeypatch) -> None:
        inv = {"dispositivos": {"gx10": {"ip_cable": "10.164.1.99", "ip_tailscale": "100.72.103.12"}}}
        monkeypatch.setattr(rr, "ping_latencia", mock.Mock(side_effect=[(True, 8.0), (False, 999)]))
        r = rr.seleccionar_ruta("gx10", inv)
        assert r["ruta"] == "down"

    def test_cable_ok_pero_latencia_limite(self, monkeypatch) -> None:
        inv = {"dispositivos": {"gx10": {"ip_cable": "10.164.1.99"}}}
        monkeypatch.setattr(rr, "ping_latencia", mock.Mock(return_value=(True, 5.0)))
        r = rr.seleccionar_ruta("gx10", inv)
        assert r["ruta"] == "down"
        assert r["metodo"] == "sin_conexion"


class TestEstadoRedRamas:
    """Ramas extra de estado_red: inventario vacio."""

    def test_inventario_vacio(self, monkeypatch) -> None:
        monkeypatch.setattr(rr, "cargar_inventario", mock.Mock(return_value={"dispositivos": {}}))
        estado = rr.estado_red()
        assert estado["total"] == 0
        assert estado["online"] == 0
        assert estado["offline"] == 0
        assert estado["por_ruta"] == {}
