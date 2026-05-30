#!/usr/bin/env python3
"""
URA ReAct Engine - Motor de Razonamiento ReAct
Implementa el patrón ReAct (Reasoning + Acting) para toma de decisiones autónoma.
Permite a URA razonar antes de actuar, reduciendo alucinaciones.

Patrón: Thought → Action → Observation
"""

import concurrent.futures
import logging
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any

from core.observability import trace_step

logger = logging.getLogger(__name__)

# Importar sistema de persistencia de memoria
try:
    from memory_persistence import get_memory_persistence

    MEMORY_PERSISTENCE_AVAILABLE = True
except ImportError:
    MEMORY_PERSISTENCE_AVAILABLE = False
    logger.warning("Memory persistence no disponible")


class ActionType(Enum):
    """Tipos de acciones que puede ejecutar el ReAct engine"""

    ANALYZE = "analyze"
    RETRIEVE = "retrieve"
    EXECUTE = "execute"
    COMMUNICATE = "communicate"
    MONITOR = "monitor"


@dataclass
class Step:
    """Un paso en el proceso de razonamiento ReAct"""

    step_id: int
    thought: str
    action: ActionType
    action_input: dict[str, Any]
    observation: str | None = None
    completed: bool = False


@dataclass
class Tool:
    """Herramienta que puede usar el ReAct engine"""

    name: str
    description: str
    function: Callable
    parameters: dict[str, Any]


class ReActEngine:
    """
    Motor de razonamiento ReAct que orquesta el patrón Thought → Action → Observation.
    """

    def __init__(self, max_steps: int = 10, verbose: bool = False, async_execution: bool = True):
        self.max_steps = max_steps
        self.verbose = verbose
        self.tools: dict[str, Tool] = {}
        self.steps: list[Step] = []
        self.current_step = 0
        self.async_execution = async_execution
        self.executor = (
            concurrent.futures.ThreadPoolExecutor(max_workers=4) if async_execution else None
        )

        # Sistema de persistencia de memoria
        self.memory_persistence = None
        if MEMORY_PERSISTENCE_AVAILABLE:
            try:
                self.memory_persistence = get_memory_persistence()
                logger.info("Memory persistence activado en ReAct engine")
            except Exception as e:
                logger.error(f"Error iniciando memory persistence: {e}")

    def register_tool(self, name: str, function: Callable):
        """Registra una herramienta disponible para el engine"""
        self.tools[name] = Tool(
            name=name, description=f"Tool: {name}", function=function, parameters={}
        )
        logger.info(f"Tool registered: {name}")

    def get_tool(self, name: str) -> Tool | None:
        """Obtiene una herramienta por nombre"""
        return self.tools.get(name)

    def list_tools(self) -> list[str]:
        """Lista todas las herramientas disponibles"""
        return list(self.tools.keys())

    @trace_step
    def think(self, context: str, query: str) -> dict[str, Any]:
        """
        Genera un thought basado en el contexto y la query.
        En una implementación real, esto usaría un LLM para generar el thought.
        """
        # Simplificado: en producción esto usaría Ollama
        thought = f"Analyzing query: {query}. Context: {context[:100]}..."
        logger.info(f"Thought: {thought}")
        return {"thought": thought, "response": thought, "action": None}

    @trace_step
    def select_action(
        self, thought: str, available_tools: list[str]
    ) -> tuple[ActionType, dict[str, Any]]:
        """
        Selecciona la acción apropiada basada en el thought.
        En una implementación real, esto usaría un LLM.
        """
        # Simplificado: en producción esto usaría Ollama
        if "analyze" in thought.lower():
            return ActionType.ANALYZE, {"query": thought}
        elif "retrieve" in thought.lower() or "memory" in thought.lower():
            return ActionType.RETRIEVE, {"query": thought}
        elif "execute" in thought.lower():
            return ActionType.EXECUTE, {"command": thought}
        elif "communicate" in thought.lower() or "send" in thought.lower():
            return ActionType.COMMUNICATE, {"message": thought}
        else:
            return ActionType.MONITOR, {"check": thought}

    @trace_step
    def execute_action(
        self, action: ActionType, action_input: dict[str, Any], timeout: float = 5.0
    ) -> str:
        """
        Ejecuta la acción seleccionada con soporte para timeout.

        Args:
            action: Tipo de acción a ejecutar
            action_input: Parámetros de la acción
            timeout: Tiempo máximo para ejecución (segundos)

        Returns:
            Resultado de la acción o mensaje de timeout
        """
        if not self.async_execution:
            # Ejecución síncrona (comportamiento original)
            return self._execute_sync(action, action_input)

        # Ejecución asíncrona con timeout
        try:
            future = self.executor.submit(self._execute_sync, action, action_input)
            result = future.result(timeout=timeout)
            return result
        except concurrent.futures.TimeoutError:
            logger.warning(f"Timeout en ejecución de acción {action.value} después de {timeout}s")
            return f"Timeout: La acción {action.value} excedió el tiempo límite de {timeout}s"
        except Exception as e:
            logger.error(f"Error en ejecución asíncrona: {str(e)}")
            return f"Error: {str(e)}"

    def _execute_sync(self, action: ActionType, action_input: dict[str, Any]) -> str:
        """
        Ejecuta la acción seleccionada de forma síncrona.
        """
        if action == ActionType.ANALYZE:
            return f"Analyzed: {action_input.get('query', '')}"
        elif action == ActionType.RETRIEVE:
            return f"Retrieved: {action_input.get('query', '')}"
        elif action == ActionType.EXECUTE:
            return f"Executed: {action_input.get('command', '')}"
        elif action == ActionType.COMMUNICATE:
            return f"Communicated: {action_input.get('message', '')}"
        elif action == ActionType.MONITOR:
            return f"Monitored: {action_input.get('check', '')}"
        else:
            return "Unknown action"

    def observe(self, action_result: str) -> str:
        """
        Genera una observación basada en el resultado de la acción.
        """
        observation = f"Observation: {action_result}"
        logger.info(f"Observation: {observation}")
        return observation

    @trace_step
    def run(self, context: str, query: str) -> list[Step]:
        """
        Ejecuta el ciclo completo de ReAct: Thought → Action → Observation
        """
        logger.info(f"Starting ReAct engine for query: {query}")
        self.steps = []
        self.current_step = 0

        while self.current_step < self.max_steps:
            # Step 1: Thought
            thought = self.think(context, query)

            # Step 2: Select Action
            available_tools = self.list_tools()
            action, action_input = self.select_action(thought, available_tools)

            # Step 3: Execute Action
            action_result = self.execute_action(action, action_input)

            # Step 4: Observe
            observation = self.observe(action_result)

            # Create step
            step = Step(
                step_id=self.current_step + 1,
                thought=thought,
                action=action,
                action_input=action_input,
                observation=observation,
                completed=True,
            )
            self.steps.append(step)

            if self.verbose:
                logger.info(f"Step {step.step_id}: {thought} → {action.value} → {observation}")

            self.current_step += 1

            # Check if we should stop (simplified)
            if "completed" in observation.lower() or "done" in observation.lower():
                break

        logger.info(f"ReAct engine completed with {len(self.steps)} steps")
        return self.steps

    def get_summary(self) -> str:
        """Obtiene un resumen de la ejecución"""
        summary = "ReAct Engine Summary:\n"
        summary += f"Total steps: {len(self.steps)}\n"
        summary += f"Tools available: {len(self.tools)}\n"
        for i, step in enumerate(self.steps, 1):
            summary += f"\nStep {i}:\n"
            summary += f"  Thought: {step.thought}\n"
            summary += f"  Action: {step.action.value}\n"
            summary += f"  Observation: {step.observation}\n"
        return summary

    def reset(self):
        """Resetea el estado del engine"""
        self.steps = []
        self.current_step = 0
        logger.info("ReAct engine reset")

    def shutdown(self):
        """Cierra el executor de hilos"""
        if self.executor:
            self.executor.shutdown(wait=True)
            logger.info("ReAct engine executor cerrado")

    def add_memory(self, content: str, metadata: dict[str, Any] | None = None) -> str:
        """
        Añade una memoria al sistema de persistencia

        Args:
            content: Contenido de la memoria
            metadata: Metadatos opcionales

        Returns:
            ID de la memoria creada
        """
        if self.memory_persistence is None:
            logger.warning("Memory persistence no disponible, no se guardará la memoria")
            return None

        import uuid

        memory_id = f"mem_{uuid.uuid4().hex[:8]}"

        self.memory_persistence.add_memory(
            memory_id=memory_id, content=content, metadata=metadata or {}
        )

        return memory_id

    def load_memories(self) -> list[dict[str, Any]]:
        """
        Carga todas las memorias persistidas

        Returns:
            Lista de memorias cargadas
        """
        if self.memory_persistence is None:
            logger.warning("Memory persistence no disponible")
            return []

        return self.memory_persistence.get_all_memories()


# Singleton instance
_react_engine_instance = None


def get_react_engine(max_steps: int = 10, verbose: bool = False) -> ReActEngine:
    """Obtiene la instancia singleton del ReAct engine"""
    global _react_engine_instance
    if _react_engine_instance is None:
        _react_engine_instance = ReActEngine(max_steps=max_steps, verbose=verbose)
    return _react_engine_instance


if __name__ == "__main__":
    # Test básico
    engine = ReActEngine(verbose=True)

    # Registrar herramientas de prueba
    def dummy_tool(input_data):
        return f"Tool executed with: {input_data}"

    engine.register_tool(
        Tool(
            name="dummy",
            description="Dummy tool for testing",
            function=dummy_tool,
            parameters={"input": "string"},
        )
    )

    # Ejecutar
    context = "URA system context"
    query = "Test query for ReAct engine"
    steps = engine.run(context, query)

    print(engine.get_summary())
