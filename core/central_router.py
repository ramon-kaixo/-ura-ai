#!/usr/bin/env python3
"""
Central Router - Router Central de URA
Detecta intención y enruta consultas al agente apropiado.
"""

import asyncio
import concurrent.futures
import logging
import random
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from core.shared_memory import get_shared_memory
from core.unified_logger import get_unified_logger
from core.forensic_scribe import get_forensic_scribe
from core.observability import Observability, URALogger, MetricsDashboard
from core.ura_diary import get_ura_diary
from core.timeout_manager import get_timeout_manager

logger = logging.getLogger(__name__)

# Singleton para trazabilidad
_scribe = get_forensic_scribe()

ROUTER_LOG = Path.home() / ".ura" / "router.log"
ROUTER_LOG.parent.mkdir(parents=True, exist_ok=True)


# === DICCIONARIO DE PALABRAS CLAVE CON PESOS (primer filtro) ===
KEYWORD_WEIGHTS = {
    "tailscale": {
        "tailscale": 5,
        "conectar vpn": 5,
        "red privada": 5,
        "conectar red": 5,
        "conéctame a": 3,
        "vpn": 3,
        "túnel": 3,
        "wireguard": 3,
        "conexión remota": 3,
        "tail": 2,
        "scale": 2,
        "red encriptada": 3,
        "mesh": 2,
        "enrutar tráfico": 3,
    },
    "facturas": {
        "crear factura": 5,
        "emitir factura": 5,
        "factura": 4,
        "factura para": 5,
        "cobro": 3,
        "facturar": 4,
        "factura electrónica": 5,
        "recibo": 3,
        "albarán": 3,
        "cuenta de cobro": 4,
        "emitir recibo": 5,
        "registrar pago": 4,
    },
    "cocina_peruana": {
        "cocina peruana": 5,
        "receta peruana": 5,
        "ceviche": 5,
        "lomo saltado": 5,
        "ají de gallina": 5,
        "causa limeña": 5,
        "comida peruana": 5,
        "plato peruano": 5,
        "gastronomía peruana": 5,
        "pisco sour": 5,
        "chicha morada": 5,
    },
    "cocina_espanola": {
        "cocina española": 5,
        "receta española": 5,
        "paella": 5,
        "tortilla de patatas": 5,
        "cocido": 4,
        "gazpacho": 4,
        "fabada": 4,
        "pulpo a la gallega": 5,
        "jamón": 3,
        "receta de lentejas": 5,
        "receta lentejas": 5,
        "lentejas": 4,
        "lentejas estofadas": 5,
        "lentejas con chorizo": 5,
        "garbanzos": 4,
        "potaje": 4,
        "estofado": 4,
        "callos": 4,
        "cordero asado": 4,
        "receta de": 3,
    },
    "seguridad": {
        "seguridad del sistema": 5,
        "seguridad sistema": 5,
        "seguridad informática": 5,
        "firewall": 5,
        "antivirus": 5,
        "blindaje sistema": 5,
        "blindaje": 4,
        "proteger sistema": 5,
        "auditar seguridad": 5,
        "amenaza": 4,
        "vulnerabilidad": 4,
        "intrusión": 4,
        "ataque": 4,
        "malware": 4,
    },
    "investigador_ia": {
        "modelos de ia": 5,
        "modelos ia": 5,
        "inteligencia artificial": 4,
        "investigar ia": 5,
        "investigador ia": 5,
        "investigador de ia": 5,
        "investigador": 4,
        "nuevos modelos": 4,
        "machine learning": 4,
        "deep learning": 4,
        "llm": 4,
        "modelo lenguaje": 4,
        "tendencia ia": 4,
        "herramienta ia": 4,
        "buscar información": 3,
        "investigar": 2,
    },
    "backup": {
        "copia de seguridad": 5,
        "copia seguridad": 5,
        "backup": 5,
        "hacer backup": 5,
        "snapshot": 5,
        "restaurar copia": 5,
        "restaurar backup": 5,
        "copia del sistema": 5,
        "backup sistema": 5,
        "respaldo": 4,
        "copia automática": 4,
        "restaurar sistema": 5,
    },
    "tendencias_pamplona": {
        "menú pamplona": 5,
        "bar pamplona": 5,
        "restaurante pamplona": 5,
        "tendencia pamplona": 5,
        "pintxos pamplona": 5,
        "san fermín": 5,
        "navarrería": 5,
        "comer pamplona": 5,
        "cocina navarra": 4,
    },
    "conectividad": {
        "red wifi": 5,
        "estado de la red": 5,
        "conectividad": 5,
        "internet": 3,
        "conexión": 2,
        "wifi": 3,
        "router": 3,
    },
    "hardware": {
        "ram": 5,
        "cpu": 5,
        "memoria": 4,
        "rendimiento sistema": 5,
        "hardware": 5,
        "procesador": 4,
        "disco": 3,
    },
    "marketing": {
        "banner": 5,
        "instagram": 4,
        "facebook": 4,
        "campaña": 4,
        "promoción": 4,
        "anuncio": 4,
        "marketing": 5,
    },
    "laboral": {
        "contrato": 5,
        "contrato de trabajo": 5,
        "revisar contrato": 5,
        "nómina": 5,
        "despido": 5,
        "seguridad social": 5,
        "laboral": 5,
    },
}


class CentralRouter:
    """Router central que detecta intención y ejecuta agentes."""

    _instance: Optional["CentralRouter"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized"):
            return
        self._initialized = True
        self.embedding_service = None
        self.maleta_manager = None
        self.shared_memory = get_shared_memory()
        self.unified_logger = get_unified_logger()
        self.observability = Observability()
        self.metrics_dashboard = MetricsDashboard()
        self.diary = get_ura_diary()
        self.timeout_manager = get_timeout_manager()
        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=8, thread_name_prefix="central_router"
        )
        self._load_services()
        self.intent_keywords = _build_intent_keywords()
        self.intent_to_agent = _build_intent_to_agent()
        self._intent_detector = None  # lazy init

    def _load_services(self):
        try:
            from core.embedding_service import EmbeddingService

            self.embedding_service = EmbeddingService()
            logger.info("Embedding service cargado en router")
        except Exception as e:
            logger.warning(f"No se pudo cargar embedding service: {e}, usando palabras clave")
        try:
            from core.ura_maleta_manager import get_maleta_manager

            self.maleta_manager = get_maleta_manager()
            logger.info("Maleta manager cargado en router")
        except Exception as e:
            logger.warning(f"No se pudo cargar maleta manager: {e}")

    def _log(self, event_type: str, details: str):
        """Registrar evento en log del router."""
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(ROUTER_LOG, "a", encoding="utf-8") as f:
                f.write(f"[{timestamp}] [{event_type}] {details}\n")
        except Exception as e:
            logger.error(f"Error registrando en router.log: {e}")

    def _detect_intent_keywords(self, texto: str) -> tuple[str, float]:
        """
        Detectar intención usando palabras clave con doble filtro y pesos específicos.

        PRIMER FILTRO: Palabras clave con peso (usando KEYWORD_WEIGHTS)
        - Usa el diccionario KEYWORD_WEIGHTS para pesos específicos
        - Si no está en KEYWORD_WEIGHTS, usa peso por defecto (3.0 para frases compuestas, 1.0 para simples)

        SEGUNDO FILTRO: Embeddings solo para desambiguación
        - Si hay 2+ agentes con el mismo peso, usar embeddings
        - Si diferencia de peso >= 3, usar el ganador directo sin embeddings
        """
        texto_lower = texto.lower()

        # PRIMER FILTRO: Calcular scores por keywords usando KEYWORD_WEIGHTS
        scores = {}
        for intent, keywords in self.intent_keywords.items():
            score = 0.0
            # Verificar si este intent tiene pesos específicos en KEYWORD_WEIGHTS
            intent_weights = KEYWORD_WEIGHTS.get(intent, {})

            for kw in keywords:
                if kw.lower() in texto_lower:
                    # Usar peso específico si existe, sino peso por defecto
                    if kw in intent_weights:
                        score += intent_weights[kw]
                    elif " " in kw:  # Frase compuesta (peso por defecto)
                        score += 3.0
                    else:  # Palabra simple (peso por defecto)
                        score += 1.0
            scores[intent] = score

        # Ordenar por score descendente
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)

        # Si no hay coincidencias
        if not sorted_scores or sorted_scores[0][1] == 0:
            return "chat", 0.5

        best_intent, best_score = sorted_scores[0]

        # Verificar si hay un ganador claro (diferencia >= 3)
        if len(sorted_scores) > 1:
            second_score = sorted_scores[1][1]
            if best_score - second_score >= 3:
                # Ganador claro, usar directo
                confidence = min(best_score / 5.0, 1.0)
                return best_intent, confidence

        # SEGUNDO FILTRO: Usar embeddings para desambiguación
        if self.embedding_service:
            return self._detect_intent_embedding(texto)

        # Si no hay embedding service, usar el mejor score de keywords
        confidence = min(best_score / 5.0, 1.0)
        return best_intent, confidence

    def _detect_intent_embedding(self, texto: str) -> tuple[str, float]:
        """Detectar intención usando embeddings."""
        if not self.embedding_service:
            return self._detect_intent_keywords(texto)

        # Embeddings de ejemplo para cada intención (actualizados con 50 agentes)
        intent_examples = {
            # COCINA
            "cocina_espanola": "receta española cocina plato",
            "cocina_navarra": "receta navarra temporada menestra",
            "gastronomo_musica": "música playlist sonido restaurante",
            "vocabulario_gastronomico": "vocabulario cocina técnica culinaria",
            "vocabulario_bar": "bar coctel bebida vocabulario",
            "media_recetas": "video receta foto multimedia",
            # CONTABILIDAD/FINANZAS
            "administrativo_contable": "administrativo papelería contable",
            "contabilidad": "factura iva impuesto contabilidad",
            "facturas": "factura cobrar recibo pago",
            "banco": "banco transferencia cuenta saldo",
            "vocabulario_financiero": "vocabulario financiero económico",
            # MARKETING
            "marketing": "banner campaña publicidad instagram",
            "creativo_marketing": "crear contenido diseño creativo",
            "marketing_navarra": "marketing navarra promoción local",
            "galeria_videos": "video galería multimedia grabación",
            "galeria_fotos": "foto galería imagen fotografía",
            # LEGAL/RRHH
            "juridico": "jurídico legal abogado consulta",
            "laboral": "laboral contrato trabajo convenio",
            "rrhh": "contrato empleado trabajador nómina",
            "camaras": "cámara videovigilancia seguridad",
            "vocabulario_legal": "vocabulario legal jurídico",
            "policia": "policía seguridad denuncia protección",
            # SISTEMA
            "tailscale": "tailscale vpn red privada conectar",
            "automatizador": "automatizar script tarea automática",
            "conectividad": "red wifi conexión internet",
            "red_telefonia": "telefonía teléfono voip llamada",
            "hardware": "hardware servidor cpu equipo",
            "scheduler": "programar agenda calendario horario",
            "gobierno": "gobierno trámite administración burocracia",
            # DOCUMENTOS
            "documentos_pdf": "pdf documento leer extraer",
            "documentos_texto": "texto documento leer extraer",
            "documentos_word": "word docx documento editar",
            "documentos_excel": "excel hoja cálculo datos",
            "documentos_presentaciones": "presentación powerpoint diapositivas",
            "orquestador_documentacion": "documentación biblioteca gestión",
            "archivist": "archivar archivo organizar clasificar",
            "librarian": "biblioteca catálogo libros referencias",
            # COMUNICACIÓN
            "email": "email correo enviar mensaje",
            "notificaciones": "notificación alerta aviso informar",
            "conversacion": "conversación saludo gracias hola",
            # IA/CONOCIMIENTO
            "investigador_ia": "investigar research estudiar datos",
            "conciencia": "conciencia memoria aprender conocimiento",
            "memoria": "memoria recordar guardar recuperar",
            "lenguaje": "lenguaje idioma traducir interpretar",
            "vocabulario": "vocabulario diccionario definición",
            "vocabulario_codigo": "código programación vocabulario",
            "vocabulario_tecnico": "técnico vocabulario tecnología",
            "vision": "visión imagen ver reconocer ocr",
            # GUI
            "gui": "gui interfaz clic pantalla automatizar",
            # ASESORÍA
            "asesor": "asesor asesoría consejo recomendación",
            # EXISTENTES
            "busqueda": "buscar investigar encontrar información",
            "sistema": "archivo sistema módulo entrenamiento",
            "chat": "hola conversación saludo gracias",
        }

        best_intent = "chat"
        best_similarity = 0.0

        for intent, example in intent_examples.items():
            similarity = self.embedding_service.similarity(texto, example)
            if similarity > best_similarity:
                best_similarity = similarity
                best_intent = intent

        return best_intent, best_similarity


async def process_request(self, texto: str) -> dict:
    """
    Procesar solicitud y enrutar al agente apropiado.

    Args:
        texto: Texto de la consulta

    Returns:
        Dict con {'intent': str, 'agent': str, 'response': str, 'confidence': float, 'metadata': dict}
    """
    trace_id = f"req_{int(time.time() * 1000)}_{random.randint(1000, 9999)}"
    t_start = time.time()
    obs_logger = URALogger("central_router")
    obs_logger.log_inicio({"texto": texto[:200]}, trace_id=trace_id)
    self.observability.agregar_trace(trace_id, "central_router", "process_request", 0)

    _scribe.log_event(
        event_type="task_start",
        module="central_router",
        action="process_request",
        context={"texto": texto[:200], "trace_id": trace_id},
        dependencies=[],
    )

    maestro_response = await check_agente_maestro(texto)
    if maestro_response and "No estoy seguro" not in maestro_response:
        return log_introspeccion(maestro_response, trace_id)

    intent, confidence = self._detect_intent_keywords(texto)
    if confidence < 0.55:
        return log_confianza_baja(confidence, trace_id)

    agent_path = self.intent_to_agent.get(intent, "chat")
    response = await self.execute(intent, texto, confidence)
    metadata = self._get_agent_metadata(intent, agent_path)

    result = {
        "intent": intent,
        "agent": agent_path,
        "response": response,
        "confidence": confidence,
        "metadata": metadata,
    }

    log_resultado(result, trace_id)
    return result


async def check_agente_maestro(texto: str) -> str:
    from core.agente_maestro import get_agente_maestro

    maestro = get_agente_maestro()
    respuesta_maestro = await maestro.preguntar(texto)
    return respuesta_maestro


def log_introspeccion(respuesta_maestro: str, trace_id: str) -> dict:
    duration_ms = int((time.time() - t_start) * 1000)
    obs_logger.log_ok(respuesta_maestro[:500], trace_id=trace_id, duracion_ms=duration_ms)
    self.observability.agregar_trace(trace_id, "central_router", "process_request", duration_ms)
    return {
        "intent": "introspeccion",
        "agent": "agente_maestro",
        "response": respuesta_maestro,
        "confidence": 1.0,
        "metadata": {"meta_agente": "registry + conciencia", "tipo": "introspeccion"},
    }


def log_confianza_baja(confidence: float, trace_id: str) -> dict:
    duration_ms = int((time.time() - t_start) * 1000)
    obs_logger.log_error("Confianza baja", trace_id=trace_id)
    self.observability.agregar_trace(trace_id, "central_router", "process_request", duration_ms)
    return {
        "intent": "chat",
        "agent": "chat",
        "response": "No he entendido bien. ¿Puedes ser más específico?",
        "confidence": confidence,
        "metadata": {},
    }


def log_resultado(result: dict, trace_id: str) -> None:
    _log_response(result, trace_id)
    _add_trace_to_observability(trace_id, "central_router", "process_request")
    _scribe_log_event(result, trace_id)


def _log_response(result: dict, trace_id: str) -> None:
    duration_ms = int((time.time() - t_start) * 1000)
    obs_logger.log_ok(
        str(result.get("response", ""))[:500],
        trace_id=trace_id,
        duracion_ms=duration_ms,
    )


def _add_trace_to_observability(trace_id: str, module: str, action: str, duration_ms: int) -> None:
    self.observability.agregar_trace(trace_id, module, action, duration_ms)


def _scribe_log_event(result: dict, trace_id: str) -> None:
    _scribe.log_event(
        event_type="task_success",
        module="central_router",
        action="process_request",
        context={
            "trace_id": trace_id,
            "intent": result.get("intent"),
            "agent": result.get("agent"),
            "response_length": len(str(result.get("response", ""))),
            "duration_ms": int((time.time() - t_start) * 1000),
        },
        dependencies=[result.get("agent", "unknown")],
    )


def _call_agent_with_timeout(
    self, agent_name: str, method: callable, texto: str, timeout_s: float = 120.0
) -> dict:
    """Llamar a un metodo de agente con timeout via ThreadPoolExecutor."""
    try:
        future = self._executor.submit(method, texto)
        result = future.result(timeout=timeout_s)
        if isinstance(result, dict):
            return result
        return {"success": True, "response": str(result), "error": ""}
    except concurrent.futures.TimeoutError:
        self.timeout_manager.register_timeout(agent_name, method.__name__, timeout_s, timeout_s)
        return {
            "success": False,
            "response": "",
            "error": f"Timeout: {agent_name}.{method.__name__} excedio {timeout_s}s",
        }
    except Exception as e:
        return {"success": False, "response": "", "error": str(e)}


async def agent_execute(self, agent_path: str, texto: str) -> dict:
    """
    Metodo universal para ejecutar cualquier agente.
    Detecta automaticamente el metodo principal del agente y lo ejecuta.

    Args:
        agent_path: Ruta del agente (ej: "agents.agente_asesor.AgenteAsesor")
        texto: Texto de la consulta

    Returns:
        Dict con {"success": bool, "response": str, "error": str}
    """
    t_start = time.time()
    agent_name = agent_path.split(".")[-1] if "." in agent_path else agent_path
    agent_logger = URALogger(agent_name)
    trace_id = str(uuid.uuid4())
    agent_logger.log_inicio({"texto": texto[:200]}, trace_id=trace_id)
    self.observability.agregar_trace(trace_id, agent_name, "agent_execute", 0)

    result_dict = None
    error_msg = ""

    try:
        # Casos especiales
        if agent_path == "system":
            result_dict = {
                "success": True,
                "response": self._system_response(texto),
                "error": "",
            }
        else:
            # Importar agente
            module_path, class_name = agent_path.rsplit(".", 1)
            module = __import__(module_path, fromlist=[class_name])
            agent_class = getattr(module, class_name)
            agent = agent_class()

            # Prioridad 1: Método execute() estándar (nuevo)
            if hasattr(agent, "execute"):
                result_dict = _call_agent_with_timeout(agent_name, agent.execute, texto)
            # Prioridad 2: Método procesar()
            elif hasattr(agent, "procesar"):
                result_dict = _call_agent_with_timeout(agent_name, agent.procesar, texto)
            # Prioridad 3: Método ejecutar()
            elif hasattr(agent, "ejecutar"):
                result_dict = _call_agent_with_timeout(agent_name, agent.ejecutar, texto)
            # Prioridad 4: Método consultar()
            elif hasattr(agent, "consultar"):
                result_dict = _call_agent_with_timeout(agent_name, agent.consultar, texto)
            # Prioridad 5: Método responder()
            elif hasattr(agent, "responder"):
                result_dict = _call_agent_with_timeout(agent_name, agent.responder, texto)
            # Prioridad 6: Método run()
            elif hasattr(agent, "run"):
                result_dict = _call_agent_with_timeout(agent_name, agent.run, texto)
            # Prioridad 7: Método search()
            elif hasattr(agent, "search"):
                result_dict = _call_agent_with_timeout(agent_name, agent.search, texto)
            # Prioridad 8: Método process()
            elif hasattr(agent, "process"):
                result_dict = _call_agent_with_timeout(agent_name, agent.process, texto)
            # Fallback: mensaje genérico
            else:
                result_dict = {
                    "success": False,
                    "response": "",
                    "error": "No se encontró método de ejecución compatible",
                }

    except Exception as e:
        error_msg = str(e)

    duration_ms = int((time.time() - t_start) * 1000)

    if result_dict:
        agent_logger.log_ok(
            str(result_dict.get("response", ""))[:500],
            trace_id=trace_id,
            duracion_ms=duration_ms,
        )
    else:
        agent_logger.log_error(error_msg, trace_id=trace_id)

    self.observability.agregar_trace(trace_id, agent_name, "agent_execute", duration_ms)

    return result_dict or {"success": False, "response": "", "error": error_msg}


async def execute(self, intent: str, texto: str, confidence: float = 0.5) -> str:
    """
    Ejecutar agente correspondiente.

    Args:
        intent: Intención detectada
        texto: Texto de la consulta
        confidence: Confianza de la detección (para degradación)

    Returns:
        Respuesta del agente
    """
    # Primero, comprobar si hay una maleta promocionada para este dominio
    cached_response = self.check_maleta_cache(intent, texto)
    if cached_response:
        self._log("CACHE_HIT", f"Intent: {intent}, Maleta cache usada")
        return cached_response

    agent_path = self.intent_to_agent.get(intent, "chat")

    # Casos especiales
    if intent == "chat":
        return self._chat_response(texto)
    elif intent == "sistema":
        return self._system_response(texto)

    # Usar el método universal agent_execute
    result = await agent_execute(agent_path, texto)

    if result["success"]:
        return result["response"]
    else:
        # Fallback a lógica específica para algunos agentes (solo si confidence >= 0.70)
        if confidence >= 0.70:
            return await self._execute_with_fallback(intent, texto, agent_path, result["error"])
        else:
            return f"Lo siento, hubo un error procesando tu solicitud: {result['error']}"


async def _execute_with_fallback(self, intent: str, texto: str, agent_path: str, error: str) -> str:
    """
    Ejecutar agente con lógica específica como fallback cuando agent_execute falla.

    Args:
        intent: Intención detectada
        texto: Texto de la consulta
        agent_path: Ruta del agente
        error: Error del intento anterior

    Returns:
        Respuesta del agente o mensaje de error
    """
    try:
        module_path, class_name = agent_path.rsplit(".", 1)
        module = __import__(module_path, fromlist=[class_name])
        agent_class = getattr(module, class_name)
        agent = agent_class()

        response = await _handle_intent_specific_logic(self, intent, texto, agent)
    except Exception as e:
        error_msg = f"Error ejecutando agente {agent_path}: {str(e)}"
        self._log("ERROR", error_msg)

        similar_intent = self._find_similar_agent(intent)
        if similar_intent:
            similar_path = self.intent_to_agent.get(similar_intent)
            self._log(
                "DEGRADATION",
                f"Intent original: {intent}, Degradando a: {similar_intent}",
            )

            self.unified_logger.log_degradation(
                original_agent=intent, fallback_agent=similar_intent, reason=error_msg
            )

            try:
                module_path, class_name = similar_path.rsplit(".", 1)
                module = __import__(module_path, fromlist=[class_name])
                agent_class = getattr(module, class_name)
                agent = agent_class()

                response = await _handle_fallback_methods(agent, texto)
            except Exception as e2:
                return f"Lo siento, hubo un error procesando tu solicitud: {error_msg}. Degradación fallida: {str(e2)}"
        else:
            response = f"Lo siento, hubo un error procesando tu solicitud: {error_msg}"

    return response


async def _handle_intent_specific_logic(self, intent: str, texto: str, agent) -> str:
    if intent == "contabilidad":
        return await _handle_contabilidad_intent(texto, agent)
    elif intent == "marketing":
        return await _handle_marketing_intent(texto, agent)
    elif intent == "cocina":
        return await _handle_cocina_intent(texto, agent)
    elif intent == "cocina_internacional":
        return await _handle_cocina_internacional_intent(texto, agent)
    elif intent == "leyes":
        return await _handle_leyes_intent(texto, agent)
    elif intent == "rrhh":
        return await _handle_rrhh_intent(texto, agent)
    elif intent == "busqueda":
        return await _handle_busqueda_intent(texto, agent)
    elif intent == "explorar":
        return await _handle_explorar_intent(texto, agent)
    else:
        return f"Agente {intent} activo. Método de ejecución no implementado aún."


async def _handle_contabilidad_intent(texto: str, agent) -> str:
    if "software" in texto.lower():
        return agent.recomendar_software()
    elif "asiento" in texto.lower():
        return str(agent.generar_asiento("Gasto", 100, 0, 121, 21))
    elif "deducción" in texto.lower():
        ded = agent.consultar_deduccion("inversión")
        return str(ded) if ded else "No se encontró deducción específica"
    else:
        return f"Agente de contabilidad: {agent.recomendar_software()}"


async def _handle_marketing_intent(texto: str, agent) -> str:
    if "banner" in texto.lower():
        return agent.crear_banner("Oferta especial")
    elif "video" in texto.lower():
        return agent.crear_video_promocional("Promo", 10)
    else:
        return "Agente de marketing disponible"


async def _handle_cocina_intent(texto: str, agent) -> str:
    ingredientes = [w for w in texto.split() if len(w) > 3]
    recetas = agent.buscar_receta(ingredientes)
    if recetas:
        return f"Receta encontrada: {recetas[0]['nombre']}"
    return "No se encontraron recetas con esos ingredientes"


async def _handle_cocina_internacional_intent(texto: str, agent) -> str:
    plato = texto.split()[-1] if texto.split() else "tacos"
    recetas = agent.buscar_receta_internacional(plato)
    if recetas:
        return f"Receta internacional: {recetas[0]['nombre']} ({recetas[0]['pais']})"
    return "No se encontraron recetas internacionales"


async def _handle_leyes_intent(texto: str, agent) -> str:
    tema = texto.split()[-1] if texto.split() else "ruido"
    norma = agent.consultar_normativa(tema)
    if norma:
        return f"Normativa: {norma['descripcion']}"
    return "No se encontró normativa específica"


async def _handle_rrhh_intent(texto: str, agent) -> str:
    if "contrato" in texto.lower():
        return str(agent.analizar_contrato("indefinido"))
    elif "cámara" in texto.lower():
        return str(agent.recomendar_camara("bar", 300))
    else:
        return "Agente RRHH disponible"


async def _handle_busqueda_intent(texto: str, agent) -> str:
    from core.buscadores.orchestrator import SearchOrchestrator

    orch = SearchOrchestrator()
    result = await orch.search(texto)
    return f"Búsqueda completada: {len(result.results)} resultados"


async def _handle_explorar_intent(texto: str, agent) -> str:
    from core.explorador_sistemico import get_explorador

    explorador = get_explorador()
    # Extraer URL y acción del texto (formato esperado: "explorar <url> <accion>")
    palabras = texto.split()
    if len(palabras) >= 2:
        # Intentar detectar URL y acción
        url = None
        accion = texto
        for palabra in palabras:
            if "http" in palabra or "www" in palabra or ".com" in palabra or ".ovh" in palabra:
                url = palabra
                break
        if url:
            # Extraer acción (todo después de la URL)
            url_idx = texto.index(url)
            accion = texto[url_idx + len(url) :].strip()
            if not accion:
                accion = "explorar"
            # Ejecutar exploración
            resultado = explorador.explorar_y_ejecutar(url, accion)
            return f"Exploración completada: {'Exitosa' if resultado else 'Fallida'}"
    return "Explorador disponible. Usa formato: 'explorar <url> <accion>'"


async def _handle_fallback_methods(agent, texto) -> str:
    if hasattr(agent, "procesar"):
        return agent.procesar(texto)
    elif hasattr(agent, "ejecutar"):
        return agent.ejecutar(texto)
    elif hasattr(agent, "consultar"):
        return agent.consultar(texto)
    elif hasattr(agent, "responder"):
        return agent.responder(texto)
    else:
        return f"Agente {agent.__class__.__name__} activo. Método de ejecución no implementado aún."

    def _chat_response(self, texto: str) -> str:
        """Respuesta para chat general."""
        texto_lower = texto.lower()

        if any(w in texto_lower for w in ["hola", "buenos días", "buenas tardes", "buenas noches"]):
            return "¡Hola! Soy URA, tu asistente inteligente. ¿En qué puedo ayudarte hoy?"
        elif "gracias" in texto_lower:
            return "¡De nada! Estoy aquí para ayudarte cuando lo necesites."
        elif "cómo estás" in texto_lower or "qué tal" in texto_lower:
            return "Estoy funcionando perfectamente, gracias por preguntar. ¿Y tú qué necesitas?"
        else:
            return "Entiendo. ¿Podrías darme más detalles sobre lo que necesitas? Puedo ayudarte con contabilidad, marketing, cocina, leyes, RRHH, búsquedas y más."

    def _system_response(self, texto: str) -> str:
        """Respuesta para consultas de sistema."""
        return "Estado del sistema: URA funcionando correctamente. 162 módulos en core/, 6 agentes de negocio activos."


def check_maleta_cache(self, intent: str, query: str) -> str | None:
    """
    Comprueba si hay una maleta promocionada para el dominio con confianza > 0.85.
    Si existe, devuelve una respuesta instantánea de la maleta.

    Args:
        intent: Intención detectada
        query: Query del usuario

    Returns:
        Respuesta de la maleta o None si no hay cache hit
    """
    if not self.maleta_manager:
        return None

    domain = get_domain_from_intent(intent)
    if not domain:
        return None

    promoted_maletas = self.maleta_manager.get_promoted_maletas()
    domain_maletas = [m for m in promoted_maletas if m.get("domain") == domain]

    if not domain_maletas:
        return None

    best_maleta = get_best_matching_maleta(domain_maletas, query)
    return best_maleta


def get_domain_from_intent(intent: str) -> str | None:
    intent_to_domain = {
        # Mapeo de intención a dominio
    }

    return intent_to_domain.get(intent)


def get_best_matching_maleta(domain_maletas: list[dict], query: str) -> str | None:
    best_maleta = None
    best_similarity = 0.0

    for maleta in domain_maletas:
        if maleta.get("confidence", 0.0) < 0.85:
            continue

        queries = maleta.get("queries", [])
        responses = maleta.get("responses", [])

        if not queries or not responses:
            continue

        best_maleta = find_best_response(queries, responses, query)
        if best_maleta:
            break

    return best_maleta


def find_best_response(queries: list[str], responses: list[str], query: str) -> str | None:
    if self.embedding_service:
        return find_best_response_with_embedding_service(queries, responses, query)
    else:
        return find_best_response_fallback(queries, responses, query)


def find_best_response_with_embedding_service(
    queries: list[str], responses: list[str], query: str
) -> str | None:
    best_maleta = None
    best_similarity = 0.0

    for q, r in zip(queries, responses, strict=False):
        sim = self.embedding_service.similarity(query, q)
        if sim > best_similarity and sim > 0.75:
            best_similarity = sim
            best_maleta = r

    return best_maleta


def find_best_response_fallback(queries: list[str], responses: list[str], query: str) -> str | None:
    for q, r in zip(queries, responses, strict=False):
        if _is_similar_query(q, query):
            return r

    return None


def _is_similar_query(query1: str, query2: str) -> bool:
    query1_lower = query1.lower()
    query2_lower = query2.lower()
    common_words = set(query1_lower.split()) & set(query2_lower.split())
    return len(common_words) > 2


def _find_similar_agent(self, failed_intent: str) -> str | None:
    """Encontrar agente similar basándose en palabras clave y categorías."""
    failed_keywords = set(self.intent_keywords.get(failed_intent, []))

    category_map = self._build_category_mapping()

    failed_category = category_map.get(failed_intent)
    if not failed_category:
        return None

    candidates = self._find_candidates(failed_category, failed_keywords)

    if candidates:
        return max(candidates, key=lambda x: x[1])[0]

    return None


def _build_category_mapping(self) -> dict:
    return {
        **_map_cocina(),
        **_map_contabilidad(),
        **_map_marketing(),
        **_map_legal(),
        **_map_rrhh(),
        **_map_sistema(),
        **_map_documentos(),
        **_map_comunicacion(),
        **_map_ia(),
        **_map_supervision(),
        **_map_especiales(),
        **_map_orquestacion(),
    }


def _map_cocina() -> dict:
    return {
        "cocina_espanola": "cocina",
        "cocina_navarra": "cocina",
        "cocina_italiana": "cocina",
        "cocina_mexicana": "cocina",
        "cocina_peruana": "cocina",
        "gastronomo_musica": "cocina",
        "orquestador_recetas": "cocina",
        "media_recetas": "cocina",
        "vocabulario_gastronomico": "cocina",
        "vocabulario_bar": "cocina",
        "cocina_internacional": "cocina",
        "recetas_con_media": "cocina",
    }


def _map_contabilidad() -> dict:
    return {
        "administrativo_contable": "contabilidad",
        "contabilidad": "contabilidad",
        "facturas": "contabilidad",
        "banco": "contabilidad",
        "vocabulario_financiero": "contabilidad",
        "contabilidad_agent": "contabilidad",
    }


def _map_marketing() -> dict:
    return {
        "marketing": "marketing",
        "creativo_marketing": "marketing",
        "marketing_navarra": "marketing",
        "galeria_videos": "marketing",
        "galeria_fotos": "marketing",
        "lenguaje_creativo": "marketing",
        "marketing_agent": "marketing",
        "tendencias_pamplona": "marketing",
    }


def _map_legal() -> dict:
    return {
        "juridico": "legal",
        "policia": "legal",
        "vocabulario_legal": "legal",
        "leyes_agent": "legal",
    }


def _map_rrhh() -> dict:
    return {
        "rrhh": "rrhh",
        "laboral": "rrhh",
        "rrhh_camaras": "rrhh",
    }


def _map_sistema() -> dict:
    return {
        "tailscale": "sistema",
        "automatizador": "sistema",
        "automatizacion": "sistema",
        "conectividad": "sistema",
        "red_telefonia": "sistema",
        "hardware": "sistema",
        "scheduler": "sistema",
        "gobierno": "sistema",
        "sistemas": "sistema",
        "red": "sistema",
        "backup": "sistema",
        "seguridad": "sistema",
        "rendimiento": "sistema",
        "instalador": "sistema",
        "camaras": "sistema",
        "arquitectura": "sistema",
        "clasificador": "sistema",
        "registry": "sistema",
        "gui": "sistema",
    }


def _map_documentos() -> dict:
    return {
        "documentos_pdf": "documentos",
        "documentos_texto": "documentos",
        "documentos_word": "documentos",
        "documentos_excel": "documentos",
        "documentos_presentaciones": "documentos",
        "orquestador_documentacion": "documentos",
        "archivist": "documentos",
        "librarian": "documentos",
        "biblioteca": "documentos",
        "bibliotecario_pasillo": "documentos",
    }


def _map_comunicacion() -> dict:
    return {
        "email": "comunicacion",
        "notificaciones": "comunicacion",
        "conversacion": "comunicacion",
        "telegram_dam": "comunicacion",
        "notificador_dam": "comunicacion",
    }


def _map_ia() -> dict:
    return {
        "investigador_ia": "ia",
        "conciencia": "ia",
        "memoria": "ia",
        "lenguaje": "ia",
        "vocabulario": "ia",
        "vocabulario_codigo": "ia",
        "vocabulario_tecnico": "ia",
        "vocabulario_bar": "ia",
        "modelos": "ia",
        "lenguaje_escribiente": "ia",
        "lenguaje_tecnico": "ia",
        "vision": "ia",
        "opencode": "ia",
    }


def _map_supervision() -> dict:
    return {
        "verificador": "supervision",
        "auditor": "supervision",
        "auditor_externo": "supervision",
        "supervisor": "supervision",
        "revisor": "supervision",
        "reparador": "supervision",
        "guardian_residente": "supervision",
    }


def _map_especiales() -> dict:
    return {
        "motor_autorizacion_dual": "especiales",
        "doble_verificacion": "especiales",
        "servidor_validacion": "especiales",
        "asesor": "especiales",
    }


def _map_orquestacion() -> dict:
    return {
        "busqueda": "orquestacion",
        "orquestador_documentacion": "orquestacion",
    }


def _find_candidates(self, failed_category: str, failed_keywords: set) -> list:
    """Buscar agentes de la misma categoría y calcular similitud."""
    candidates = []

    for intent, keywords in self.intent_keywords.items():
        if intent == failed_intent:
            continue

        current_category = self._build_category_mapping().get(intent)
        if current_category != failed_category:
            continue

        current_keywords = set(keywords)
        similarity = len(failed_keywords & current_keywords)

        candidates.append((intent, similarity))

    return candidates


def _get_agent_metadata(self, intent: str, agent_path: str) -> dict:
    """Obtener metadata del agente para feedback más rico."""
    keywords = self.intent_keywords.get(intent, [])

    # Buscar agentes relacionados por palabras clave comunes
    related_agents = []
    for other_intent, other_keywords in self.intent_keywords.items():
        if other_intent != intent:
            common_keywords = set(keywords) & set(other_keywords)
            if len(common_keywords) > 0:
                related_agents.append(
                    {
                        "intent": other_intent,
                        "agent": self.intent_to_agent.get(other_intent),
                        "common_keywords": list(common_keywords),
                    }
                )

    # Ordenar por número de palabras clave comunes y limitar a 3
    related_agents.sort(key=lambda x: len(x["common_keywords"]), reverse=True)
    related_agents = related_agents[:3]

    return {
        "intent": intent,
        "agent_path": agent_path,
        "keywords": keywords,
        "related_agents": related_agents,
        "routing_method": "embedding" if self.embedding_service else "keywords",
    }


def list_agents(self) -> list[dict]:
    """Listar todos los 93 agentes con su estado."""
    agents_list = []

    for intent, agent_path in self.intent_to_agent.items():
        status = "disponible"
        error = None

        try:
            if agent_path == "system":
                status = "sistema"
            else:
                module_path, class_name = agent_path.rsplit(".", 1)
                __import__(module_path)
        except Exception as e:
            status = "no disponible"
            error = str(e)[:50]

        agents_list.append(
            {
                "intent": intent,
                "agent": agent_path,
                "status": status,
                "error": error,
                "keywords": self.intent_keywords.get(intent, []),
            }
        )

    return agents_list


def get_agent_info(self, nombre: str) -> dict:
    """Obtener documentación de un agente específico."""
    if nombre not in self.intent_to_agent:
        return {"error": "Agente no encontrado"}

    agent_path = self.intent_to_agent[nombre]
    keywords = self.intent_keywords.get(nombre, [])

    # Intentar obtener documentación del módulo
    doc = None
    try:
        if agent_path != "system":
            module_path, class_name = agent_path.rsplit(".", 1)
            module = __import__(module_path, fromlist=[class_name])
            agent_class = getattr(module, class_name)
            doc = agent_class.__doc__
    except Exception as e:
        logger.warning(f"Error silencioso en central_router.get_doc: {e}")
        # fallback: continuar

    return {"intent": nombre, "agent": agent_path, "keywords": keywords, "documentation": doc}


def get_status(self) -> dict:
    """Estado del router."""
    return {
        "embedding_service": self.embedding_service is not None,
        "maleta_manager": self.maleta_manager is not None,
        "intents": len(self.intent_keywords),
        "agents": len(self.intent_to_agent),
        "shared_memory_keys": len(self.shared_memory.list_keys()),
        "session_id": self.shared_memory.get_session_id(),
    }


def set_shared_memory(self, key: str, value: Any, agent: str = "system") -> None:
    """Guardar valor en memoria compartida."""
    self.shared_memory.set(key, value, agent)


def get_shared_memory(self, key: str) -> Any | None:
    """Obtener valor de memoria compartida."""
    return self.shared_memory.get(key)


def list_shared_memory(self) -> list[str]:
    """Listar todas las claves en memoria compartida."""
    return self.shared_memory.list_keys()


async def consultar_uram(self, consulta: str, agent: str = "system") -> dict:
    """
    Consultar información a URAM.

    Args:
        consulta: Consulta a realizar a URAM
        agent: Agente que realiza la consulta

    Returns:
        Dict con la respuesta de URAM
    """
    try:
        # Intentar usar el servicio de búsqueda

        orch = SearchOrchestrator()
        result = await orch.search(consulta)

        return {
            "success": True,
            "consulta": consulta,
            "agent": agent,
            "resultados": len(result.results),
            "data": result.results[:5],  # Limitar a 5 resultados
        }
    except Exception as e:
        return {"success": False, "consulta": consulta, "agent": agent, "error": str(e)}


def get_central_router() -> CentralRouter:
    """Obtener instancia singleton del router central."""
    return CentralRouter()


if __name__ == "__main__":

    async def test():
        router = CentralRouter()
        print("Status:", router.get_status())

        tests = [
            "¿Qué software de contabilidad me recomiendas?",
            "Dame una receta de ajoarriero",
            "¿Qué normativa de ruido hay en Pamplona?",
            "Busca información sobre inteligencia artificial",
            "Hola, ¿qué tal estás?",
        ]

        for t in tests:
            result = await router.process_request(t)
            print(f"Query: {t}")
            print(
                f"  Intención: {result['intent']} | Agente: {result['agent']} | Confianza: {result['confidence']:.2f}"
            )
            print(f"  Respuesta: {result['response'][:120]}...")
            print()

    asyncio.run(test())


# ─── DATOS DE INTENCIONES (extraídos del __init__) ──────────────────


def _build_intent_keywords():
    return {
        "cocina_espanola": [
            "cocina española",
            "receta española",
            "paella",
            "tortilla de patatas",
            "cocido",
            "gazpacho",
            "fabada",
            "pulpo a la gallega",
            "jamón",
            "receta de lentejas",
            "receta lentejas",
            "lentejas",
            "lentejas estofadas",
            "lentejas con chorizo",
            "garbanzos",
            "potaje",
            "estofado",
            "callos",
            "cordero asado",
            "receta de",
        ],
        "cocina_navarra": ["navarra", "temporada navarra", "menestra", "pochas", "ajoarriero"],
        "cocina_italiana": ["receta italiana", "pasta", "pizza", "risotto", "lasaña", "italiana"],
        "cocina_mexicana": [
            "receta mexicana",
            "tacos",
            "burritos",
            "nachos",
            "guacamole",
            "mexicana",
        ],
        "cocina_peruana": [
            "cocina peruana",
            "receta peruana",
            "ceviche",
            "lomo saltado",
            "ají de gallina",
            "causa limeña",
            "anticucho",
            "pollo a la brasa",
            "tiradito",
            "chupe de camarones",
            "rocoto relleno",
            "pachamanca",
            "arroz con pollo peruano",
            "suspiro a la limeña",
            "picarones",
            "comida peruana",
            "plato peruano",
            "gastronomía peruana",
            "pisco sour",
            "chicha morada",
            "peruana",
        ],
        "gastronomo_musica": ["música", "playlist", "sonido", "maridaje", "vino"],
        "orquestador_recetas": ["coordinar recetas", "buscar receta", "planificar menú"],
        "media_recetas": ["video receta", "foto receta", "multimedia"],
        "vocabulario_gastronomico": [
            "vocabulario cocina",
            "técnica culinaria",
            "descripción plato",
        ],
        "vocabulario_bar": ["vocabulario bar", "coctel", "bebida", "hostelería"],
        "cocina_internacional": ["cocina internacional", "receta extranjera"],
        "recetas_con_media": ["receta con foto", "receta con vídeo"],
        # CONTABILIDAD/FINANZAS (6 agentes)
        "administrativo_contable": ["administrativo", "papelería", "ocr"],
        "contabilidad": ["factura", "iva", "irpf", "autónomo", "asiento", "nómina", "hacienda"],
        "facturas": [
            "crear factura",
            "emitir factura",
            "factura para",
            "factura",
            "cobro",
            "cobrar",
            "facturación",
            "factura electrónica",
            "comprobante",
            "recibo",
            "albarán",
            "cuenta de cobro",
            "facturar",
            "emitir recibo",
            "registrar pago",
            "factura rectificativa",
            "factura proforma",
            "factura simplificada",
            "factura completa",
            "descuento factura",
        ],
        "banco": ["banco", "transferencia", "cuenta", "saldo", "extracto"],
        "vocabulario_financiero": ["vocabulario financiero", "término financiero"],
        "contabilidad_agent": ["pgc", "impuesto", "autónomo"],
        # MARKETING (7 agentes)
        "marketing": ["banner", "campaña", "instagram", "publicidad", "facebook"],
        "creativo_marketing": ["crear contenido", "creativo", "diseño", "menú digital"],
        "marketing_navarra": ["marketing navarra", "san fermín", "estacional"],
        "galeria_videos": ["video", "galería video", "reel", "editar vídeo"],
        "galeria_fotos": ["foto", "galería foto", "imagen", "cartel"],
        "lenguaje_creativo": ["copywriting", "eslogan", "texto publicitario"],
        "marketing_agent": ["anuncio", "campaña", "publicación", "red social"],
        # LEGAL (4 agentes)
        "juridico": ["jurídico", "legal", "abogado", "normativa", "consulta jurídica"],
        "policia": ["policía", "denuncia", "validación"],
        "vocabulario_legal": ["vocabulario legal", "término jurídico", "boe", "sentencia"],
        "leyes_agent": ["ley", "normativa", "ordenanza", "pamplona", "navarra", "subvención"],
        # RRHH (3 agentes)
        "rrhh": ["contrato", "empleado", "trabajador", "nómina", "personal"],
        "laboral": [
            "laboral",
            "contrato trabajo",
            "contrato laboral",
            "convenio",
            "seguridad social",
        ],
        "rrhh_camaras": ["cámara seguridad", "videovigilancia", "lopd", "protección datos"],
        # SISTEMA (14 agentes)
        "tailscale": [
            "tailscale",
            "vpn",
            "conectar vpn",
            "red privada",
            "conectar red",
            "conéctame a",
            "red tailscale",
            "túnel",
            "conexión segura",
            "wireguard",
            "tail",
            "scale",
            "conexión remota",
            "acceso remoto",
            "red encriptada",
            "conectar dispositivos",
            "red mesh",
            "conexión punto a punto",
            "proxy inverso",
            "túnel seguro",
            "conectar tailscale",
            "conéctame a tailscale",
            "conectar vpn",
        ],
        "automatizador": ["automatizar", "script", "workflow", "n8n"],
        "automatizacion": ["automatizar ratón", "automatizar teclado", "macro"],
        "conectividad": ["red", "wifi", "conexión", "cloudflare", "túnel", "ip", "vps"],
        "red_telefonia": ["telefonía", "teléfono", "voip", "movistar", "telefónica"],
        "hardware": [
            "hardware",
            "ram usando",
            "ram sistema",
            "cuánta ram",
            "usando el sistema",
            "servidor",
            "cpu",
            "tpv",
            "impresora",
            "caja registradora",
            "ram",
            "memoria",
        ],
        "scheduler": ["programar", "agenda", "cron", "recordatorio", "cita"],
        "gobierno": ["gobierno", "trámite", "servicio público", "sede electrónica"],
        "sistemas": ["sistema", "monitorización", "administración", "servicio"],
        "red": ["red", "monitorizar red", "anomalía", "tráfico"],
        "backup": [
            "haz una copia de seguridad del sistema",
            "copia de seguridad del sistema",
            "copia de seguridad",
            "backup",
            "snapshot",
            "restaurar",
            "haz una copia",
            "hacer backup",
            "restaurar copia",
            "restaurar backup",
            "copia del sistema",
            "backup sistema",
            "respaldo",
            "copia automática",
            "backup automático",
            "copiar datos",
            "guardar copia",
            "crear backup",
            "sincronizar backup",
            "backup incremental",
            "backup completo",
            "restaurar sistema",
            "punto de restauración",
        ],
        "seguridad": [
            "seguridad del sistema",
            "seguridad sistema",
            "seguridad informática",
            "firewall",
            "antivirus",
            "blindaje sistema",
            "blindaje",
            "proteger sistema",
            "auditar seguridad",
            "amenaza",
            "vulnerabilidad",
            "intrusión",
            "ataque",
            "malware",
        ],
        "rendimiento": ["cpu", "ram", "memoria", "rendimiento", "monitorizar recursos"],
        "instalador": ["instalar", "desinstalar", "paquete", "dependencia", "brew", "pip"],
        # DOCUMENTOS (9 agentes)
        "documentos_pdf": ["pdf", "leer pdf", "extraer texto pdf"],
        "documentos_texto": ["texto", "txt", "markdown", "md", "rtf"],
        "documentos_word": ["word", "docx", "documento word", "leer word"],
        "documentos_excel": ["excel", "xlsx", "hoja cálculo", "csv"],
        "documentos_presentaciones": ["presentación", "powerpoint", "pptx", "diapositiva"],
        "orquestador_documentacion": ["documentación", "biblioteca", "coordinar documentos"],
        "archivist": ["archivar", "archivo", "trazabilidad", "control versiones"],
        "librarian": ["biblioteca", "libros", "vocabulario", "semántica"],
        "biblioteca": ["biblioteca", "documentación", "manual", "referencia"],
        "bibliotecario_pasillo": ["índice", "catálogo", "inventario", "código"],
        # COMUNICACIÓN (5 agentes)
        "email": ["email", "correo", "enviar correo", "bandeja", "buzón"],
        "notificaciones": ["notificación", "alerta", "aviso", "push"],
        "conversacion": ["conversación", "saludo", "gracias", "hola", "charlar"],
        "telegram_dam": ["telegram", "autorización", "aprobar", "rechazar"],
        "notificador_dam": ["notificación urgente", "pushover", "twilio", "whatsapp"],
        # IA/CONOCIMIENTO (11 agentes)
        "investigador_ia": [
            "nuevos modelos ia",
            "modelos de ia",
            "inteligencia artificial",
            "investigar ia",
            "investigador ia",
            "investigador de ia",
            "investigador",
            "buscar información ia",
            "tendencia ia",
            "herramienta ia",
            "modelo lenguaje",
            "llm",
            "machine learning",
            "deep learning",
            "red neuronal",
            "transformers",
            "modelo generativo",
            "investigación ia",
            "paper ia",
            "avance ia",
            "descubrimiento ia",
            "modelo multimodal",
            "ia generativa",
        ],
        "conciencia": ["conciencia", "memoria", "autoconocimiento", "awareness"],
        "memoria": ["memoria", "recordar", "almacenar", "recuperar información"],
        "lenguaje": ["lenguaje", "traducir", "procesar lenguaje", "nlp"],
        "vocabulario": ["vocabulario", "palabra", "definición", "sinónimo"],
        "vocabulario_codigo": ["código", "programación", "sintaxis", "api", "función"],
        "vocabulario_tecnico": ["técnico", "informática", "tecnología"],
        "vocabulario_bar": ["vocabulario bar", "hostelería", "restaurante", "cocina profesional"],
        "modelos": ["modelo ollama", "descargar modelo", "listar modelos", "gestionar ia"],
        "lenguaje_escribiente": ["redactar", "escribir", "informe", "documentación"],
        "lenguaje_tecnico": ["documentación técnica", "manual técnico", "especificación"],
        # SUPERVISIÓN (7 agentes)
        "verificador": ["verificar instalación", "comprobar", "validar"],
        "auditor": ["auditoría", "registro", "trazabilidad", "log"],
        "auditor_externo": ["auditar github", "reddit", "noticias", "web externa"],
        "supervisor": ["supervisar", "monitorizar todo", "vigilar"],
        "revisor": ["revisar código", "detectar error", "bug", "fallo"],
        "reparador": ["reparar error", "solucionar", "arreglar", "auto-reparación"],
        "guardian_residente": ["vigilar carpeta", "archivo no autorizado", "intruso"],
        # ESPECIALES (10 agentes)
        "motor_autorizacion_dual": ["autorización doble", "alfa", "omega", "validar"],
        "doble_verificacion": ["2fa", "verificación doble", "faceid", "touchid", "email"],
        "servidor_validacion": ["validación móvil", "dam", "autorización remota"],
        "camaras": ["cámara dahua", "videovigilancia", "cámara ip", "grabar"],
        "asesor": ["asesor", "asesoría", "consejo", "comparar", "recomendar"],
        "tendencias_pamplona": [
            "menú pamplona",
            "bar pamplona",
            "restaurante pamplona",
            "tendencia pamplona",
            "gastronomía pamplona",
            "comer pamplona",
            "pintxos pamplona",
            "san fermín",
            "navarrería",
            "casco viejo pamplona",
            "bar de pintxos",
            "menú del día pamplona",
            "carta pamplona",
            "plato típico pamplona",
            "cocina navarra",
            "restaurante navarro",
            "asador pamplona",
            "sidrería pamplona",
            "taberna pamplona",
            "mercado pamplona",
            "qué menú",
        ],
        "opencode": ["opencode", "deepseek", "código asistido", "programar con ia"],
        "arquitectura": ["diseñar sistema", "arquitectura software", "estructura"],
        "clasificador": ["clasificar intención", "puerta entrada", "enrutar"],
        "registry": ["catálogo", "registro", "mapear", "inventario"],
        # VISIÓN/GUI (2 agentes)
        "vision": ["visión", "imagen", "ocr", "ver pantalla", "captura"],
        "gui": ["gui", "interfaz", "clic", "mover ratón", "escribir teclado"],
        # ORQUESTACIÓN (3 agentes)
        "busqueda": ["buscar", "investigar", "encontrar", "internet", "web"],
        "orquestador_documentacion": ["coordinar documentos", "flujo documental"],
        # EXISTENTES
        "sistema": ["sistema", "estado", "módulo"],
        "explorar": ["explorar", "pantalla", "automatizar"],
    }


def _build_intent_to_agent():
    return build_intents_by_category()


def build_intents_by_category():
    governance = build_governance_intents()
    cocina = build_cocina_intents()
    contabilidad_finanzas = build_contabilidad_finanzas_intents()
    marketing = build_marketing_intents()
    legal = build_legal_intents()
    rrhh = build_rrhh_intents()
    sistema = build_sistema_intents()
    documentos = build_documentos_intents()
    comunicacion = build_comunicacion_intents()
    ia_conocimiento = build_ia_conocimiento_intents()
    supervisión = build_supervisión_intents()
    especiales = build_especiales_intents()
    visión_gui = build_visión_gui_intents()
    orquestación = build_orquestación_intents()
    existentes = build_existentes_intents()

    return {
        **governance,
        **cocina,
        **contabilidad_finanzas,
        **marketing,
        **legal,
        **rrhh,
        **sistema,
        **documentos,
        **comunicacion,
        **ia_conocimiento,
        **supervisión,
        **especiales,
        **visión_gui,
        **orquestación,
        **existentes,
    }


def build_governance_intents():
    return {"introspeccion": "core.agente_maestro.AgenteMaestro"}


def build_cocina_intents():
    return {
        "cocina_espanola": "agents.agente_cocina_espanola.AgenteCocinaEspanola",
        "cocina_navarra": "agents.agente_cocina_navarra_temporada.AgenteCocinaNavarraTemporada",
        "cocina_italiana": "agents.agente_cocina_italiana.AgenteCocinaItaliana",
        "cocina_mexicana": "agents.agente_cocina_mexicana.AgenteCocinaMexicana",
        "cocina_peruana": "agents.agente_cocina_peruana.AgenteCocinaPeruana",
        "gastronomo_musica": "agents.agente_gastronomo_musica.AgenteGastronomoMusica",
        "orquestador_recetas": "agents.agente_orquestador_recetas.AgenteOrquestadorRecetas",
        "media_recetas": "agents.agente_media_recetas.AgenteMediaRecetas",
        "vocabulario_gastronomico": "agents.agente_vocabulario_gastronomico.AgenteVocabularioGastronomico",
        "vocabulario_bar": "agents.agente_vocabulario_bar.AgenteVocabularioBar",
        "cocina_internacional": "agents.cocina_internacional_agent.CocinaInternacionalAgent",
        "recetas_con_media": "agents.recetas_con_media.RecetasConMedia",
    }


def build_contabilidad_finanzas_intents():
    return {
        "administrativo_contable": "agents.agente_administrativo_contable.AgenteAdministrativoContable",
        "contabilidad": "agents.agente_contabilidad.AgenteContabilidad",
        "facturas": "agents.agente_facturas.AgenteFacturas",
        "banco": "agents.agente_banco.AgenteBanco",
        "vocabulario_financiero": "agents.agente_vocabulario_financiero.AgenteVocabularioFinanciero",
        "contabilidad_agent": "agents.contabilidad_agent.ContabilidadAgent",
    }


def build_marketing_intents():
    return {
        "marketing": "agents.agente_marketing.AgenteMarketing",
        "creativo_marketing": "agents.agente_creativo_marketing.AgenteCreativoMarketing",
        "marketing_navarra": "agents.agente_marketing_temporada_navarra.AgenteMarketingTemporadaNavarra",
        "galeria_videos": "agents.agente_galeria_videos.AgenteGaleriaVideos",
        "galeria_fotos": "agents.agente_galeria_fotos.AgenteGaleriaFotos",
        "lenguaje_creativo": "agents.agente_lenguaje_creativo.AgenteLenguajeCreativo",
        "marketing_agent": "agents.marketing_agent.MarketingAgent",
    }


def build_legal_intents():
    return {
        "juridico": "agents.agente_juridico.AgenteJuridico",
        "policia": "agents.agente_policia_v2.AgentePoliciaV2",
        "vocabulario_legal": "agents.agente_vocabulario_legal.AgenteVocabularioLegal",
        "leyes_agent": "agents.leyes_agent.LeyesAgent",
    }


def build_rrhh_intents():
    return {
        "rrhh": "agents.agente_rrhh.AgenteRRHH",
        "laboral": "agents.agente_laboral.AgenteLaboral",
        "rrhh_camaras": "agents.rrhh_camaras_agent.RRHHCamarasAgent",
    }


def build_sistema_intents():
    return {
        "tailscale": "agents.agente_tailscale.AgenteTailscale",
        "automatizador": "agents.agente_automatizador.AgenteAutomatizador",
        "automatizacion": "agents.agente_automatizacion.AgenteAutomatizacion",
        "conectividad": "agents.agente_conectividad.AgenteConectividad",
        "red_telefonia": "agents.agente_red_telefonia.AgenteRedTelefonia",
        "hardware": "agents.agente_operativo_hardware.AgenteOperativoHardware",
        "scheduler": "agents.agente_scheduler.AgenteScheduler",
        "gobierno": "agents.agente_gobierno.AgenteGobierno",
        "sistemas": "agents.agente_sistemas.AgenteSistemas",
        "red": "agents.agente_red.AgenteRed",
        "backup": "agents.agente_backup.AgenteBackup",
        "seguridad": "agents.agente_seguridad.AgenteSeguridad",
        "rendimiento": "agents.agente_rendimiento.AgenteRendimiento",
        "instalador": "agents.agente_instalador.AgenteInstalador",
    }


def build_documentos_intents():
    return {
        "documentos_pdf": "agents.agente_documentos_pdf.AgenteDocumentosPDF",
        "documentos_texto": "agents.agente_documentos_texto.AgenteDocumentosTexto",
        "documentos_word": "agents.agente_documentos_word.AgenteDocumentosWord",
        "documentos_excel": "agents.agente_documentos_excel.AgenteDocumentosExcel",
        "documentos_presentaciones": "agents.agente_documentos_presentaciones.AgenteDocumentosPresentaciones",
        "orquestador_documentacion": "agents.agente_orquestador_documentacion.AgenteOrquestadorDocumentacion",
        "archivist": "agents.agente_archivist.AgenteArchivist",
        "librarian": "agents.agente_librarian.AgenteLibrarian",
        "biblioteca": "agents.agente_biblioteca.AgenteBiblioteca",
        "bibliotecario_pasillo": "agents.bibliotecario_pasillo.BibliotecarioPasillo",
    }


def build_comunicacion_intents():
    return {
        "email": "agents.agente_email.AgenteEmail",
        "notificaciones": "agents.agente_notificaciones.AgenteNotificaciones",
        "conversacion": "agents.agente_conversacion.AgenteConversacion",
        "telegram_dam": "agents.agente_telegram_dam.AgenteTelegramDAM",
        "notificador_dam": "agents.notificador_dam.NotificadorDAM",
    }


def build_ia_conocimiento_intents():
    return {
        "investigador_ia": "agents.agente_investigador_ia.AgenteInvestigadorIA",
        "conciencia": "agents.agente_conciencia.AgenteConciencia",
        "memoria": "agents.agente_memoria.AgenteMemoria",
        "lenguaje": "agents.agente_lenguaje.AgenteLenguaje",
        "vocabulario": "agents.agente_vocabulario.AgenteVocabulario",
        "vocabulario_codigo": "agents.agente_vocabulario_codigo.AgenteVocabularioCodigo",
        "vocabulario_tecnico": "agents.agente_vocabulario_tecnico.AgenteVocabularioTecnico",
        "vocabulario_bar": "agents.agente_vocabulario_bar.AgenteVocabularioBar",
        "modelos": "agents.agente_modelos.AgenteModelos",
        "lenguaje_escribiente": "agents.agente_lenguaje_escribiente.AgenteLenguajeEscribiente",
        "lenguaje_tecnico": "agents.agente_lenguaje_tecnico.AgenteLenguajeTecnico",
    }


def build_supervisión_intents():
    return {
        "verificador": "agents.agente_verificador.AgenteVerificador",
        "auditor": "agents.agente_auditor.AgenteAuditor",
        "auditor_externo": "agents.agente_auditor_externo.AgenteAuditorExterno",
        "supervisor": "agents.agente_supervisor.AgenteSupervisor",
        "revisor": "agents.agente_revisor.AgenteRevisor",
        "reparador": "agents.agente_reparador.AgenteReparador",
        "guardian_residente": "agents.guardian_residente.GuardianResidente",
    }


def build_especiales_intents():
    return {
        "motor_autorizacion_dual": "agents.motor_autorizacion_dual.MotorAutorizacionDual",
        "doble_verificacion": "agents.doble_verificacion.DobleVerificacion",
        "servidor_validacion": "agents.servidor_validacion.ServidorValidacion",
        "camaras": "agents.agente_camaras.AgenteCamaras",
        "asesor": "agents.agente_asesor.AgenteAsesor",
        "tendencias_pamplona": "agents.agente_tendencias_pamplona.AgenteTendenciasPamplona",
        "opencode": "agents.agente_opencode.AgenteOpenCode",
        "arquitectura": "agents.agente_arquitectura.AgenteArquitectura",
        "clasificador": "agents.clasificador.Clasificador",
        "registry": "agents.registry.Registry",
    }


def build_visión_gui_intents():
    return {"vision": "agents.agente_vision.AgenteVision", "gui": "agents.agente_gui.GUIAgent"}


def build_orquestación_intents():
    return {
        "busqueda": "core.buscadores.orchestrator.SearchOrchestrator",
        "orquestador_documentacion": "agents.agente_orquestador_documentacion.AgenteOrquestadorDocumentacion",
    }


def build_existentes_intents():
    return {"sistema": "system", "explorar": "core.explorador_sistemico.ExploradorSistemico"}
