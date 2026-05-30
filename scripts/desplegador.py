#!/usr/bin/env python3
"""Desplegador — ejecuta planes de despliegue en nodos remotos con rollback."""

import json
import logging
import os
import subprocess
import time
from pathlib import Path
from typing import Any

import paramiko

from core.utils import sanitize_log

logger = logging.getLogger("Desplegador")

URA_BASE = Path(__file__).resolve().parent.parent
PLANES_DIR = URA_BASE / "data" / "planes"
NODOS_DB = URA_BASE / "data" / "nodos_conocidos.json"
EVENTOS_DIR = URA_BASE / "data" / "registry" / "eventos"


def ejecutar_paso(ssh: paramiko.SSHClient, paso: dict[str, str]) -> bool:
    """Ejecuta un paso del plan en el nodo remoto.

    Args:
        ssh: Conexion SSH establecida.
        paso: Diccionario con comando y verificacion opcional.

    Returns:
        True si el paso se ejecuto correctamente.
    """
    cmd = paso["comando"]
    logger.info(sanitize_log(f"Ejecutando: {cmd}"))
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=120)
    exit_status = stdout.channel.recv_exit_status()
    if exit_status != 0:
        err = stderr.read().decode()
        logger.error(sanitize_log(f"Fallo: {err}"))
        return False
    # Verificacion opcional
    if "verificacion" in paso:
        vcmd = paso["verificacion"]
        stdin, stdout, stderr = ssh.exec_command(vcmd, timeout=30)
        if stdout.channel.recv_exit_status() != 0:
            logger.warning(f"Verificacion fallo: {vcmd}")
            return False
    return True


def desplegar(nodo_id: str, plan: dict[str, Any]) -> bool:
    """Despliega un plan completo en un nodo remoto.

    Args:
        nodo_id: Identificador del nodo.
        plan: Plan de despliegue con lista de pasos.

    Returns:
        True si el despliegue fue exitoso.
    """
    with open(NODOS_DB, encoding="utf-8") as fh:
        nodos = json.load(fh)
    nodo_info = next((n for n in nodos["nodos"] if n["id"] == nodo_id), None)
    if not nodo_info:
        logger.error(f"Nodo {nodo_id} no encontrado")
        return False

    ip = nodo_info["ip"]
    user = os.getenv("SSH_USER", "ramon")
    ssh_key = os.path.expanduser("~/.ssh/id_ura_gx10")

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    connected = False

    # Intentar conexion con clave SSH primero
    if os.path.isfile(ssh_key):
        try:
            ssh.connect(ip, username=user, key_filename=ssh_key, timeout=10)
            connected = True
        except Exception:
            pass

    # Fallback a password
    if not connected:
        try:
            from core.security.ssh_credentials import obtener_credenciales

            passwd = obtener_credenciales(user)
        except Exception:
            passwd = None
        if not passwd:
            logger.error(sanitize_log(f"Credenciales no disponibles para {user}@{ip}"))
            return False
        try:
            ssh.connect(ip, username=user, password=passwd, timeout=10)
            connected = True
        except Exception as exc:
            logger.error(sanitize_log(f"Error SSH: {exc}"))
            return False

    if not connected:
        return False

    try:
        pasos_aplicados: list[int] = []
        for i, paso in enumerate(plan.get("pasos", [])):
            if not ejecutar_paso(ssh, paso):
                logger.error(f"Fallo en paso {i}. Iniciando rollback...")
                # Ejecutar rollbacks en orden inverso
                for j in reversed(pasos_aplicados):
                    if "rollback" in plan["pasos"][j]:
                        ssh.exec_command(plan["pasos"][j]["rollback"], timeout=30)
                ssh.close()
                return False
            pasos_aplicados.append(i)
        ssh.close()

        # Marcar como desplegado
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        for n in nodos["nodos"]:
            if n["id"] == nodo_id:
                n["desplegado"] = True
                n["fecha_despliegue"] = timestamp
                n["last_seen"] = timestamp
                n["version_scripts"] = plan.get("version", "1")
        with open(NODOS_DB, "w", encoding="utf-8") as fh:
            json.dump(nodos, fh, indent=2)

        # Notificar exito
        notif_script = URA_BASE / "scripts" / "notificar.sh"
        if notif_script.exists():
            subprocess.run(
                ["bash", str(notif_script), f"Nodo {nodo_id} desplegado correctamente"],
                capture_output=True,
            )
        return True
    except Exception as exc:
        logger.error(sanitize_log(f"Error SSH: {exc}"))
        return False


def main() -> None:
    """Procesa planes pendientes de despliegue."""
    logging.basicConfig(level=logging.INFO)
    for plan_file in PLANES_DIR.glob("*_plan.json"):
        nodo_id = plan_file.stem.replace("_plan", "")
        with open(plan_file, encoding="utf-8") as fh:
            plan = json.load(fh)
        if desplegar(nodo_id, plan):
            logger.info(f"Despliegue de {nodo_id} completado")
            plan_file.rename(plan_file.with_name(f"{nodo_id}_desplegado.json"))
        else:
            logger.error(f"Despliegue de {nodo_id} fallo")


if __name__ == "__main__":
    main()
