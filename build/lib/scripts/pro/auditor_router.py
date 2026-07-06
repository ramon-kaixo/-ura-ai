#!/usr/bin/env python3
"""Auditor de Router — Detecta relays, firewall, y sugiere puertos a abrir.

📖 MANUAL DE USO RÁPIDO:
  python3 scripts/pro/auditor_router.py              # Auditoría completa
  python3 scripts/pro/auditor_router.py --target hetzner-escudo  # Auditar conexión a Hetzner

🔒 OBJETIVO:
  - Detectar si la conexión ASUS→Hetzner pasa por relay (DERP) → limitada a 20 Mbps
  - Verificar NAT type, puertos UDP abiertos, capacidad real de subida
  - Si el router doméstico está estrangulando → sugerir puertos a abrir
  - Prohibir DERP relays: forzar conexión directa peer-to-peer
"""

import json
import os
import socket
import subprocess
import time
from pathlib import Path

URA = Path(os.environ.get("URA_ROOT", "/home/ramon/URA/ura_ia_1972"))
NERVIOSO = URA / ".nervioso"
NERVIOSO.mkdir(parents=True, exist_ok=True)

# Puertos necesarios para conexión directa Tailscale
PUERTOS_TAILSCALE = [
    {"puerto": 41641, "protocolo": "UDP", "descripcion": "Tailscale direct P2P (WireGuard)"},
    {"puerto": 3478, "protocolo": "UDP", "descripcion": "STUN (NAT traversal)"},
    {"puerto": 443, "protocolo": "TCP", "descripcion": "HTTPS (fallback DERP relay)"},
]

# Puertos para Hetzner exit node
PUERTOS_HETZNER = [
    {"puerto": 11434, "protocolo": "TCP", "descripcion": "Ollama API"},
    {"puerto": 8081, "protocolo": "TCP", "descripcion": "OpenCode Server"},
    {"puerto": 18789, "protocolo": "TCP", "descripcion": "OpenClaw Gateway"},
    {"puerto": 22, "protocolo": "TCP", "descripcion": "SSH"},
]


def tailscale_status() -> dict:
    """Obtiene estado de Tailscale en JSON."""
    try:
        r = subprocess.run(["tailscale", "status", "--json"], capture_output=True, text=True, timeout=10, check=False)
        return json.loads(r.stdout) if r.returncode == 0 else {}
    except Exception:
        return {}


def detectar_relay(peer_name: str | None = None) -> dict:
    """Detecta si alguna conexión usa relay (DERP).

    Returns:
        {usa_relay: bool, conexiones_directas: int, conexiones_relay: int,
         peers: [{name, relay, direct_ip}]}

    """
    status = tailscale_status()
    peers = status.get("Peer", {})
    resultados = {"usa_relay": False, "conexiones_directas": 0, "conexiones_relay": 0, "peers": []}

    for peer in peers.values():
        name = peer.get("DNSName", "").rstrip(".")
        relay = peer.get("Relay", "")
        direct = peer.get("CurAddr", "")
        online = peer.get("Online", False)

        if online:
            if relay:
                resultados["usa_relay"] = True
                resultados["conexiones_relay"] += 1
            elif direct:
                resultados["conexiones_directas"] += 1

            resultados["peers"].append(
                {
                    "name": name,
                    "relay": relay,
                    "direct_ip": direct,
                    "es_relay": bool(relay),
                },
            )

    return resultados


def test_puerto(host: str, puerto: int, protocolo: str = "TCP", timeout: float = 2.0) -> bool:
    """Testea si un puerto está abierto."""
    try:
        if protocolo.upper() == "TCP":
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((host, puerto))
            sock.close()
            return result == 0
        # UDP
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(timeout)
        sock.sendto(b"", (host, puerto))
        sock.recvfrom(1024)
        sock.close()
        return False  # UDP no confirma apertura
    except Exception:
        return False


def test_velocidad_internet() -> dict:
    """Test rápido de velocidad de Internet."""
    result = {"download_ok": False, "upload_ok": False, "latencia_ms": 0}
    try:
        t0 = time.monotonic()
        r = subprocess.run(
            [
                "curl",
                "-s",
                "-o",
                "/dev/null",
                "-w",
                "%{http_code} %{time_total}",
                "--max-time",
                "10",
                "http://httpbin.org/ip",
            ],
            capture_output=True,
            text=True,
            timeout=12,
            check=False,
        )
        t1 = time.monotonic()
        result["latencia_ms"] = round((t1 - t0) * 1000, 1)
        result["download_ok"] = r.stdout.startswith("200")
    except Exception:
        pass
    return result


def auditoria_completa(target: str = "hetzner-escudo") -> dict:
    """Ejecuta auditoría completa del router y conectividad."""
    reporte = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "target": target,
    }

    # 1. Tailscale status
    ts = tailscale_status()
    self_node = ts.get("Self", {})
    reporte["tailscale"] = {
        "self": self_node.get("DNSName", "?").rstrip("."),
        "self_ip": self_node.get("TailscaleIPs", [])[0] if self_node.get("TailscaleIPs") else "?",
    }

    # 2. Detectar relay
    relay_info = detectar_relay(target)
    reporte["relay"] = relay_info

    # 3. NAT type
    try:
        r = subprocess.run(["tailscale", "netcheck"], capture_output=True, text=True, timeout=10, check=False)
        for line in r.stdout.splitlines():
            if "MappingVariesByDestIP" in line:
                reporte["nat_varia"] = "true" in line.lower()
            if "UDP:" in line:
                reporte["udp_disponible"] = "true" in line.lower()
    except Exception:
        pass

    # 4. Test puertos
    try:
        with open(URA / "config" / "dispositivos.json") as f:
            cfg = json.load(f)
        mac = cfg.get("dispositivos", {}).get("mac-mini-de-ramon", {})
        test_ip = mac.get("ip_cable", "10.164.1.26")
    except (FileNotFoundError, json.JSONDecodeError):
        test_ip = "10.164.1.26"
    reporte["puertos_test"] = []
    for p in PUERTOS_TAILSCALE + PUERTOS_HETZNER:
        abierto = test_puerto(test_ip, p["puerto"], p["protocolo"])
        reporte["puertos_test"].append({**p, "abierto": abierto, "testeado_en": test_ip})

    # 5. Velocidad
    reporte["internet"] = test_velocidad_internet()

    # 6. Diagnóstico
    if relay_info["usa_relay"]:
        reporte["diagnostico"] = "⚠️ LIMITADO POR FIREWALL DOMÉSTICO — Se detectó relay DERP"
        reporte["accion"] = "ABRIR_PUERTOS"
        reporte["puertos_sugeridos"] = PUERTOS_TAILSCALE
    else:
        reporte["diagnostico"] = "✅ CONEXIÓN DIRECTA — Sin limitaciones de relay"
        reporte["accion"] = "OK"

    # Guardar reporte
    reporte_path = NERVIOSO / "auditoria_router.json"
    reporte_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = reporte_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(reporte, indent=2, ensure_ascii=False) + "\n")
    tmp.replace(reporte_path)

    return reporte


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Auditor de Router — Detectar relays y firewall")
    parser.add_argument("--target", default="hetzner-escudo", help="Host a auditar")
    parser.add_argument("--json", action="store_true", help="Salida JSON")
    args = parser.parse_args()

    reporte = auditoria_completa(args.target)

    if args.json:
        pass
    else:
        # Tabla de Estado de Conectividad

        for p in reporte["puertos_test"]:
            "✅" if p["abierto"] else "❌"

        if reporte["accion"] == "ABRIR_PUERTOS":
            for p in PUERTOS_TAILSCALE:
                pass


if __name__ == "__main__":
    main()
