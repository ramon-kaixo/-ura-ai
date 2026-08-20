"""Tests de cobertura para motor/scanner/collector_red.py (gate 85%, meta 100)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from motor.scanner import collector_red


class FakeResult:
    def __init__(self, ok: bool = True, stdout: str = "") -> None:
        self.ok = ok
        self.stdout = stdout


def _config(asus_host: str = "") -> MagicMock:
    config = MagicMock()
    config.asus_host = asus_host
    config.tailscale_iface = "tailscale0"
    return config


class TestEscaneoRed:
    @patch("motor.scanner.collector_red._executor")
    def test_estructura_completa(self, executor: MagicMock) -> None:
        executor.run.side_effect = [
            FakeResult(ok=True, stdout="default via 192.168.1.1 dev eth0"),
            FakeResult(ok=True, stdout="64 bytes from 8.8.8.8: time=12.3 ms"),
            FakeResult(ok=True, stdout="64 bytes from 8.8.8.8: time=9.1 ms"),
            FakeResult(ok=True, stdout="64 bytes from 8.8.8.8: time=8.1 ms"),
            FakeResult(ok=True, stdout="tailscale0: <BROADCAST,UP,LOWER_UP> mtu 1280"),
            FakeResult(ok=True, stdout='{"Peer": {"1": {"DNSName": "nodo.hetzner.", "Online": true}}}'),
            FakeResult(ok=True, stdout="64 bytes from 10.0.0.1: time=7.2 ms"),
        ]
        r = collector_red.escanear_red(_config(asus_host="10.0.0.1"))
        assert r["gateway"] == "192.168.1.1"
        assert r["internet"] is True
        assert r["dns_ok"] is True
        assert r["latencia_ms"] == 8
        assert r["tailscale_iface_up"] is True
        assert r["tailscale_peers"] == {"nodo.hetzner": {"online": True, "last_seen": "", "relay": ""}}
        assert r["exit_node_online"] is True
        assert r["peer_gateway_timems"] == 7

    @patch("motor.scanner.collector_red._executor")
    def test_sin_asus_host_no_peer_latencia(self, executor: MagicMock) -> None:
        executor.run.side_effect = [
            FakeResult(ok=True, stdout=""),
            FakeResult(ok=False),
            FakeResult(ok=False),
            FakeResult(ok=True, stdout=""),
            FakeResult(ok=True, stdout="{}"),
        ]
        r = collector_red.escanear_red(_config())
        assert r["gateway"] == ""
        assert r["internet"] is False
        assert r["dns_ok"] is False
        assert r["peer_gateway_timems"] == 999

    @patch("motor.scanner.collector_red._executor")
    def test_excepciones_devuelven_defaults(self, executor: MagicMock) -> None:
        executor.run.side_effect = RuntimeError("todo roto")
        r = collector_red.escanear_red(_config())
        assert r["gateway"] == ""
        assert r["internet"] is False
        assert r["latencia_ms"] == 999
        assert r["tailscale_peers"] == {}


class TestFunciones:
    @patch("motor.scanner.collector_red._executor")
    def test_get_gateway(self, executor: MagicMock) -> None:
        executor.run.return_value = FakeResult(ok=True, stdout="default via 10.0.0.1 dev wlan0")
        assert collector_red._get_gateway() == "10.0.0.1"

    @patch("motor.scanner.collector_red._executor")
    def test_get_gateway_corto(self, executor: MagicMock) -> None:
        executor.run.return_value = FakeResult(ok=True, stdout="default")
        assert collector_red._get_gateway() == ""

    @patch("motor.scanner.collector_red._executor")
    def test_ping_ok(self, executor: MagicMock) -> None:
        executor.run.return_value = FakeResult(ok=True)
        assert collector_red._ping("host") is True

    @patch("motor.scanner.collector_red._executor")
    def test_ping_error(self, executor: MagicMock) -> None:
        executor.run.side_effect = RuntimeError("no ping")
        assert collector_red._ping("host") is False

    @patch("motor.scanner.collector_red._executor")
    def test_latencia_parsea(self, executor: MagicMock) -> None:
        executor.run.return_value = FakeResult(ok=True, stdout="64 bytes from h: icmp_seq=1 ttl=64 time=14.5 ms")
        assert collector_red._latencia("h") == 14

    @patch("motor.scanner.collector_red._executor")
    def test_latencia_sin_match(self, executor: MagicMock) -> None:
        executor.run.return_value = FakeResult(ok=True, stdout="sin time=")
        assert collector_red._latencia("h") == 999

    @patch("motor.scanner.collector_red._executor")
    def test_iface_up(self, executor: MagicMock) -> None:
        executor.run.return_value = FakeResult(ok=True, stdout="UP,LOWER_UP")
        assert collector_red._iface_up("eth0") is True

    @patch("motor.scanner.collector_red._executor")
    def test_iface_down(self, executor: MagicMock) -> None:
        executor.run.return_value = FakeResult(ok=True, stdout="DOWN")
        assert collector_red._iface_up("eth0") is False

    @patch("motor.scanner.collector_red._executor")
    def test_tailscale_status(self, executor: MagicMock) -> None:
        executor.run.return_value = FakeResult(ok=True, stdout='{"Peer": {"A": {"DNSName": "pc1.", "Online": true, "LastSeen": "x", "Relay": "relay1"}}}')
        peers = collector_red._tailscale_status()
        assert peers == {"pc1": {"online": True, "last_seen": "x", "relay": "relay1"}}

    @patch("motor.scanner.collector_red._executor")
    def test_tailscale_status_json_error(self, executor: MagicMock) -> None:
        executor.run.return_value = FakeResult(ok=True, stdout="no json")
        assert collector_red._tailscale_status() == {}

    @patch("motor.scanner.collector_red.socket.gethostname", return_value="hetzner-01")
    def test_exit_node_hetzner_local(self, _gh: MagicMock) -> None:
        assert collector_red._check_exit_node({}) is True

    def test_exit_node_peer_online(self) -> None:
        peers = {"nodo-exit": {"online": True}}
        assert collector_red._check_exit_node(peers) is True

    def test_exit_node_peer_offline(self) -> None:
        peers = {"nodo-exit": {"online": False}, "pc1": {"online": True}}
        assert collector_red._check_exit_node(peers) is False
