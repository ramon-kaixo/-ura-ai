#!/usr/bin/env python3
"""
core/n8n_workflow_validator.py - Validador de seguridad para workflows n8n
Valida workflows antes de importarlos a n8n
"""

import json
import logging
from core.logging_config import get_logger

logger = get_logger("n8n_workflow_validator", log_dir="./logs")


def validar_workflow(workflow_json: dict) -> tuple[bool, str]:
    """
    Valida un workflow n8n antes de importarlo

    Args:
        workflow_json: Workflow JSON a validar

    Returns:
        Tuple (valido, motivo): True si es válido, False si no es válido con el motivo
    """
    # Validación 1: No hay nodos de borrado masivo sin aprobación manual previa
    if _contiene_borrado_masivo(workflow_json):
        return False, "Workflow contiene nodos de borrado masivo sin aprobación manual previa"

    # Validación 2: No hay credenciales en el JSON
    if _contiene_credenciales(workflow_json):
        return (
            False,
            "Workflow contiene credenciales en el JSON (deben usar variables de entorno de n8n)",
        )

    # Validación 3: No hay workflows que se ejecuten más de 60 veces por hora
    if _supera_limite_ejecuciones(workflow_json):
        return False, "Workflow se ejecutaría más de 60 veces por hora (protección anti-bucle)"

    # Validación 4: Estructura básica válida
    if not _estructura_valida(workflow_json):
        return False, "Workflow no tiene estructura válida"

    logger.info("Workflow validado correctamente")
    return True, "Workflow válido"


def _contiene_borrado_masivo(workflow_json: dict) -> bool:
    """
    Verifica si el workflow contiene nodos de borrado masivo

    Args:
        workflow_json: Workflow JSON a verificar

    Returns:
        True si contiene borrado masivo
    """
    # Palabras clave que indican borrado masivo
    delete_keywords = [
        "delete",
        "remove",
        "erase",
        "purge",
        "clear",
        "borrar",
        "eliminar",
        "limpiar",
        "purgar",
    ]

    nodes = workflow_json.get("nodes", [])
    workflow_str = json.dumps(workflow_json, default=str).lower()

    # Buscar nodos con palabras de borrado
    for node in nodes:
        node_name = node.get("name", "").lower()
        node_type = node.get("type", "").lower()

        for keyword in delete_keywords:
            if keyword in node_name or keyword in node_type:
                logger.warning(f"Nodo de borrado detectado: {node_name}")
                # Verificar si tiene aprobación manual
                if not _tiene_aprobacion_manual(node):
                    return True

    return False


def _tiene_aprobacion_manual(node: dict) -> bool:
    """
    Verifica si un nodo tiene aprobación manual configurada

    Args:
        node: Nodo a verificar

    Returns:
        True si tiene aprobación manual
    """
    # Buscar configuración de aprobación en parámetros
    parameters = node.get("parameters", {})

    # Aprobación manual explícita
    if parameters.get("requireManualApproval", False):
        return True

    # Nodos de tipo "manual trigger" o similar
    node_type = node.get("type", "").lower()
    if "manual" in node_type or "approval" in node_type:
        return True

    return False


def _contiene_credenciales(workflow_json: dict) -> bool:
    """
    Verifica si el workflow contiene credenciales en el JSON

    Args:
        workflow_json: Workflow JSON a verificar

    Returns:
        True si contiene credenciales
    """
    # Palabras clave que indican credenciales
    credential_keywords = [
        "password",
        "passwd",
        "pwd",
        "token",
        "api_key",
        "apikey",
        "secret",
        "credential",
        "auth",
        "private_key",
        "key",
        "bearer",
        "authorization",
    ]

    workflow_str = json.dumps(workflow_json, default=str).lower()

    for keyword in credential_keywords:
        # Verificar si la palabra clave está presente y no está como variable de entorno
        if keyword in workflow_str:
            # Excluir variables de entorno de n8n ({{$env.VARIABLE}})
            if "${{" + keyword in workflow_str or "{{$env." + keyword in workflow_str:
                continue
            # Si está en texto plano, es un problema
            if f'"{keyword}"' in workflow_str or f"'{keyword}'" in workflow_str:
                logger.warning(f"Credencial potencial detectada: {keyword}")
                return True

    return False


def _supera_limite_ejecuciones(workflow_json: dict) -> bool:
    """
    Verifica si el workflow se ejecutaría más de 60 veces por hora

    Args:
        workflow_json: Workflow JSON a verificar

    Returns:
        True si supera el límite
    """
    nodes = workflow_json.get("nodes", [])

    for node in nodes:
        # Buscar nodos de tipo trigger/schedule
        node_type = node.get("type", "").lower()

        if "schedule" in node_type or "trigger" in node_type or "cron" in node_type:
            parameters = node.get("parameters", {})

            # Verificar intervalo
            rule = parameters.get("rule", {})
            interval = rule.get("interval", [])

            for interval_item in interval:
                # Si se ejecuta más de una vez por minuto = más de 60 por hora
                if (
                    interval_item.get("field") == "minutes"
                    and interval_item.get("minutesInterval", 60) < 1
                ):
                    logger.warning(f"Workflow con frecuencia alta: {interval_item}")
                    return True

                # Si se ejecuta más de una vez por segundo
                if interval_item.get("field") == "seconds":
                    logger.warning(f"Workflow con frecuencia muy alta: {interval_item}")
                    return True

    return False


def _estructura_valida(workflow_json: dict) -> bool:
    """
    Verifica que el workflow tenga estructura básica válida

    Args:
        workflow_json: Workflow JSON a verificar

    Returns:
        True si la estructura es válida
    """
    required_keys = ["name", "nodes", "connections"]

    for key in required_keys:
        if key not in workflow_json:
            logger.error(f"Workflow JSON falta clave requerida: {key}")
            return False

    # Validar que nodes sea una lista
    if not isinstance(workflow_json["nodes"], list):
        logger.error("Workflow JSON 'nodes' debe ser una lista")
        return False

    # Validar que connections sea un dict
    if not isinstance(workflow_json["connections"], dict):
        logger.error("Workflow JSON 'connections' debe ser un dict")
        return False

    return True


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Prueba con workflow inválido (credenciales)
    workflow_invalido = {
        "name": "Workflow de prueba",
        "nodes": [
            {"name": "Nodo con password", "type": "test", "parameters": {"password": "123456"}}
        ],
        "connections": {},
    }

    valido, motivo = validar_workflow(workflow_invalido)
    print(f"Workflow inválido: {valido}, Motivo: {motivo}")

    # Prueba con workflow válido
    workflow_valido = {
        "name": "Workflow de prueba válido",
        "nodes": [
            {"name": "Nodo seguro", "type": "test", "parameters": {"apiKey": "{{$env.API_KEY}}"}}
        ],
        "connections": {},
    }

    valido, motivo = validar_workflow(workflow_valido)
    print(f"Workflow válido: {valido}, Motivo: {motivo}")
