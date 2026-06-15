import logging, subprocess, json, socket
from core.config import UraConfig

log = logging.getLogger("ura.scanner.red")

HOST_PING = "8.8.8.8"
HOST_DNS = "google.com"

def escanear_red(config: UraConfig) -> dict:
    """Escanea conectividad de red, tailscale y peers."""
    r = {
        "gateway": "",
        "internet": False,
        "dns_ok": False,
        "latencia_ms": 0,
        "tailscale_peers": {},
        "tailscale_iface_up": False,
        "peer_gateway_timems": 999,
        "exit_node_online": False,
    }
    r["gateway"] = _get_gateway()
    r["internet"] = _ping(HOST_PING)
    r["dns_ok"] = _ping(HOST_DNS) or r["internet"]
    r["latencia_ms"] = _latencia(HOST_PING)
    r["tailscale_iface_up"] = _iface_up(config.tailscale_iface)
    r["tailscale_peers"] = _tailscale_status()
    r["exit_node_online"] = _check_exit_node(r["tailscale_peers"])
    if config.asus_host:
        r["peer_gateway_timems"] = _latencia(config.asus_host)
    return r

def _get_gateway() -> str:
    """Obtiene la IP del gateway por defecto."""
    try:
        r = subprocess.run(["ip", "route", "show", "default"], capture_output=True, text=True, timeout=5)
        parts = r.stdout.strip().split()
        return parts[2] if len(parts) >= 3 else ""
    except Exception as e:
        log.debug("gateway falló: %s", e)
        return ""

def _ping(host: str) -> bool:
    """Ping básico a un host."""
    try:
        r = subprocess.run(["ping", "-c1", "-W2", host], capture_output=True, timeout=5)
        return r.returncode == 0
    except Exception as e:
        log.debug("ping %s falló: %s", host, e)
        return False

def _latencia(host: str) -> int:
    """Mide latencia en ms a un host via ping."""
    try:
        r = subprocess.run(["ping", "-c1", "-W3", host], capture_output=True, text=True, timeout=6)
        for line in r.stdout.split("\n"):
            if "time=" in line:
                ms = line.split("time=")[1].split(" ")[0]
                return int(float(ms.replace("ms", "")))
        return 999
    except Exception as e:
        log.debug("latencia %s falló: %s", host, e)
        return 999

def _iface_up(iface: str) -> bool:
    """Verifica si una interfaz de red está levantada."""
    try:
        r = subprocess.run(["ip", "link", "show", iface], capture_output=True, text=True, timeout=3)
        return "UP" in r.stdout and "LOWER_UP" in r.stdout
    except Exception as e:
        log.debug("iface_up %s falló: %s", iface, e)
        return False

def _tailscale_status() -> dict:
    """Obtiene estado de peers Tailscale."""
    peers = {}
    try:
        r = subprocess.run(["tailscale", "status", "--json"], capture_output=True, text=True, timeout=5)
        data = json.loads(r.stdout)
        for k, v in data.get("Peer", {}).items():
            peers[v.get("DNSName", k).rstrip(".")] = {
                "online": v.get("Online", False),
                "last_seen": v.get("LastSeen", ""),
                "relay": v.get("Relay", ""),
            }
    except Exception as e:
        log.debug("tailscale status falló: %s", e)
    return peers

def _check_exit_node(peers: dict) -> bool:
    """Determina si el exit node de Tailscale está online."""
    host = socket.gethostname().lower()
    if "hetzner" in host:
        return True
    for name, info in peers.items():
        if "hetzner" in name.lower() or "exit" in name.lower():
            if info.get("online"):
                return True
    return False
