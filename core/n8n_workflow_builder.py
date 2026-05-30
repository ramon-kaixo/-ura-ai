#!/usr/bin/env python3
"""
core/n8n_workflow_builder.py - Constructor de workflows n8n
Usa Ollama para generar workflows n8n válidos desde descripciones en lenguaje natural
"""

import json
import logging
import os
import requests
from pathlib import Path

from core.model_config import get_active_model
from core.logging_config import get_logger
from core.n8n_workflow_validator import validar_workflow

logger = get_logger("n8n_workflow_builder", log_dir="./logs")

# Configuración n8n
N8N_API_URL = "http://localhost:5678/api/v1"
N8N_API_KEY = os.environ.get("N8N_API_KEY")  # configurar en .env o variables de entorno
WORKFLOW_TEMPLATE_FILE = Path(__file__).parent.parent / "data" / "n8n_workflow_template.json"


def _load_template() -> dict:
    """Carga plantilla base de workflow n8n"""
    if not WORKFLOW_TEMPLATE_FILE.exists():
        logger.warning(f"Plantilla no encontrada: {WORKFLOW_TEMPLATE_FILE}")
        return _get_default_template()

    try:
        with open(WORKFLOW_TEMPLATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error cargando plantilla: {e}")
        return _get_default_template()


def _get_default_template() -> dict:
    """Devuelve plantilla por defecto si no existe archivo"""
    return {
        "name": "Workflow generado por URA",
        "nodes": [],
        "connections": {},
        "settings": {"executionOrder": "v1"},
        "staticData": None,
        "tags": [],
        "pinData": {},
        "versionId": "1",
    }


def _validate_workflow(workflow_json: dict) -> bool:
    """Valida que el workflow JSON tenga las claves mínimas"""
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

    logger.info("Workflow JSON validado correctamente")
    return True


def construir_workflow(descripcion: str) -> dict:
    """
    Construye un workflow n8n a partir de una descripción en lenguaje natural
    Args:
        descripcion: Descripción de la tarea en lenguaje natural
    Returns:
        Dict con el workflow JSON generado
    """
    logger.info(f"Construyendo workflow para: {descripcion}")

    # Cargar plantilla base
    template = _load_template()

    # Construir prompt para Ollama
    prompt = f"""
Eres un experto en n8n (workflow automation). Tu tarea es generar un workflow JSON válido basado en una descripción en lenguaje natural.

PLANTILLA BASE (usa esta estructura, no inventes campos nuevos):
{json.dumps(template, indent=2)}

DESCRIPCIÓN DE LA TAREA:
{descripcion}

INSTRUCCIONES:
1. Genera un workflow JSON que cumpla la tarea descrita
2. Usa los nodos típicos de n8n: Schedule Trigger, HTTP Request, Code, Set, IF, Merge, etc.
3. Define las conexiones entre nodos en el campo "connections"
4. Asegúrate de que el JSON sea válido y tenga las claves: name, nodes, connections
5. NO inventes campos que no estén en la plantilla
6. Responde SOLO con el JSON, sin explicaciones adicionales

Responde con el JSON completo del workflow:
"""

    try:
        # Llamar a Ollama
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={"model": get_active_model(), "prompt": prompt, "stream": False},
            timeout=60,
        )

        if response.status_code != 200:
            logger.error(f"Error llamando a Ollama: {response.status_code}")
            return template

        # Extraer JSON de la respuesta
        result = response.json()
        workflow_text = result.get("response", "")

        # Intentar parsear JSON (puede estar envuelto en markdown)
        # Buscar el primer { y el último }
        start_idx = workflow_text.find("{")
        end_idx = workflow_text.rfind("}")

        if start_idx != -1 and end_idx != -1:
            json_str = workflow_text[start_idx : end_idx + 1]
            workflow_json = json.loads(json_str)
        else:
            # Si no encuentra JSON, devolver plantilla
            logger.warning("No se pudo extraer JSON de la respuesta, usando plantilla")
            return template

        # Validar workflow
        if _validate_workflow(workflow_json):
            logger.info("Workflow generado y validado correctamente")
            return workflow_json
        else:
            logger.warning("Workflow generado no es válido, usando plantilla")
            return template

    except json.JSONDecodeError as e:
        logger.error(f"Error parseando JSON: {e}")
        return template
    except Exception as e:
        logger.error(f"Error construyendo workflow: {e}")
        return template


def importar_a_n8n(workflow_json: dict) -> bool:
    """
    Importa un workflow a n8n vía API
    Args:
        workflow_json: Workflow JSON a importar
    Returns:
        True si se importó correctamente, False en caso contrario
    """
    logger.info("Importando workflow a n8n...")

    # Validar workflow con el validador de seguridad
    valido, motivo = validar_workflow(workflow_json)
    if not valido:
        logger.error(f"Workflow rechazado por validador: {motivo}")
        return False

    # Verificar si el workflow implica pagos — pasa por payment_guardian
    if _involves_payment(workflow_json):
        logger.warning("Workflow implica pagos — solicitando autorización")
        try:
            from core.payment_guardian import autorizar_pago

            autorizado = autorizar_pago(
                0.0, "Workflow n8n con operación de pago", "n8n_workflow_builder"
            )
            if not autorizado:
                logger.warning("Workflow de pago rechazado por payment_guardian")
                return False
        except Exception as e:
            logger.error("payment_guardian no disponible: %s — bloqueando por seguridad", e)
            return False

    try:
        # Headers para API de n8n
        headers = {"Content-Type": "application/json"}

        if N8N_API_KEY:
            headers["Authorization"] = f"Bearer {N8N_API_KEY}"

        # POST workflow
        response = requests.post(
            f"{N8N_API_URL}/workflows", json=workflow_json, headers=headers, timeout=30
        )

        if response.status_code in [200, 201]:
            result = response.json()
            workflow_id = result.get("id")
            logger.info(f"Workflow importado correctamente: {workflow_id}")

            # Activar workflow
            _activate_workflow(workflow_id, headers)

            return True
        else:
            logger.error(f"Error importando workflow: {response.status_code} - {response.text}")
            return False

    except requests.exceptions.ConnectionError:
        logger.error("No se pudo conectar a n8n. ¿Está ejecutándose en http://localhost:5678?")
        return False
    except Exception as e:
        logger.error(f"Error importando workflow: {e}")
        return False


def _activate_workflow(workflow_id: str, headers: dict) -> bool:
    """Activa un workflow en n8n"""
    try:
        response = requests.patch(
            f"{N8N_API_URL}/workflows/{workflow_id}",
            json={"active": True},
            headers=headers,
            timeout=30,
        )

        if response.status_code in [200, 201]:
            logger.info(f"Workflow {workflow_id} activado")
            return True
        else:
            logger.warning(f"No se pudo activar workflow: {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"Error activando workflow: {e}")
        return False


def _involves_payment(workflow_json: dict) -> bool:
    """
    Verifica si el workflow implica servicios de pago
    Args:
        workflow_json: Workflow JSON a verificar
    Returns:
        True si implica pagos, False en caso contrario
    """
    # Palabras clave que indican pagos
    payment_keywords = [
        "payment",
        "pago",
        "stripe",
        "paypal",
        "credit card",
        "tarjeta",
        "factura",
        "invoice",
        "billing",
        "cobro",
    ]

    workflow_str = json.dumps(workflow_json).lower()

    for keyword in payment_keywords:
        if keyword in workflow_str:
            logger.info(f"Workflow implica pagos (detectado: {keyword})")
            return True

    return False


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Prueba
    descripcion = "Revisar Gmail cada día y avisar por Telegram si hay correos importantes"
    workflow = construir_workflow(descripcion)

    print("\n=== WORKFLOW GENERADO ===")
    print(json.dumps(workflow, indent=2))

    # Intentar importar (comentado por seguridad)
    # success = importar_a_n8n(workflow)
    # print(f"\nImportación: {'EXITOSA' if success else 'FALLIDA'}")
