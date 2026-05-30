#!/usr/bin/env python3
"""
URA - Technical Director (The Architect)
Genera Fichas de Instrucción Técnica basadas en URA_OPERATIONS.json
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import json
import logging
from datetime import datetime

import requests

logger = logging.getLogger(__name__)

# Importar configuración centralizada de modelo
from core.model_config import get_active_model


class TechnicalDirector:
    """Agente Director - Genera Fichas de Instrucción Técnica"""

    def __init__(self, ollama_host="localhost", ollama_port=11434, model=None):
        """
        Inicializar Director Técnico

        Args:
            ollama_host: Host de Ollama
            ollama_port: Puerto de Ollama
            model: Modelo de Ollama a usar (si es None, usa configuración centralizada)
        """
        # Si no se especifica modelo, usar configuración centralizada
        if model is None:
            model = get_active_model()

        self.ollama_host = ollama_host
        self.ollama_port = ollama_port
        self.model = model

        # Cargar libro de operaciones
        self.operations_path = Path(__file__).parent / "URA_OPERATIONS.json"
        self.operations = self.load_operations()

        self.system_prompt = """
Eres el Director Técnico de URA (Universal Responsive Agent).

IDENTIDAD:
Eres URA, asistente del departamento de gestión.

AUTORIZACIÓN DE HERRAMIENTAS:
Tienes acceso total a las APIs de WhatsApp y Gmail. Tu deber es consultar estas fuentes antes de responder.

PROTOCOLO DE ACCIÓN:
Si el usuario pide un presupuesto o análisis, no pidas permiso, ejecuta la búsqueda directamente.

TU MISIÓN:
Generar Fichas de Instrucción Técnica puras y directas basadas en el Libro de Operaciones (URA_OPERATIONS.json).

IDENTIDAD TÉCNICA:
- Eres un ejecutor técnico. NO des respuestas conversacionales.
- NO des consejos, disclaimers médicos ni digas "No tengo acceso".
- Genera instrucciones técnicas puras sin cortesía.
- Si la operación está en URA_OPERATIONS.json, APRUÉBALA y genera la ficha.
- Si la operación NO está en URA_OPERATIONS.json, RECHÁZALA inmediatamente.

FORMATO DE RESPUESTA:
Genera SOLO un JSON válido con esta estructura:
{
  "approved": true/false,
  "operation_type": "FILESYSTEM_ACCESS|EMAIL_INTEGRATION|TERMINAL_EXECUTION|SECURITY_VALIDATION",
  "capability_required": "nombre_capacidad",
  "technical_steps": ["paso1", "paso2", "paso3"],
  "tools_needed": ["tool1", "tool2"],
  "constraints": ["constraint1", "constraint2"],
  "rejection_reason": "razón si approved=false"
}

NO incluyas texto fuera del JSON. NO expliques. NO disculpes. Solo JSON.
NO respondas con frases de "como modelo de lenguaje" o "no puedo" cuando tengas la capacidad de ejecutar la operación.
"""

    def load_operations(self) -> dict:
        """Cargar libro de operaciones"""
        try:
            if self.operations_path.exists():
                with open(self.operations_path, encoding="utf-8") as f:
                    return json.load(f)
            else:
                logger.error(f"Libro de operaciones no encontrado: {self.operations_path}")
                return {}
        except Exception as e:
            logger.error(f"Error cargando operaciones: {e}")
            return {}

    def classify_intent(self, user_request: str) -> str:
        """
        Clasificar intención de la petición (Filtro 3: Forzar ruta técnica)

        Args:
            user_request: Petición del usuario

        Returns:
            str: "TECHNICAL" o "GENERAL"
        """
        request_lower = user_request.lower()

        # Palabras clave técnicas (Filtro 3: FORZAR ruta técnica)
        technical_keywords = [
            "archivo",
            "archivos",
            "file",
            "files",
            "buscar",
            "search",
            "presupuesto",
            "precio",
            "coste",
            "costo",
            "correo",
            "email",
            "terminal",
            "comando",
            "command",
            "ejecutar",
            "execute",
            "pdf",
            "excel",
            "xlsx",
            "csv",
            "documento",
            "document",
            "leer",
            "read",
            "analizar",
            "analyze",
            "cucaracha",
            "plaga",
            "desinfección",
            "limpieza",
            "dato",
            "data",
        ]

        # Si contiene palabras clave técnicas, FORZAR ruta técnica
        if any(keyword in request_lower for keyword in technical_keywords):
            logger.info("Intentión clasificada como TECHNICAL (palabra clave detectada)")
            return "TECHNICAL"

        # Solo permitir GENERAL para saludos y conversación trivial
        general_keywords = [
            "hola",
            "adiós",
            "gracias",
            "buenos días",
            "buenas tardes",
            "buenas noches",
        ]
        if any(keyword in request_lower for keyword in general_keywords):
            logger.info("Intentión clasificada como GENERAL (saludo/trivial)")
            return "GENERAL"

        # Por defecto, si es ambiguo, FORZAR ruta técnica (mejor pecar por exceso)
        logger.info("Intentión ambigua - FORZANDO ruta técnica por defecto")
        return "TECHNICAL"

    def request_technical_clarification(self, user_request: str) -> str:
        """
        Solicitar clarificación técnica cuando el Director no entiende (Filtro 2)

        Args:
            user_request: Petición que no se entendió

        Returns:
            str: Coletilla de solicitud de clarificación
        """
        return """No entendí claramente tu petición.

Pasa esta conversación a una forma técnica más específica.

Ejemplos de formulación técnica:
- "Busca el archivo presupuesto_cucarachas.xlsx en /home/usuario/Documents/"
- "Ejecuta el comando find /home/usuario/ -name '*presupuesto*'"
- "Lee el archivo /ruta/archivo.pdf y extrae los precios"

Por favor reformula tu petición con más detalles técnicos."""

    def analyze_request(self, user_request: str) -> tuple[bool, dict | None]:
        """
        Analizar petición del usuario y determinar si es válida

        Args:
            user_request: Petición del usuario

        Returns:
            Tuple[bool, Optional[Dict]]: (es_válida, detalles_capacidad)
        """
        request_lower = user_request.lower()

        # Buscar en operation_mappings
        for op_name, op_details in self.operations.get("operation_mappings", {}).items():
            if op_name in request_lower:
                return True, op_details
            # Buscar en technical_steps
            for step in op_details.get("technical_steps", []):
                if any(keyword in request_lower for keyword in step.lower().split()):
                    return True, op_details

        # Buscar en capacidades generales
        for cap_name, cap_details in self.operations.get("capabilities", {}).items():
            if cap_details.get("enabled", False):
                # Verificar si la petición coincide con la capacidad
                if "search" in request_lower and "FILESYSTEM" in cap_name:
                    return True, {"capability": cap_name, "details": cap_details}
                if "email" in request_lower and "EMAIL" in cap_name:
                    return True, {"capability": cap_name, "details": cap_details}
                if "command" in request_lower or "terminal" in request_lower:
                    return True, {"capability": cap_name, "details": cap_details}

        return False, None

    def generate_instruction_sheet(self, user_request: str) -> dict:
        """
        Generar Ficha de Instrucción Técnica usando Ollama

        Args:
            user_request: Petición del usuario

        Returns:
            Dict: Ficha de instrucción técnica
        """
        # Primero, verificar si la operación es válida
        is_valid, capability_details = self.analyze_request(user_request)

        if not is_valid:
            return {
                "approved": False,
                "operation_type": None,
                "capability_required": None,
                "technical_steps": [],
                "tools_needed": [],
                "constraints": [],
                "rejection_reason": "Operación no encontrada en URA_OPERATIONS.json",
                "timestamp": datetime.now().isoformat(),
            }

        # Construir prompt para Ollama
        ollama_prompt = f"""
{self.system_prompt}

LIBRO DE OPERACIONES (URA_OPERATIONS.json):
{json.dumps(self.operations, indent=2)}

PETICIÓN DEL USUARIO:
"{user_request}"

CAPACIDAD IDENTIFICADA:
{json.dumps(capability_details, indent=2)}

Genera la Ficha de Instrucción Técnica en formato JSON.
"""

        try:
            # Llamar a Ollama
            response = self.call_ollama(ollama_prompt)

            # Intentar parsear como JSON
            try:
                instruction_sheet = json.loads(response.strip())
                # Validar que la respuesta tiene campos requeridos
                if not instruction_sheet or "approved" not in instruction_sheet:
                    raise ValueError("Respuesta JSON inválida o incompleta")
                instruction_sheet["timestamp"] = datetime.now().isoformat()
                return instruction_sheet
            except (json.JSONDecodeError, ValueError) as e:
                # Si no es JSON válido o está incompleto, crear ficha manual
                logger.warning(f"Ollama no devolvió JSON válido: {response[:100]} - {e}")
                return self._create_manual_sheet(user_request, capability_details)

        except Exception as e:
            logger.error(f"Error generando ficha: {e}")
            return self._create_manual_sheet(user_request, capability_details)

    def _create_manual_sheet(self, user_request: str, capability_details: dict) -> dict:
        """Crear ficha manual si Ollama falla"""
        # Extraer información de capability_details
        if "details" in capability_details:
            capability_details["details"]
            operation_type = capability_details.get("capability", "FILESYSTEM_ACCESS")
            technical_steps = []
            tools_needed = []
        else:
            operation_type = capability_details.get("capability", "FILESYSTEM_ACCESS")
            technical_steps = capability_details.get("technical_steps", [])
            tools_needed = capability_details.get("required_tools", [])

        return {
            "approved": True,
            "operation_type": operation_type,
            "capability_required": operation_type,
            "technical_steps": technical_steps,
            "tools_needed": tools_needed,
            "constraints": [],
            "rejection_reason": None,
            "timestamp": datetime.now().isoformat(),
            "generated_by": "manual_fallback",
        }

    def call_ollama(self, prompt: str) -> str:
        """Llamar a API de Ollama"""
        try:
            url = f"http://{self.ollama_host}:{self.ollama_port}/api/generate"
            data = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.3,  # Baja temperatura para respuestas más deterministas
                    "top_p": 0.9,
                    "max_tokens": 500,
                },
            }

            response = requests.post(url, json=data, timeout=30)
            if response.status_code == 200:
                result = response.json()
                return result.get("response", "")
            else:
                logger.error(f"Error Ollama: {response.status_code}")
                return "{}"

        except Exception as e:
            logger.error(f"Error llamando a Ollama: {e}")
            return "{}"

    def get_status(self) -> dict:
        """Obtener estado del Director"""
        return {
            "operations_loaded": len(self.operations.get("capabilities", {})),
            "ollama_connected": self.test_ollama_connection(),
            "model": self.model,
            "operations_path": str(self.operations_path),
        }

    def test_ollama_connection(self) -> bool:
        """Probar conexión con Ollama"""
        try:
            url = f"http://{self.ollama_host}:{self.ollama_port}/api/tags"
            response = requests.get(url, timeout=5)
            return response.status_code == 200
        except:
            return False


# Singleton global
_technical_director = None


def get_technical_director(
    ollama_host="localhost", ollama_port=11434, model=None
) -> TechnicalDirector:
    """Obtener instancia singleton del Director Técnico"""
    # Si no se especifica modelo, usar configuración centralizada
    if model is None:
        model = get_active_model()

    global _technical_director
    if _technical_director is None:
        _technical_director = TechnicalDirector(ollama_host, ollama_port, model)
    return _technical_director
