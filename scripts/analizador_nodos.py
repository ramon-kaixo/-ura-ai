#!/usr/bin/env python3
"""Analizador de nodos — perfila y clasifica nodos Tailscale via SSH."""

import hashlib
import hmac
import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import paramiko
import requests

from core.utils import sanitize_log

logger = logging.getLogger("AnalizadorNodos")

GX10_URL = os.getenv("GX10_URL", "http://10.164.1.99:11434/api/chat")
MODEL = os.getenv("MODEL_CODIFICACION", "qwen2.5-coder:14b")
URA_BASE = Path(__file__).resolve().parent.parent
URA_TOKEN = os.getenv("URA_TOKEN", "")

EVENTOS_DIR = os.getenv(
    "EVENTOS_DIR",
    str(URA_BASE / "data" / "registry" / "eventos"),
)
PROCESADOS_DIR = os.getenv(
    "PROCESADOS_DIR",
    str(URA_BASE / "data" / "registry" / "procesados"),
)
FALLIDOS_DIR = os.getenv(
    "FALLIDOS_DIR",
    str(URA_BASE / "data" / "registry" / "fallidos"),
)
NODOS_DB = os.getenv("NODOS_DB", str(URA_BASE / "data" / "nodos_conocidos.json"))
REGISTRY_DB = str(URA_BASE / "data" / "registry.db")
FALLBACK_CONFIG = str(URA_BASE / "config" / "fallback_roles.json")
CURRENT_VERSION = "1"
MAX_RETRIES = 3
MIN_DISK_GB = 5


def sanitize_log_wrapper(message: str) -> str:
    """Wrapper para sanitize_log."""
    return sanitize_log(message)


def fallback_classify(perfil: dict[str, Any]) -> str:
    """Clasifica un nodo usando reglas de fallback sin LLM.

    Args:
        perfil: Diccionario con informacion del nodo.

    Returns:
        Rol asignado segun reglas de fallback.
    """
    try:
        with open(FALLBACK_CONFIG, encoding="utf-8") as fh:
            rules = json.load(fh)
    except Exception:
        rules = {"rules": [{"default": "worker"}]}

    for rule in rules.get("rules", []):
        cond = rule.get("if", {})
        if "default" in cond:
            return rule["then"]
        match = True
        for k, v in cond.items():
            if k == "so_contains":
                if v.lower() not in perfil.get("so", "").lower():
                    match = False
                    break
            elif perfil.get(k) != v:
                match = False
                break
        if match:
            return rule["then"]
    return "worker"


def classify_with_llm(perfil: dict[str, Any]) -> str:
    """Clasifica un nodo usando LLM basado en su perfil.

    Args:
        perfil: Diccionario con informacion del nodo.

    Returns:
        Rol asignado (worker, tpv-server, camaras, master, storage).
    """
    prompt = (
        f"Eres un clasificador de nodos para URA. Segun este perfil, "
        f"asigna uno de estos roles exactos: worker, tpv-server, camaras, master, storage.\n"
        f"Perfil: {json.dumps(perfil)}\n"
        f"Responde solo el rol."
    )
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
    }
    try:
        r = requests.post(GX10_URL, json=payload, timeout=10)
        rol = r.json()["message"]["content"].strip().lower()
        if rol in {"worker", "tpv-server", "camaras", "master", "storage"}:
            return rol
    except (requests.Timeout, requests.ConnectionError) as exc:
        logger.warning(sanitize_log_wrapper(f"LLM no disponible, usando fallback: {exc}"))
        return fallback_classify(perfil)
    except Exception as exc:
        logger.warning(sanitize_log_wrapper(f"Error clasificando con LLM: {exc}"))
        return fallback_classify(perfil)

    return fallback_classify(perfil)


def verificar_firma(evento: dict[str, Any], firma: str) -> bool:
    """Verifica la firma HMAC de un evento.

    Args:
        evento: Diccionario del evento.
        firma: Firma HMAC hexadecimal.

    Returns:
        True si la firma es valida.
    """
    if not URA_TOKEN:
        return True
    expected = hmac.new(
        URA_TOKEN.encode(), json.dumps(evento, sort_keys=True).encode(), hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, firma)


def registrar_evento_sqlite(timestamp: str, tipo: str, datos: dict[str, Any]) -> None:
    """Registra un evento en la base SQLite del registry.

    Args:
        timestamp: Timestamp ISO del evento.
        tipo: Tipo de evento.
        datos: Datos del evento.
    """
    import sqlite3

    Path(REGISTRY_DB).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(REGISTRY_DB)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS eventos (
            id TEXT PRIMARY KEY,
            timestamp TEXT,
            type TEXT,
            data TEXT
        )"""
    )
    evento_id = hashlib.sha256(f"{timestamp}{tipo}{json.dumps(datos)}".encode()).hexdigest()[:16]
    conn.execute(
        "INSERT OR REPLACE INTO eventos VALUES (?, ?, ?, ?)",
        (evento_id, timestamp, tipo, json.dumps(datos)),
    )
    conn.commit()
    conn.close()


def analizar_version_remota(ssh: paramiko.SSHClient) -> str:
    """Obtiene la version de scripts instalados en el nodo remoto.

    Args:
        ssh: Conexion SSH establecida.

    Returns:
        Version instalada o '0' si no existe.
    """
    try:
        stdin, stdout, stderr = ssh.exec_command(
            "cat /opt/ura/version.txt 2>/dev/null || echo '0'", timeout=5
        )
        return stdout.read().decode().strip()
    except Exception:
        return "0"


def analyze_node(hostname: str, ip: str) -> dict[str, Any] | None:
    """Analiza un nodo via SSH y devuelve su perfil.

    Args:
        hostname: Nombre del host.
        ip: Direccion IP del nodo.

    Returns:
        Diccionario con perfil del nodo o None si fallo.
    """
    logger.info(sanitize_log_wrapper(f"Analizando {hostname} ({ip})"))
    user = os.getenv("SSH_USER", "ramon")
    ssh_key = os.path.expanduser("~/.ssh/id_ura_gx10")

    info: dict[str, Any] = {"hostname": hostname, "ip": ip}
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    connected = False
    # Intentar conexion con clave SSH primero
    if os.path.isfile(ssh_key):
        try:
            ssh.connect(ip, username=user, key_filename=ssh_key, timeout=10)
            connected = True
            logger.info(f"Conectado a {ip} via clave SSH")
        except Exception as exc:
            logger.debug(f"SSH key fallo para {ip}: {exc}")

    # Fallback a password
    if not connected:
        try:
            from core.security.ssh_credentials import obtener_credenciales

            passwd = obtener_credenciales(user)
        except Exception:
            passwd = os.getenv("URA_SSH_PASSWORD")

        if not passwd:
            logger.error(sanitize_log_wrapper(f"Sin credenciales para {user}@{ip}"))
            return None

        try:
            ssh.connect(ip, username=user, password=passwd, timeout=10)
            connected = True
            logger.info(f"Conectado a {ip} via password")
        except Exception as exc:
            logger.warning(sanitize_log_wrapper(f"SSH password fallo para {ip}: {exc}"))
            return None

    if not connected:
        return None

    try:
        # Punto 4: Verificar version remota
        version_remota = analizar_version_remota(ssh)
        info["version_scripts"] = version_remota

        # Comparar con version actual
        with open(NODOS_DB, encoding="utf-8") as fh:
            nodos = json.load(fh)
        nodo_previo = next((n for n in nodos.get("nodos", []) if n["id"] == hostname), None)
        if (
            nodo_previo
            and nodo_previo.get("version_scripts") == version_remota
            and version_remota != "0"
        ):
            logger.info(
                f"Nodo {hostname} ya esta en la version actual ({version_remota}). No se redesplegara."
            )
            ssh.close()
            info["rol"] = nodo_previo.get("rol", "worker")
            info["actualizado"] = False
            return info

        # Recopilar perfil
        commands = {
            "distro": "cat /etc/os-release | grep PRETTY_NAME | cut -d= -f2",
            "memoria_mb": "free -m | awk '/Mem/{print $2}'",
            "cpu_cores": "nproc",
            "arch": "uname -m",
            "disco_total": "df -h / | tail -1 | awk '{print $2}'",
            "disco_libre": "df -h / | tail -1 | awk '{print $4}'",
            "docker": "command -v docker && echo si || echo no",
            "ollama": "command -v ollama && ollama --version 2>/dev/null || echo no",
            "python": "python3 --version 2>/dev/null || echo no",
            "gpu": "nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null || echo no",
            "vram": "nvidia-smi --query-gpu=memory.total --format=csv,noheader 2>/dev/null || echo 0",
            "tailscale_ver": "tailscale version 2>/dev/null || echo no",
            "ip_local": "hostname -I | awk '{print $1}'",
        }
        for k, cmd in commands.items():
            try:
                stdin, stdout, stderr = ssh.exec_command(cmd, timeout=5)
                val = stdout.read().decode().strip()
                info[k] = val if val else "no"
            except Exception:
                info[k] = "error"

        # Punto 13: Verificar espacio en disco
        disco_libre = info.get("disco_libre", "0G")
        if "G" in disco_libre:
            try:
                gb = float(disco_libre.replace("G", "").strip())
                if gb < MIN_DISK_GB:
                    logger.warning(
                        f"Nodo {hostname} tiene menos de {MIN_DISK_GB}GB libres ({disco_libre}). No se desplegara."
                    )
                    ssh.close()
                    return None
            except ValueError:
                pass

        ssh.close()
    except Exception as exc:
        logger.warning(sanitize_log_wrapper(f"SSH a {ip}: {exc}"))
        return {"hostname": hostname, "ip": ip, "error": str(exc)}

    rol = classify_with_llm(info)
    info["rol"] = rol
    info["actualizado"] = True
    return info


def procesar_evento(ev_file: Path) -> bool:
    """Procesa un evento de nuevo nodo.

    Args:
        ev_file: Ruta al archivo de evento.

    Returns:
        True si se proceso correctamente.
    """
    with open(ev_file, encoding="utf-8") as fh:
        evento = json.load(fh)

    # Punto 10: Verificar firma HMAC si existe
    firma = evento.get("firma", "")
    if firma and not verificar_firma(evento, firma):
        logger.warning(f"Firma invalida en evento {ev_file.name}")
        return False

    nodo = evento["nodo"]
    perfil = analyze_node(nodo["hostname"], nodo["ip"])
    if perfil:
        procesado_file = Path(PROCESADOS_DIR) / f"analizado_{nodo['hostname']}.json"
        with open(procesado_file, "w", encoding="utf-8") as fh:
            json.dump(perfil, fh, indent=2)
        logger.info(
            sanitize_log_wrapper(f"Nodo {nodo['hostname']} analizado: rol={perfil.get('rol')}")
        )

        # Punto 14: Registrar en SQLite
        timestamp = evento.get("timestamp", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
        registrar_evento_sqlite(timestamp, "nodo_analizado", perfil)
        return True
    return False


def main() -> None:
    """Procesa eventos de nuevos nodos pendientes de analisis."""
    logging.basicConfig(level=logging.INFO)
    Path(PROCESADOS_DIR).mkdir(parents=True, exist_ok=True)
    Path(FALLIDOS_DIR).mkdir(parents=True, exist_ok=True)

    # Punto 5: Verificar permisos de escritura
    if not os.access(EVENTOS_DIR, os.W_OK):
        logger.error("Sin permisos de escritura en el registry de eventos")
        sys.exit(1)

    for ev_file in Path(EVENTOS_DIR).glob("nuevo_nodo_*.json"):
        retries = 0
        while retries < MAX_RETRIES:
            if procesar_evento(ev_file):
                ev_file.rename(Path(PROCESADOS_DIR) / ev_file.name)
                break
            retries += 1
            logger.warning(f"Reintento {retries}/{MAX_RETRIES} para {ev_file.name}")
            time.sleep(5)
        else:
            ev_file.rename(Path(FALLIDOS_DIR) / ev_file.name)
            logger.error(f"Evento {ev_file.name} fallo {MAX_RETRIES} veces")
            notif_script = URA_BASE / "scripts" / "notificar.sh"
            if notif_script.exists():
                subprocess.run(
                    [
                        "bash",
                        str(notif_script),
                        f"Evento {ev_file.name} fallo {MAX_RETRIES} veces",
                        "error",
                        "all",
                    ],
                    capture_output=True,
                )


if __name__ == "__main__":
    main()
