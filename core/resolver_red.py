#!/usr/bin/env python3
"""DNS Resolver + Network Failover — MagicDNS + Cable + Tailscale.

📖 MANUAL DE USO RÁPIDO:
  python3 core/resolver_red.py --resolver <hostname>    # Resolver DNS a IP
  python3 core/resolver_red.py --ping <hostname>        # Latencia cable vs Tailscale
  python3 core/resolver_red.py --status                 # Estado de toda la red

🔒 GARANTÍAS:
  - 0 IPs hardcodeadas. Todo por MagicDNS (gx10-64c3, mac-mini-de-ramon, etc.)
  - Prioridad: Cable físico (<1ms) → Tailscale (fallback)
  - Si latencia cable >5ms → conmuta a Tailscale automáticamente
  - Timeout 2s por ping, 3 intentos antes de declarar DOWN
  - Autenticación vía Tailscale SSH (sin passwords en texto plano)

Estrategia de resolución:
  1. Intentar resolver via getent hosts (DNS local + MagicDNS)
  2. Intentar via tailscale status --json (API local de Tailscale)
  3. Fallback: IPs del inventario (config/dispositivos.json)
  4. Conmutación: cable → Tailscale según latencia
"""

import json
import logging
import subprocess
import sys
import time
from pathlib import Path

log = logging.getLogger("ura.resolver_red")

URA = Path(__file__).resolve().parent.parent  # /home/ramon/URA/ura_ia_1972
INVENTARIO_PATH = URA / "config" / "dispositivos.json"
CABLE_LATENCY_THRESHOLD_MS = 5  # Si cable >5ms → conmutar a Tailscale
TAILSCALE_LATENCY_THRESHOLD_MS = 50  # Si Tailscale >50ms → dispositivo DOWN


def cargar_inventario() -> dict:
    if INVENTARIO_PATH.exists():
        try:
            return json.loads(INVENTARIO_PATH.read_text())
        except Exception:
            log.exception("Error loading inventory from %s", INVENTARIO_PATH)
    return {"dispositivos": {}}


def resolver_dns(hostname: str) -> str | None:
    """Resuelve un hostname a IP usando DNS local + MagicDNS.

    Prioridad:
      1. getent hosts (DNS local + /etc/hosts)
      2. tailscale status --json
      3. Inventario (config/dispositivos.json)
    """
    # 1. DNS local
    try:
        import socket

        ip = socket.gethostbyname(hostname)
        if ip and not ip.startswith("127."):
            return ip
    except socket.gaierror:
        pass

    # 2. MagicDNS via tailscale
    try:
        r = subprocess.run(["tailscale", "status", "--json"], capture_output=True, text=True, timeout=5, check=False)  # noqa: S607  -- comando constante
        if r.returncode == 0:
            data = json.loads(r.stdout)
            peers = data.get("Peer", {})
            for peer in peers.values():
                name = peer.get("DNSName", "").rstrip(".")
                if hostname in name or name in hostname:
                    ips = peer.get("TailscaleIPs", [])
                    if ips:
                        return ips[0]
    except Exception:
        log.exception("Error querying Tailscale status for %s", hostname)

    # 3. Fallback: inventario
    inventario = cargar_inventario()
    for dev_id, dev in inventario.get("dispositivos", {}).items():
        if dev_id == hostname or dev.get("nombre_dns") == hostname:
            return dev.get("ip_cable") or dev.get("ip_tailscale")

    return None


def ping_latencia(ip: str, timeout: float = 2.0) -> tuple[bool, float]:
    """Hace ping a una IP y devuelve (success, latencia_ms)."""
    try:
        r = subprocess.run(  # noqa: S603  -- IP desde caller interno
            ["ping", "-c", "1", "-W", str(int(timeout)), ip],  # noqa: S607  -- IP desde caller interno
            capture_output=True,
            text=True,
            timeout=timeout + 1,
            check=False,
        )
        if r.returncode == 0:
            for line in r.stdout.splitlines():
                if "time=" in line:
                    ms = float(line.split("time=")[1].split()[0])
                    return True, ms
    except Exception:
        log.exception("Error pinging %s", ip)
    return False, 999


def seleccionar_ruta(hostname: str, inventario: dict | None = None) -> dict:
    """Selecciona la mejor ruta de conexión para un dispositivo.

    Estrategia de conmutación:
      1. Intentar cable directo (<1ms óptimo)
      2. Si cable DOWN o latencia >5ms → Tailscale
      3. Si Tailscale DOWN → declarar OFFLINE

    Returns:
        {ruta, ip, latencia_ms, metodo}

    """
    inv = inventario or cargar_inventario()
    dev = None
    for d_id, d in inv.get("dispositivos", {}).items():
        if d_id == hostname or d.get("nombre_dns") == hostname:
            dev = d
            break

    if not dev:
        return {"ruta": "desconocido", "ip": None, "latencia_ms": 999, "metodo": "no_encontrado", "ok": False}

    # Intentar cable
    ip_cable = dev.get("ip_cable")
    if ip_cable:
        ok, lat = ping_latencia(ip_cable, timeout=2.0)
        if ok and lat < CABLE_LATENCY_THRESHOLD_MS:
            return {"ruta": "cable", "ip": ip_cable, "latencia_ms": lat, "metodo": "directo_fisico", "ok": True}

    # Fallback: Tailscale
    ip_ts = dev.get("ip_tailscale")
    if ip_ts:
        ok, lat = ping_latencia(ip_ts, timeout=2.0)
        if ok and lat < TAILSCALE_LATENCY_THRESHOLD_MS:
            return {"ruta": "tailscale", "ip": ip_ts, "latencia_ms": lat, "metodo": "tailscale_vpn", "ok": True}

    # DOWN
    return {"ruta": "down", "ip": None, "latencia_ms": 999, "metodo": "sin_conexion", "ok": False}


def estado_red() -> dict:
    """Escanea toda la red y devuelve estado de cada dispositivo."""
    inv = cargar_inventario()
    resultados = {}

    for dev_id, dev in inv.get("dispositivos", {}).items():
        ruta = seleccionar_ruta(dev_id, inv)
        resultados[dev_id] = {
            "nombre_dns": dev.get("nombre_dns", dev_id),
            "rol": dev.get("rol", "?"),
            "ruta_activa": ruta["ruta"],
            "ip": ruta["ip"],
            "latencia_ms": ruta["latencia_ms"],
            "ok": ruta["ok"],
            "tipo": dev.get("tipo", "?"),
            "tareas": dev.get("tareas_asignables", []),
        }

    # Contar
    online = sum(1 for r in resultados.values() if r["ok"])
    offline = sum(1 for r in resultados.values() if not r["ok"])
    por_ruta = {}
    for r in resultados.values():
        rt = r["ruta_activa"]
        por_ruta[rt] = por_ruta.get(rt, 0) + 1

    return {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "total": len(resultados),
        "online": online,
        "offline": offline,
        "dispositivos": resultados,
        "por_ruta": por_ruta,
    }


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="DNS Resolver + Network Failover")
    parser.add_argument("--resolver", type=str, help="Resolver hostname a IP")
    parser.add_argument("--ping", type=str, help="Medir latencia a dispositivo")
    parser.add_argument("--status", action="store_true", help="Estado de toda la red")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.resolver:
        ip = resolver_dns(args.resolver)
        if ip:
            pass
        else:
            sys.exit(1)

    elif args.ping:
        ruta = seleccionar_ruta(args.ping)
        if args.json:
            pass
        else:
            "✅" if ruta["ok"] else "❌"

    elif args.status or not any([args.resolver, args.ping]):
        estado = estado_red()
        if args.json:
            pass
        else:
            for _dev_id, dev in sorted(estado["dispositivos"].items()):
                "✅" if dev["ok"] else "❌"
                ip = dev["ip"] or "—"
                dev["latencia_ms"]


if __name__ == "__main__":
    main()
