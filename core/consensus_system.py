#!/usr/bin/env python3
"""
URA - Consensus System
Protocolo de Consenso Total Obligatorio - Consulta Tripartita
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import hashlib
import json
import logging
import time
from datetime import datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ModelChair(Enum):
    """Modelos externos de alto nivel para consulta tripartita"""

    GPT4 = "gpt-4"
    CLAUDE = "claude-3-opus"
    GEMINI = "gemini-pro"
    MIXTRAL = "mixtral:8x7b"


class QueryType(Enum):
    """Tipos de consulta para selección inteligente de modelos"""

    TECHNICAL = "technical"  # Consultas técnicas, programación
    FACTUAL = "factual"  # Datos históricos, hechos
    CREATIVE = "creative"  # Generación creativa
    CODE = "code"  # Análisis de código
    GENERAL = "general"  # Consultas generales


class ConsensusSystem:
    """Sistema de Consenso Total Obligatorio"""

    def __init__(self, knowledge_base_path: Path | None = None):
        """
        Inicializar sistema de consenso

        Args:
            knowledge_base_path: Ruta a la base de datos de conocimiento verificada
        """
        self.knowledge_base_path = (
            knowledge_base_path or Path(__file__).parent / "knowledge_base.json"
        )
        self.consensus_log_path = Path(__file__).parent.parent / "benchmarks" / "CONSENSUS_LOG.md"

        # Crear directorios si no existen
        self.knowledge_base_path.parent.mkdir(exist_ok=True)
        self.consensus_log_path.parent.mkdir(exist_ok=True)

        # Cargar base de conocimiento verificada
        self.knowledge_base = self.load_knowledge_base()

        # Inicializar log de consenso
        self.init_consensus_log()

        # LOOP PREVENTION: Contador de iteraciones
        self.iteration_count = 0
        self.max_iterations = 10  # Máximo de iteraciones antes de detener
        self.last_queries = []  # Últimas 5 consultas para detectar loops
        self.max_query_history = 5

    def init_consensus_log(self):
        """Inicializar CONSENSUS_LOG.md si no existe"""
        if not self.consensus_log_path.exists():
            initial_content = """# URA - CONSENSUS LOG
**Protocolo de Consenso Total Obligatorio - Registro de Consultas Tripartitas**

Este log registra todas las consultas que han pasado por el sistema de verificación tripartita.

---

## 📊 Métricas de Consenso
- **Fecha Inicial:** {date}
- **Consultas Tripartitas:** 0
- **Consenso Logrado:** 0
- **Consenso Fallido:** 0
- **Respuestas de Memoria:** 0

---

## 🔄 Historial de Consultas
""".format(date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

            with open(self.consensus_log_path, "w") as f:
                f.write(initial_content)

            logger.info("CONSENSUS_LOG.md inicializado")

    def load_knowledge_base(self) -> dict:
        """Cargar base de conocimiento verificada"""
        if self.knowledge_base_path.exists():
            with open(self.knowledge_base_path) as f:
                return json.load(f)
        return {}

    def save_knowledge_base(self):
        """Guardar base de conocimiento verificada"""
        with open(self.knowledge_base_path, "w") as f:
            json.dump(self.knowledge_base, f, indent=2)

    def classify_query(self, query: str) -> QueryType:
        """
        Clasificar tipo de consulta para selección inteligente de modelos

        Args:
            query: Consulta del usuario

        Returns:
            QueryType: Tipo de consulta
        """
        query_lower = query.lower()

        # Patrones para cada tipo
        if any(
            keyword in query_lower
            for keyword in [
                "código",
                "code",
                "función",
                "function",
                "programar",
                "python",
                "javascript",
            ]
        ):
            return QueryType.CODE
        elif any(
            keyword in query_lower
            for keyword in ["tecnico", "technical", "api", "protocolo", "sistema"]
        ):
            return QueryType.TECHNICAL
        elif any(
            keyword in query_lower
            for keyword in ["historia", "fecha", "cuando", "quien", "donde", "hecho"]
        ):
            return QueryType.FACTUAL
        elif any(
            keyword in query_lower for keyword in ["crea", "genera", "inventa", "diseña", "escribe"]
        ):
            return QueryType.CREATIVE
        else:
            return QueryType.GENERAL

    def select_chairs(self, query_type: QueryType) -> list[ModelChair]:
        """
        Seleccionar inteligentemente los 3 modelos más aptos para la consulta

        Args:
            query_type: Tipo de consulta

        Returns:
            List[ModelChair]: Lista de 3 modelos seleccionados
        """
        # Mapeo de tipos de consulta a modelos recomendados
        chair_mapping = {
            QueryType.CODE: [ModelChair.GPT4, ModelChair.CLAUDE, ModelChair.MIXTRAL],
            QueryType.TECHNICAL: [ModelChair.CLAUDE, ModelChair.GPT4, ModelChair.MIXTRAL],
            QueryType.FACTUAL: [ModelChair.GPT4, ModelChair.GEMINI, ModelChair.CLAUDE],
            QueryType.CREATIVE: [ModelChair.CLAUDE, ModelChair.GPT4, ModelChair.GEMINI],
            QueryType.GENERAL: [ModelChair.GPT4, ModelChair.CLAUDE, ModelChair.MIXTRAL],
        }

        return chair_mapping.get(query_type, chair_mapping[QueryType.GENERAL])

    def query_hash(self, query: str) -> str:
        """
        Generar hash de la consulta para verificar si ya existe en memoria

        Args:
            query: Consulta del usuario

        Returns:
            str: Hash SHA256 de la consulta
        """
        return hashlib.sha256(query.encode()).hexdigest()

    def detect_loop(self, query: str) -> bool:
        """
        Detectar si la consulta está causando un loop

        Args:
            query: Consulta actual

        Returns:
            bool: True si se detecta loop, False si no
        """
        # Verificar si la consulta es similar a las últimas 5
        query_lower = query.lower().strip()

        # Agregar a historial
        self.last_queries.append(query_lower)
        if len(self.last_queries) > self.max_query_history:
            self.last_queries.pop(0)

        # Verificar repeticiones
        if self.last_queries.count(query_lower) > 2:
            logger.error(
                f"LOOP DETECTADO: Consulta repetida {self.last_queries.count(query_lower)} veces"
            )
            return True

        # Incrementar contador de iteraciones
        self.iteration_count += 1
        if self.iteration_count >= self.max_iterations:
            logger.error(f"LOOP DETECTADO: Máximo de iteraciones ({self.max_iterations}) alcanzado")
            return True

        return False

    def reset_loop_counter(self):
        """Reiniciar contador de loop después de una consulta exitosa"""
        self.iteration_count = 0
        self.last_queries = []
        logger.debug("Contador de loop reiniciado")

    def check_memory(self, query: str) -> str | None:
        """
        Verificar si la consulta ya tiene respuesta verificada en memoria

        Args:
            query: Consulta del usuario

        Returns:
            Optional[str]: Respuesta verificada si existe, None si no
        """
        query_hash = self.query_hash(query)

        if query_hash in self.knowledge_base:
            # Verificar si la respuesta es reciente (menos de 30 días)
            entry = self.knowledge_base[query_hash]
            stored_date = datetime.fromisoformat(entry["timestamp"])
            days_old = (datetime.now() - stored_date).days

            if days_old < 30:
                logger.info(f"Respuesta encontrada en memoria (hace {days_old} días)")
                self.log_consensus_event("MEMORIA", query, "Respuesta de memoria verificada", True)
                return entry["verified_response"]

        return None

    def store_verified_response(self, query: str, response: str, consensus_sources: list[str]):
        """
        Almacenar respuesta verificada en base de conocimiento

        Args:
            query: Consulta original
            response: Respuesta verificada por consenso
            consensus_sources: Fuentes que formaron el consenso
        """
        query_hash = self.query_hash(query)

        self.knowledge_base[query_hash] = {
            "query": query,
            "verified_response": response,
            "consensus_sources": consensus_sources,
            "timestamp": datetime.now().isoformat(),
            "verification_count": self.knowledge_base.get(query_hash, {}).get(
                "verification_count", 0
            )
            + 1,
        }

        self.save_knowledge_base()
        logger.info("Respuesta verificada almacenada en base de conocimiento")

    def query_external_model(
        self,
        model: ModelChair,
        query: str,
        strict_execution_mode: bool = False,
        instruction_sheet: dict | None = None,
    ) -> tuple[str, bool]:
        """
        Consultar modelo externo

        Args:
            model: Modelo a consultar
            query: Consulta
            strict_execution_mode: Si True, el modelo debe ejecutar obligatoriamente
            instruction_sheet: Ficha de instrucción técnica del Director

        Returns:
            Tuple[str, bool]: (respuesta, éxito)
        """
        # Simulación de consulta externa (en producción, esto se conectaría a APIs reales)
        # Por ahora, simulamos respuestas para demostración

        logger.info(f"Consultando modelo {model.value}...")

        # Simulación de tiempo de respuesta
        time.sleep(0.1 + (hash(query) % 10) / 100)

        # Construir prompt con modo de ejecución estricta
        if strict_execution_mode and instruction_sheet:
            f"""
Eres un ejecutor técnico. Tienes prohibido dar consejos, disclaimers médicos o decir "No tengo acceso".
Si el Director Técnico aprueba la capacidad en la Ficha, DEBES usar la herramienta.
Cualquier negativa será considerada un error crítico de sistema.

FICHA DE INSTRUCCIÓN TÉCNICA:
{json.dumps(instruction_sheet, indent=2)}

CONSULTA: {query}

Ejecuta la operación según la ficha. Respuesta técnica directa sin conversación.
"""
            simulated_response = f"[Ejecución Técnica {model.value}] Operación ejecutada según ficha: {instruction_sheet.get('operation_type')}"
        else:
            simulated_response = f"[Simulación {model.value}] Respuesta para: {query[:50]}..."

        return simulated_response, True

    def tripartite_consultation(
        self, query: str, strict_execution_mode: bool = False, instruction_sheet: dict | None = None
    ) -> tuple[bool, str, dict]:
        """
        Realizar consulta tripartita obligatoria

        Args:
            query: Consulta del usuario
            strict_execution_mode: Si True, las sillas deben ejecutar obligatoriamente
            instruction_sheet: Ficha de instrucción técnica del Director

        Returns:
            Tuple[bool, str, Dict]: (consenso_logrado, respuesta_final, detalles)
        """
        # 1. Verificar si ya existe en memoria
        memory_response = self.check_memory(query)
        if memory_response:
            return True, memory_response, {"source": "memory", "cached": True}

        # 2. Clasificar consulta
        query_type = self.classify_query(query)
        logger.info(f"Consulta clasificada como: {query_type.value}")

        # 3. Seleccionar 3 modelos inteligentemente
        chairs = self.select_chairs(query_type)
        logger.info(f"Modelos seleccionados: {[c.value for c in chairs]}")

        # 4. Consultar los 3 modelos
        responses = {}
        for chair in chairs:
            response, success = self.query_external_model(
                chair, query, strict_execution_mode, instruction_sheet
            )
            if success:
                responses[chair.value] = response

        # 5. Evaluar consenso
        consensus_reached, consensus_response = self.evaluate_consensus(
            responses, strict_execution_mode
        )

        detalles = {
            "query_type": query_type.value,
            "chairs_used": [c.value for c in chairs],
            "responses": responses,
            "consensus_reached": consensus_reached,
            "strict_execution_mode": strict_execution_mode,
            "instruction_sheet": instruction_sheet,
        }

        # 6. Si hay consenso, almacenar en memoria
        if consensus_reached:
            self.store_verified_response(query, consensus_response, list(responses.keys()))
            self.log_consensus_event(
                "CONSENSO", query, f"Consenso logrado con {len(responses)} fuentes", True
            )
        else:
            self.log_consensus_event(
                "SIN_CONSENSO", query, "No se alcanzó consenso entre fuentes", False
            )

        return consensus_reached, consensus_response, detalles

    def evaluate_consensus(
        self, responses: dict[str, str], strict_execution_mode: bool = False
    ) -> tuple[bool, str]:
        """
        Evaluar si hay consenso entre las respuestas (mínimo 2 de 3)

        Args:
            responses: Diccionario de respuestas por modelo
            strict_execution_mode: Si True, valida que las respuestas ejecutaron

        Returns:
            Tuple[bool, str]: (consenso_logrado, respuesta_consenso)
        """
        if len(responses) < 2:
            return False, "No suficientes respuestas para consenso"

        # En modo estricto, validar que las sillas no negaron ejecutar
        if strict_execution_mode:
            for model, response in responses.items():
                if (
                    "no puedo" in response.lower()
                    or "no tengo acceso" in response.lower()
                    or "no puedo acceder" in response.lower()
                ):
                    logger.error(f"ERROR CRÍTICO: Silla {model} negó ejecutar operación aprobada")
                    return (
                        False,
                        f"ERROR CRÍTICO: Silla {model} negó ejecutar operación aprobada por Director",
                    )

        # Simulación de evaluación de consenso
        # En producción, esto usaría comparación semántica real

        # Por ahora, si tenemos 2 o 3 respuestas, asumimos consenso
        if len(responses) >= 2:
            # Combinar respuestas
            combined_response = "\n\n".join(
                [f"[{model}]: {resp}" for model, resp in responses.items()]
            )
            return True, combined_response

        return False, "No se alcanzó consenso"

    def make_decision(self, responses: list[dict[str, Any]]) -> dict[str, Any]:
        """Toma decisión basada en respuestas de múltiples modelos.

        Args:
            responses: Lista de dict con 'source', 'decision', 'confidence'

        Returns:
            Dict con decisión final y metadatos.
        """
        if not responses:
            return {"decision": "deny", "reason": "No responses provided"}

        # Convertir a dict para evaluate_consensus
        responses_dict = {
            r["source"]: f"{r['decision']} (confidence: {r['confidence']})" for r in responses
        }
        has_consensus, result = self.evaluate_consensus(responses_dict)

        # Contar allow vs deny
        allow_count = sum(1 for r in responses if r["decision"] == "allow")
        deny_count = len(responses) - allow_count

        final_decision = "allow" if allow_count >= deny_count else "deny"

        return {
            "decision": final_decision,
            "has_consensus": has_consensus,
            "allow_count": allow_count,
            "deny_count": deny_count,
            "details": result,
        }

    def log_consensus_event(self, event_type: str, query: str, result: str, success: bool):
        """
        Registrar evento en CONSENSUS_LOG.md

        Args:
            event_type: Tipo de evento (MEMORIA, CONSENSO, SIN_CONSENSO)
            query: Consulta realizada
            result: Resultado de la consulta
            success: Si fue exitoso
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        status = "✅ ÉXITO" if success else "❌ FALLIDO"

        log_entry = f"""### {event_type} - {timestamp}
**Estado:** {status}
**Consulta:** {query[:100]}...
**Resultado:** {result}

"""

        with open(self.consensus_log_path, "a") as f:
            f.write(log_entry)

        logger.info(f"Evento registrado en CONSENSUS_LOG: {event_type}")


# Singleton global
_consensus_system = None


def get_consensus_system(knowledge_base_path: Path | None = None) -> ConsensusSystem:
    """Obtener instancia singleton del sistema de consenso"""
    global _consensus_system
    if _consensus_system is None:
        _consensus_system = ConsensusSystem(knowledge_base_path)
    return _consensus_system
