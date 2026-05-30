#!/usr/bin/env python3
"""
core/repair/distributed.py - Distributed repair functionality
"""

import json
import logging

logger = logging.getLogger(__name__)


def setup_distributed_repair(instance, nodes: list[str]):
    """Configurar auto-reparación distribuida entre múltiples nodos"""
    instance.distributed_nodes = nodes
    logger.info(f"Auto-reparación distribuida configurada con {len(nodes)} nodos")


def broadcast_repair_request(
    instance, error_type: str, error_message: str
) -> list[tuple[str, bool, str]]:
    """Broadcast solicitud de reparación a todos los nodos"""
    results = []

    if not hasattr(instance, "distributed_nodes"):
        logger.warning("Auto-reparación distribuida no configurada")
        return results

    for node in instance.distributed_nodes:
        try:
            import requests

            response = requests.post(
                f"{node}/api/auto-repair/repair",
                json={"error_type": error_type, "error_message": error_message},
                timeout=30,
            )

            if response.status_code == 200:
                data = response.json()
                results.append((node, data.get("success", False), data.get("message", "")))
            else:
                results.append((node, False, f"HTTP {response.status_code}"))

        except Exception as e:
            results.append((node, False, str(e)))

    return results


def sync_repair_history(instance):
    """Sincronizar historial de reparaciones entre nodos"""
    if not hasattr(instance, "distributed_nodes"):
        return

    try:
        local_history = instance.get_repair_history()

        for node in instance.distributed_nodes:
            try:
                import requests

                response = requests.get(f"{node}/api/auto-repair/history", timeout=10)

                if response.status_code == 200:
                    data = response.json()
                    remote_history = data.get("history", [])

                    # Fusionar historiales
                    for entry in remote_history:
                        if entry not in local_history:
                            local_history.append(entry)

                    # Guardar historial fusionado
                    with open(instance.repair_history_file, "w") as f:
                        json.dump(local_history[-100:], f, indent=2)

            except Exception as e:
                logger.warning(f"Error sincronizando con {node}: {e}")

    except Exception as e:
        logger.error(f"Error en sincronización distribuida: {e}")
