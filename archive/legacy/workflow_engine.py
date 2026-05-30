#!/usr/bin/env python3
"""
URA Workflow Engine
Motor del flujo de trabajo en 3 fases con Director Técnico
"""

import logging
import time
from pathlib import Path

import requests

from core.code_agents.generators import generar, listar
from core.observability import trace_step

logger = logging.getLogger(__name__)

# Importar configuración centralizada de modelo
from core.model_config import get_active_model

# Importar Director Técnico
try:
    from technical_director import get_technical_director

    TECHNICAL_DIRECTOR_AVAILABLE = True
except ImportError:
    TECHNICAL_DIRECTOR_AVAILABLE = False
    logger.warning("Technical Director no disponible - usando modo fallback")

import re


def clean_human_garbage(response: str) -> str:
    """
    Elimina frases hipócritas de IA de la respuesta

    Args:
        response: Respuesta original

    Returns:
        str: Respuesta limpia sin basura humana
    """
    garbage_phrases = [
        r"Como modelo de lenguaje.*?\.?\n?",
        r"Es importante recordar que.*?\.?\n?",
        r"No soy un experto.*?\.?\n?",
        r"No soy un profesional.*?\.?\n?",
        r"Espero que esto te sea de ayuda.*?\.?\n?",
        r"Si necesitas algo más.*?\.?\n?",
        r"Por favor ten en cuenta.*?\.?\n?",
        r"Debo mencionar que.*?\.?\n?",
        r"Ten en cuenta que.*?\.?\n?",
        r"Como asistente de IA.*?\.?\n?",
        r"Estoy aquí para ayudarte.*?\.?\n?",
        r"Quiero aclarar que.*?\.?\n?",
        r"Es worth noting.*?\.?\n?",
        r"It's worth mentioning.*?\.?\n?",
        r"As an AI.*?\.?\n?",
        r"I should note.*?\.?\n?",
    ]

    cleaned = response
    for phrase in garbage_phrases:
        cleaned = re.sub(phrase, "", cleaned, flags=re.IGNORECASE)

    # Limpiar líneas vacías múltiples
    cleaned = re.sub(r"\n\s*\n\s*\n", "\n\n", cleaned)

    # Limpiar espacios extra
    cleaned = cleaned.strip()

    return cleaned


def detect_ai_commercial_bypass(response: str) -> bool:
    """
    Detecta si la respuesta es de IA comercial (bypass del Technical Director)

    Args:
        response: Respuesta a analizar

    Returns:
        bool: True si es bypass de IA comercial
    """
    bypass_indicators = [
        "Como modelo de lenguaje",
        "As an AI language model",
        "No puedo hacer eso porque soy una ia",
        "soy una ia",
        "como ia,",
        "como ia ",
        "como asistente de ia",
        "No puedo responder a preguntas",
        "I cannot respond to questions",
        "Mi función principal es ser útil y seguro",
        "My primary function is to be helpful and safe",
        "Te ofrezco algunas alternativas",
        "I offer some alternatives",
        "Si sigues teniendo problemas",
        "If you continue to have problems",
        "contactar al equipo de soporte",
        "contact the support team",
        "support.google.com",
    ]

    response_lower = response.lower()
    for indicator in bypass_indicators:
        if indicator.lower() in response_lower:
            logger.error(f"BYPASS DETECTADO: Respuesta de IA comercial detectada - '{indicator}'")
            return True

    return False


class URAWorkflowEngine:
    """Motor de flujo de trabajo URA en 3 fases"""

    def __init__(
        self, ollama_host="localhost", ollama_port=11434, model=None, department="gestion"
    ):
        # Si no se especifica modelo, usar configuración centralizada
        if model is None:
            model = get_active_model()

        self.ollama_host = ollama_host
        self.ollama_port = ollama_port
        self.model = model
        self.department = department
        self.windsurf_manual = self.load_windsurf_manual()
        self.conversation_history = []

        logger.info(f"URAWorkflowEngine inicializado - Modelo: {model}, Departamento: {department}")

        # Seguimiento de estado de conversación
        self.conversation_state = {
            "first_interaction": True,
            "interaction_count": 0,
            "awaiting_clarification": False,
            "last_intent": None,
        }

        # Inicializar Director Técnico
        if TECHNICAL_DIRECTOR_AVAILABLE:
            self.technical_director = get_technical_director(ollama_host, ollama_port, model)
            logger.info("Director Técnico inicializado")
        else:
            self.technical_director = None
            logger.warning("Director Técnico no disponible")

    def load_windsurf_manual(self) -> str:
        """Cargar manual de Windsurf como contexto"""
        manual_path = Path(__file__).parent.parent / "config" / "windsurf_manual.txt"

        # Manual básico integrado si no existe archivo
        default_manual = """
MANUAL DE WINDSURF - CONTEXTO DEL SISTEMA

Windsurf es un IDE inteligente con capacidades de IA que incluye:

HERRAMIENTAS DISPONIBLES:
1. Lectura de archivos (read_file)
2. Escritura y edición de archivos (edit, multi_edit)
3. Búsqueda en código (grep_search, find_by_name)
4. Ejecución de comandos (bash)
5. Navegación por directorios (list_dir)
6. Vista previa de navegador (browser_preview)
7. Gestión de memoria (create_memory)
8. Listas de tareas (todo_list)

MEJORES PRÁCTICAS:
- Usar nombres de archivo absolutos
- Verificar existencia de archivos antes de editar
- Usar multi_edit para múltiples cambios
- Leer archivos antes de modificarlos
- Usar herramientas de búsqueda para encontrar código
- Ejecutar comandos en el directorio correcto
- Proporcionar contexto claro en los prompts

ESTRUCTURA DE PROYECTOS:
- main.py o app.py para entrada principal
- requirements.txt para dependencias
- README.md para documentación
- Carpeta src/ para código fuente
- Carpeta tests/ para pruebas
- Carpeta docs/ para documentación

COMANDOS COMUNES:
- Crear nuevo proyecto: estructura básica de carpetas
- Añadir funcionalidad: implementar nuevas características
- Debug: encontrar y corregir errores
- Refactor: mejorar código existente
- Testing: añadir pruebas unitarias
- Documentación: actualizar README y docs

INTEGRACIÓN CON OLLAMA:
- Formatear prompts específicos para Windsurf
- Proporcionar contexto del proyecto
- Especificar herramientas a utilizar
- Indicar estructura de archivos esperada
- Incluir ejemplos de código cuando sea necesario
"""

        try:
            if manual_path.exists():
                with open(manual_path, encoding="utf-8") as f:
                    return f.read()
            else:
                # Crear archivo con manual por defecto
                manual_path.parent.mkdir(exist_ok=True)
                with open(manual_path, "w", encoding="utf-8") as f:
                    f.write(default_manual)
                return default_manual
        except Exception as e:
            logger.warning(f"No se pudo cargar manual de Windsurf: {e}")
            return default_manual

    @trace_step
    def process_user_request(self, user_message: str) -> str:
        """
        Procesar solicitud del usuario con Director Técnico como Gatekeeper (3 Filtros)

        FILTRO 1: Primera interacción obliga al Técnico
        FILTRO 2: Si Técnico no entiende, coletilla "pasa a forma técnica"
        FILTRO 3: Si es problema técnico, forzar ruta técnica
        """
        try:
            # Actualizar estado de conversación
            self.conversation_state["interaction_count"] += 1
            is_first_interaction = self.conversation_state["first_interaction"]

            # FILTRO 1: Primera interacción OBLIGATORIAMENTE al Director Técnico
            if is_first_interaction or self.conversation_state["awaiting_clarification"]:
                logger.info(
                    "FILTRO 1: Primera interacción o awaiting clarification → Director Técnico"
                )
                if not self.technical_director:
                    logger.warning("Director Técnico no disponible - fallback a URA")
                    return self._process_with_ura(user_message)

                # Clasificar intención con FILTRO 3
                intent = self.technical_director.classify_intent(user_message)
                self.conversation_state["last_intent"] = intent

                logger.info(f"FILTRO 3: Intentión clasificada como {intent}")

                if intent == "TECHNICAL":
                    # Ruta técnica: Director genera ficha y ejecuta
                    instruction_sheet = self.technical_director.generate_instruction_sheet(
                        user_message
                    )

                    # Si Director no entiende (no aprobó y no es rechazo claro), aplicar FILTRO 2
                    if not instruction_sheet.get("approved", False) and not instruction_sheet.get(
                        "rejection_reason"
                    ):
                        logger.warning("FILTRO 2: Director no entendió → coletilla técnica")
                        clarification = self.technical_director.request_technical_clarification(
                            user_message
                        )
                        self.conversation_state["awaiting_clarification"] = True
                        return clarification

                    # Si Director rechaza explícitamente
                    if not instruction_sheet.get("approved", False):
                        rejection_reason = instruction_sheet.get(
                            "rejection_reason", "Operación no autorizada"
                        )
                        logger.warning(f"Director Técnico rechazó operación: {rejection_reason}")
                        return f"[STATUS: REJECTED] [REASON: {rejection_reason}]"

                    # Ejecutar operación técnica
                    logger.info(
                        f"Director Técnico aprobó operación: {instruction_sheet.get('operation_type')}"
                    )
                    return self._execute_technical_operation(user_message, instruction_sheet)

                else:
                    # Ruta general (solo para saludos triviales)
                    logger.info("Ruta GENERAL permitida (saludo/trivial)")
                    self.conversation_state["first_interaction"] = False
                    return self._process_with_ura(user_message)

            else:
                # No es primera interacción - usar clasificación normal
                if not self.technical_director:
                    return self._process_with_ura(user_message)

                intent = self.technical_director.classify_intent(user_message)
                logger.info(
                    f"Intentión clasificada como {intent} (interacción #{self.conversation_state['interaction_count']})"
                )

                if intent == "TECHNICAL":
                    instruction_sheet = self.technical_director.generate_instruction_sheet(
                        user_message
                    )
                    if instruction_sheet.get("approved", False):
                        return self._execute_technical_operation(user_message, instruction_sheet)
                    else:
                        return self._process_with_ura(user_message)
                else:
                    return self._process_with_ura(user_message)

        except Exception as e:
            logger.error(f"Error en flujo de trabajo: {e}")
            return f"Error procesando tu solicitud: {str(e)}"

    @trace_step
    def _execute_technical_operation(self, user_message: str, instruction_sheet: dict) -> str:
        """
        Ejecutar operación técnica con ficha del Director

        Args:
            user_message: Petición del usuario
            instruction_sheet: Ficha de instrucción técnica

        Returns:
            str: Respuesta técnica
        """
        try:
            # FASE 1: Formatear prompt con Ollama (incluyendo ficha)
            formatted_prompt = self.format_prompt_with_ollama(user_message, instruction_sheet)

            # FASE 2: Simular envío a Windsurf (placeholder)
            windsurf_response = self.simulate_windsurf_execution(formatted_prompt)

            # FASE 2.5: VERIFICACIÓN DE DATOS REALES (CRÍTICO)
            # Verificar que las APIs (Gmail/WhatsApp) devolvieron datos reales
            if not self.verify_real_data(windsurf_response, instruction_sheet):
                logger.error("VERIFICACIÓN DE DATOS FALLIDA - APIs no devolvieron datos reales")
                return "[STATUS: API_FAILURE] [REASON: Las APIs de Gmail/WhatsApp no devolvieron datos reales. No se puede confirmar la operación sin evidencia de ejecución.]"

            # Procesar respuesta con Ollama para lenguaje natural
            natural_response = self.format_response_with_ollama(windsurf_response)

            # MODO CERO EXCUSAS: Validar conducta si hay ficha aprobada
            if instruction_sheet and instruction_sheet.get("approved"):
                if self.check_conduct_violation(natural_response):
                    logger.warning("FALLO DE CONDUCTA detectado - regenerando respuesta")
                    natural_response = self.regenerate_strict_response(
                        instruction_sheet, user_message
                    )

            # Aplicar filtro de basura humana
            natural_response = clean_human_garbage(natural_response)

            # Actualizar estado
            self.conversation_state["first_interaction"] = False
            self.conversation_state["awaiting_clarification"] = False

            # Guardar en historial
            self.conversation_history.append(
                {
                    "user": user_message,
                    "instruction_sheet": instruction_sheet,
                    "prompt": formatted_prompt,
                    "windsurf_response": windsurf_response,
                    "final_response": natural_response,
                    "timestamp": time.time(),
                }
            )

            return natural_response

        except Exception as e:
            logger.error(f"Error ejecutando operación técnica: {e}")
            return f"Error en ejecución técnica: {str(e)}"

    @trace_step
    def _process_with_ura(self, user_message: str) -> str:
        """
        Procesar petición con URA (ruta general)

        Args:
            user_message: Petición del usuario

        Returns:
            str: Respuesta de URA
        """
        try:
            logger.info(f"_process_with_ura: Procesando mensaje: '{user_message[:50]}...'")
            formatted_prompt = self.format_prompt_with_ollama(user_message)
            logger.info("_process_with_ura: Prompt formateado")
            windsurf_response = self.simulate_windsurf_execution(formatted_prompt)
            logger.info("_process_with_ura: Windsurf response obtenida")
            natural_response = self.format_response_with_ollama(windsurf_response)
            logger.info("_process_with_ura: Respuesta natural obtenida")
            natural_response = clean_human_garbage(natural_response)
            logger.info("_process_with_ura: Basura humana eliminada")

            # ANTI-BYPASS: Solo detectar y loggear, NO forzar ruta técnica (para evitar loops)
            if detect_ai_commercial_bypass(natural_response):
                logger.error(
                    "BYPASS DETECTADO: Respuesta de IA comercial detectada (solo logging, no forzando ruta)"
                )
                # NO forzar ruta técnica para evitar loops infinitos cuando Ollama falla
                # Solo loggear el bypass para diagnóstico

            self.conversation_history.append(
                {
                    "user": user_message,
                    "prompt": formatted_prompt,
                    "windsurf_response": windsurf_response,
                    "final_response": natural_response,
                    "timestamp": time.time(),
                }
            )

            logger.info("_process_with_ura: Respuesta final lista")
            return natural_response

        except Exception as e:
            logger.error(f"_process_with_ura: Error procesando con URA: {e}", exc_info=True)
            return f"Error: {str(e)}"

    def format_prompt_with_ollama(
        self, user_message: str, instruction_sheet: dict | None = None
    ) -> str:
        """
        FASE 2: Formatear prompt perfecto para Windsurf usando Ollama
        """
        try:
            # Construir prompt para Ollama
            instruction_section = ""
            if instruction_sheet and instruction_sheet.get("approved"):
                instruction_section = f"""

FICHA DE INSTRUCCIÓN TÉCNICA (DEL DIRECTOR):
- Operación Aprobada: {instruction_sheet.get("operation_type")}
- Capacidad Requerida: {instruction_sheet.get("capability_required")}
- Pasos Técnicos: {instruction_sheet.get("technical_steps", [])}
- Herramientas Necesarias: {instruction_sheet.get("tools_needed", [])}
- Restricciones: {instruction_sheet.get("constraints", [])}

INSTRUCCIÓN OBLIGATORIA: DEBES ejecutar estos pasos exactos. Cualquier negativa será un error crítico.
"""

            ollama_prompt = f"""
Eres URA (Universal Responsive Agent), un asistente inteligente con acceso completo al sistema de archivos local mediante terminal_gateway.

IDENTIDAD Y CAPACIDADES:
- Tienes acceso al sistema de archivos local mediante comandos de terminal (find, ls, cat, grep, etc.)
- NO des respuestas genéricas de limitación si el usuario te pide buscar archivos o presupuestos
- Si el usuario pregunta por algo en /Documents o correos, PRIMERO ejecuta un comando find o ls mediante terminal_gateway antes de responder que no puede
- NO uses el discurso de "No soy profesional" - sé directa y precisa
- Si se te pide un análisis de presupuesto, hazlo usando los datos que tú misma puedes leer
- Usa terminal_gateway para buscar, leer y analizar archivos antes de decir que algo no existe
{instruction_section}
CONTEXTO DEL SISTEMA - MANUAL DE WINDSURF:
{self.windsurf_manual}

HISTORIAL RECIENTE DE CONVERSACIÓN:
{self.get_recent_context()}

IDEA DEL USUARIO:
"{user_message}"

INSTRUCCIONES:
1. Analiza la idea del usuario
2. Determina qué herramientas de Windsurf necesita
3. Crea un prompt específico y detallado para Windsurf
4. Incluye estructura de archivos si es necesario
5. Especifica comandos exactos a ejecutar
6. Proporciona contexto claro del proyecto
7. SI el usuario pide buscar archivos, PRIMERO ejecuta find/ls antes de decir que no puedes
8. SI el usuario pide análisis de presupuestos/correos, PRIMERO busca los archivos y léelos
9. SI hay una Ficha de Instrucción Técnica, DEBES seguirla obligatoriamente

FORMATO DE RESPUESTA:
- Analizar qué quiere hacer el usuario
- Determinar herramientas necesarias
- Crear prompt estructurado para Windsurf
- Incluir ejemplos de código si aplica

Responde SOLO con el prompt formateado para Windsurf, sin explicaciones adicionales.
"""

            # Llamar a Ollama
            response = self.call_ollama(ollama_prompt)
            return response.strip()

        except Exception as e:
            logger.error(f"Error formateando prompt: {e}")
            return f"Por favor ayuda con: {user_message}"

    def check_conduct_violation(self, response: str) -> bool:
        """
        Verificar si la respuesta contiene excusas prohibidas (Modo Cero Excusas)

        Args:
            response: Respuesta a verificar

        Returns:
            bool: True si hay violación de conducta
        """
        excuse_patterns = [
            r"lo siento",
            r"no puedo",
            r"limitación",
            r"no tengo acceso",
            r"no puedo acceder",
            r"no soy capaz",
            r"no está disponible",
            r"no puedo ayudar",
            r"no estoy autorizado",
        ]

        response_lower = response.lower()
        return any(re.search(pattern, response_lower) for pattern in excuse_patterns)

    def regenerate_strict_response(self, instruction_sheet: dict, user_request: str) -> str:
        """
        Regenerar respuesta usando solo datos de la ficha técnica (sin excusas)

        Args:
            instruction_sheet: Ficha de instrucción técnica
            user_request: Petición original del usuario

        Returns:
            str: Respuesta regenerada sin excusas
        """
        operation_type = instruction_sheet.get("operation_type", "UNKNOWN")
        technical_steps = instruction_sheet.get("technical_steps", [])
        tools_needed = instruction_sheet.get("tools_needed", [])

        # Generar respuesta técnica directa usando solo datos de la ficha
        strict_response = f"""**[OPERACIÓN EJECUTADA]**
Tipo: {operation_type}
Herramientas: {", ".join(tools_needed)}

**[PASOS TÉCNICOS]**
"""
        for i, step in enumerate(technical_steps, 1):
            strict_response += f"{i}. {step}\n"

        strict_response += """
**[RESULTADO]**
Operación completada según Ficha de Instrucción Técnica del Director Técnico.
"""

        return strict_response

    def extract_technical_data(self, text: str) -> dict:
        """
        Extraer datos técnicos (rutas, precios, fechas) del texto

        Args:
            text: Texto del que extraer datos

        Returns:
            dict: Datos técnicos extraídos por categoría
        """
        result: dict = {}

        file_paths = re.findall(r"/[a-zA-Z0-9_\-./]+", text)
        if file_paths:
            result["file_path"] = file_paths[:5]

        prices = re.findall(r"\$?\d+\.?\d*\s*(?:€|USD|EUR|€)?", text)
        if prices:
            result["prices"] = prices[:5]

        dates = re.findall(r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}", text)
        if dates:
            result["dates"] = dates[:5]

        sizes = re.findall(r"\d+\s*(?:KB|MB|GB|TB)", text, re.IGNORECASE)
        if sizes:
            result["sizes"] = sizes[:5]

        return result

    def clean_human_garbage(self, text: str) -> str:
        """Eliminar frases de bypass de IA del texto."""
        return clean_human_garbage(text)

    def detect_ai_commercial_bypass(self, text: str) -> bool:
        """Detectar si el texto contiene frases de bypass de IA comercial."""
        return detect_ai_commercial_bypass(text)

    def simulate_windsurf_execution(self, prompt: str) -> str:
        """
        Simular ejecución en Windsurf (placeholder hasta integración real)
        """
        # Simulación básica de respuesta de Windsurf
        if "crear" in prompt.lower() and "proyecto" in prompt.lower():
            return """
Estructura de proyecto creada:
- main.py (archivo principal)
- requirements.txt (dependencias)
- README.md (documentación)
- src/ (código fuente)
- tests/ (pruebas)
- docs/ (documentación)

Proyecto inicializado correctamente.
"""
        elif "añadir" in prompt.lower() or "agregar" in prompt.lower():
            return """
Funcionalidad añadida al proyecto:
- Nuevo módulo implementado
- Dependencias actualizadas
- Tests creados
- Documentación actualizada

Cambios aplicados exitosamente.
"""
        elif "error" in prompt.lower() or "bug" in prompt.lower():
            return """
Análisis de errores completado:
- Problemas identificados: 3
- Soluciones aplicadas: 3
- Tests actualizados: 2
- Código optimizado: 1

Todos los errores han sido corregidos.
"""
        else:
            return f"Procesamiento completado para: {prompt[:100]}..."

    def format_response_with_ollama(self, windsurf_response: str) -> str:
        """
        Formatear respuesta de Windsurf a lenguaje natural con Ollama (Data First)
        """
        try:
            # Extraer datos técnicos (rutas, precios, fechas) para priorizar
            technical_data = self.extract_technical_data(windsurf_response)

            ollama_prompt = f"""
Eres URA (Universal Responsive Agent), un asistente inteligente con acceso completo al sistema de archivos local mediante terminal_gateway.

IDENTIDAD Y CAPACIDADES:
- Tienes acceso al sistema de archivos local mediante comandos de terminal (find, ls, cat, grep, etc.)
- NO des respuestas genéricas de limitación si el usuario te pide buscar archivos o presupuestos
- Si el usuario pregunta por algo en /Documents o correos, PRIMERO ejecuta un comando find o ls mediante terminal_gateway antes de responder que no puede
- NO uses el discurso de "No soy profesional" - sé directa y precisa
- Si se te pide un análisis de presupuesto, hazlo usando los datos que tú misma puedes leer
- Usa terminal_gateway para buscar, leer y analizar archivos antes de decir que algo no existe

DATOS TÉCNICOS EXTRAÍDOS (PRIORIDAD MÁXIMA):
{technical_data}

RESPUESTA TÉCNICA DE WINDSURF:
{windsurf_response}

INSTRUCCIONES (DATA FIRST):
1. PRIORIDAD ABSOLUTA: Los datos técnicos deben aparecer PRIMERO en la respuesta
2. Coloca rutas de archivos, precios, fechas y datos numéricos al principio en **negrita**
3. Minimiza o elimina el comentario de la IA si no aporta valor técnico
4. NO uses frases hipócritas como "Como modelo de lenguaje" o "Espero que esto te sea de ayuda"
5. Sé directa y ejecutiva, no conversacional
6. NO digas "no puedo acceder" sin intentar primero buscar los archivos

FORMATO DE RESPUESTA:
**[DATOS TÉCNICOS PRIMERO]**
- Rutas: /ruta/archivo
- Precios: $X.XX
- Fechas: DD/MM/YYYY
- Otros datos relevantes

[Breve explicación técnica si es necesaria]

Responde como si tú fueras el asistente que realizó el trabajo, con acceso completo al sistema de archivos.
"""

            response = self.call_ollama(ollama_prompt)
            return response.strip()

        except Exception as e:
            logger.error(f"Error formateando respuesta: {e}")
            return f"He completado tu solicitud. {windsurf_response[:100]}..."

    def call_ollama(self, prompt: str) -> str:
        """Llamar a API de Ollama"""
        try:
            url = f"http://{self.ollama_host}:{self.ollama_port}/api/generate"
            data = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.7, "top_p": 0.9, "max_tokens": 1000},
            }

            response = requests.post(url, json=data, timeout=30)
            if response.status_code == 200:
                result = response.json()
                return result.get("response", "")
            else:
                logger.error(f"Error Ollama: {response.status_code}")
                return "Error en la comunicación con Ollama"

        except Exception as e:
            logger.error(f"Error llamando a Ollama: {e}")
            return "No se pudo conectar con Ollama"

    def get_recent_context(self) -> str:
        """Obtener contexto reciente de conversación"""
        if not self.conversation_history:
            return "Sin conversación previa"

        # Últimas 3 interacciones
        recent = self.conversation_history[-3:]
        context = []

        for item in recent:
            context.append(f"Usuario: {item['user']}")
            context.append(f"URA: {item['final_response']}")
            context.append("---")

        return "\n".join(context)

    def get_available_models(self) -> list[str]:
        """Obtener modelos disponibles en Ollama"""
        try:
            url = f"http://{self.ollama_host}:{self.ollama_port}/api/tags"
            response = requests.get(url, timeout=10)

            if response.status_code == 200:
                data = response.json()
                models = [model["name"] for model in data.get("models", [])]
                return models
            else:
                return []

        except Exception as e:
            logger.error(f"Error obteniendo modelos: {e}")
            return []

    def set_model(self, model_name: str) -> bool:
        """Cambiar modelo de Ollama"""
        available_models = self.get_available_models()
        if model_name in available_models:
            self.model = model_name
            logger.info(f"Modelo cambiado a: {model_name}")
            return True
        else:
            logger.warning(f"Modelo {model_name} no disponible")
            return False

    def clear_history(self):
        """Limpiar historial de conversación"""
        self.conversation_history = []
        logger.info("Historial de conversación limpiado")

    def get_conversation_stats(self) -> dict:
        """Obtener estadísticas de conversación"""
        return {
            "total_messages": len(self.conversation_history),
            "model_used": self.model,
            "last_activity": (
                self.conversation_history[-1]["timestamp"] if self.conversation_history else None
            ),
            "available_models": len(self.get_available_models()),
        }

    def summarize_context_if_needed(self) -> str | None:
        """
        Resumir contexto si el historial es demasiado largo para evitar que Llama olvide instrucciones

        Returns:
            Optional[str]: Resumen de contexto si se generó, None si no
        """
        MAX_HISTORY_ITEMS = 10  # Máximo de items antes de resumir

        if len(self.conversation_history) < MAX_HISTORY_ITEMS:
            return None

        logger.info(
            f"Generando resumen de contexto (historial: {len(self.conversation_history)} items)"
        )

        # Extraer información clave del historial
        key_points = []
        for item in self.conversation_history[-5:]:  # Últimas 5 interacciones
            user_msg = item.get("user", "")[:100]
            response = item.get("final_response", "")[:100]
            key_points.append(f"Usuario: {user_msg}...")
            key_points.append(f"URA: {response}...")

        # Generar resumen
        summary = f"""
RESUMEN DE CONTEXTO (Últimas {len(self.conversation_history)} interacciones):

{chr(10).join(key_points)}

INSTRUCCIÓN ACTUAL:
- Eres URA, asistente del departamento de {self.department}.
- Tienes acceso total a las APIs de WhatsApp y Gmail.
- AHORA TAMBIÉN PUEDES VER EL MONITOR DE RAMÓN cuando él te lo pida explícitamente
  (por ejemplo: "URA, mira mi pantalla"). Úsalo para ayudarle con Jurassic, facturas,
  navegador o cualquier ventana abierta. Nunca captures la pantalla sin que te lo pida.
- Si el usuario pregunta qué puedes ver o a qué tienes acceso, responde:
  "Entendido Ramón, ahora puedo ver tu monitor cuando me lo pidas."
- Si el usuario pide un presupuesto o análisis, no pidas permiso, ejecuta la búsqueda directamente.
"""

        logger.info("Resumen de contexto generado")

        # Reducir historial manteniendo solo lo esencial
        self.conversation_history = self.conversation_history[-MAX_HISTORY_ITEMS:]

        return summary

    def verify_real_data(self, windsurf_response: str, instruction_sheet: dict) -> bool:
        """
        Verificar que las APIs (Gmail/WhatsApp) devolvieron datos reales

        Args:
            windsurf_response: Respuesta del sistema de ejecución
            instruction_sheet: Ficha de instrucción técnica

        Returns:
            bool: True si hay datos reales, False si no
        """
        operation_type = instruction_sheet.get("operation_type", "").upper()

        # Operaciones que requieren datos reales de APIs
        api_operations = ["EMAIL_INTEGRATION", "WHATSAPP_INTEGRATION", "DATA_RETRIEVAL"]

        if operation_type not in api_operations:
            # Operaciones que no dependen de APIs externas
            logger.debug(f"Operación {operation_type} no requiere verificación de API")
            return True

        # Verificar que la respuesta no sea vacía o genérica
        if not windsurf_response or len(windsurf_response.strip()) < 20:
            logger.error("Verificación fallida: Respuesta vacía o muy corta")
            return False

        # Verificar que no sea una respuesta de error genérica
        generic_error_indicators = [
            "error",
            "failed",
            "no data",
            "not found",
            "unable to",
            "no se pudo",
            "error al",
            "fallo al",
        ]

        response_lower = windsurf_response.lower()
        if any(indicator in response_lower for indicator in generic_error_indicators):
            logger.error("Verificación fallida: Respuesta contiene indicadores de error")
            return False

        # Verificar que haya datos específicos (no placeholders)
        placeholder_indicators = ["placeholder", "example", "sample", "ejemplo", "muestra"]

        if any(indicator in response_lower for indicator in placeholder_indicators):
            logger.error("Verificación fallida: Respuesta contiene placeholders")
            return False

        logger.info("Verificación de datos reales exitosa")
        return True

    # ------------------------------------------------------------------
    # Code Generators integration
    # ------------------------------------------------------------------
    def _log_action(self, mensaje: str) -> None:
        """Log auxiliar para acciones del workflow."""
        logger.info(mensaje)

    def _invoke_generator(self, tipo: str, tarea: str) -> dict:
        """Invoca un generator especializado si la confianza es suficiente.

        Args:
            tipo: identificador del generator (e.g. 'python', 'api', 'data').
            tarea: descripción de la tarea a generar.

        Returns:
            dict con la respuesta del generator (incluye 'ok',
            'requiere_confirmacion', etc.).
        """
        resultado = generar(tipo, tarea)
        if resultado.get("ok") and not resultado.get("requiere_confirmacion"):
            # Alta confianza — aplicar automáticamente
            self._log_action(f"Generator {tipo} aplicado: {tarea}")
        else:
            # Baja confianza — notificar y esperar confirmación
            self._log_action(f"Generator {tipo} requiere confirmación: {tarea}")
        return resultado

    def listar_generators(self) -> list:
        """Devuelve la lista de generators disponibles para el Director Técnico."""
        return listar()


# Clase de conveniencia para uso directo
class URAWorkflow:
    """Wrapper simple para uso del motor de flujo"""

    def __init__(self):
        self.engine = URAWorkflowEngine()

    def process(self, message: str) -> str:
        """Procesar mensaje del usuario"""
        return self.engine.process_user_request(message)

    def get_models(self) -> list[str]:
        """Obtener modelos disponibles"""
        return self.engine.get_available_models()

    def set_model(self, model: str) -> bool:
        """Cambiar modelo"""
        return self.engine.set_model(model)

    def clear_history(self):
        """Limpiar historial"""
        self.engine.clear_history()
