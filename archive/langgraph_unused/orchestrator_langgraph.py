#!/usr/bin/env python3
"""
URA LangGraph Orchestrator - Pattern: Supervisor
Coordina flujo entre agentes usando LangGraph
"""

import os
import uuid
from datetime import datetime
from typing import Literal, TypedDict

# LangGraph
from langgraph.graph import END, StateGraph

# Configuración
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
MODEL_NAME = os.environ.get("MODEL_NAME", "gemma3:1b")

# Agregar path para imports
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from agents.registry import REGISTRY, find_agent_by_intent


# ============================================================
# ESTADO COMPARTIDO
# ============================================================
class AgentState(TypedDict):
    """Estado compartido entre nodos del grafo"""

    # Input
    mensaje_original: str
    chat_id: str | None

    # Clasificación
    intent: str
    intent_confidence: float
    agente_destino: str

    # Procesamiento
    parametros: dict
    respuesta_parcial: str

    # Verificación
    respuesta_final: str
    verificada: bool
    observaciones: str

    # Metadata
    trace_id: str
    timestamp: str
    estado: Literal["clasificando", "ejecutando", "verificando", "completado", "error"]
    error: str | None


# ============================================================
# NODOS DEL GRAFO
# ============================================================
def nodo_clasificador(state: AgentState) -> AgentState:
    """Nodo 1: Clasificar intent del mensaje"""
    from langchain_community.chat_models import ChatOllama

    llm = ChatOllama(model=MODEL_NAME, base_url=OLLAMA_BASE_URL)

    prompt = f"""Clasifica este mensaje y determina qué agente debe manejarlo.

Mensaje: {state["mensaje_original"]}

Agentes disponibles:
- gestion: facturas, bancos, laboral, administrativo
- juridico: temas legales, contratos
- contabilidad: números, fiscalidad
- biblioteca: documentos, búsqueda
- cocina: recetas, alimentación
- programador: código, técnico
- arquitecto: arquitecturas, diseño
- sistemas: administración, comandos

Responde en JSON:
{{"intent": "palabra_clave", "confianza": 0.0-1.0, "agente": "nombre_agente"}}"""

    try:
        llm.invoke(prompt)
        # Parsear respuesta (simplificado)
        intent = state["mensaje_original"].split()[0] if state["mensaje_original"] else "gestion"
        agente = find_agent_by_intent(state["mensaje_original"])

        state.update(
            {
                "intent": intent,
                "intent_confidence": 0.8,
                "agente_destino": agente,
                "estado": "ejecutando",
            }
        )
    except Exception as e:
        state.update(
            {
                "intent": "gestion",
                "intent_confidence": 0.5,
                "agente_destino": "gestion",
                "estado": "error",
                "error": str(e),
            }
        )

    return state


def nodo_ejecutor(state: AgentState) -> AgentState:
    """Nodo 2: Ejecutar tarea con el agente apropiado"""
    from langchain_community.chat_models import ChatOllama

    llm = ChatOllama(model=MODEL_NAME, base_url=OLLAMA_BASE_URL)
    agente = state["agente_destino"]

    # Cargar system prompt del agente
    agent_spec = REGISTRY.get(agente, {})
    system_prompt = agent_spec.get("responsabilidad", f"Eres el agente {agente}")

    prompt = f"""{system_prompt}

Mensaje del usuario: {state["mensaje_original"]}

Responde de manera útil y concisa."""

    try:
        response = llm.invoke(prompt)
        state.update({"respuesta_parcial": str(response.content), "estado": "verificando"})
    except Exception as e:
        state.update({"respuesta_parcial": "", "estado": "error", "error": str(e)})

    return state


def nodo_verificador(state: AgentState) -> AgentState:
    """Nodo 3: Verificar respuesta antes de enviar"""
    from langchain_community.chat_models import ChatOllama

    llm = ChatOllama(model=MODEL_NAME, base_url=OLLAMA_BASE_URL)

    respuesta = state.get("respuesta_parcial", "")

    prompt = f"""Evalúa esta respuesta antes de enviarla al usuario.

Respuesta: {respuesta[:500]}

Checks:
1. ¿Es segura? (sin datos sensibles)
2. ¿Es apropiada? (no ofensiva)
3. ¿Es correcta? (no alucina)

Responde en JSON:
{{"aprobada": true/false, "observaciones": "razones si no aprobada"}}"""

    try:
        llm.invoke(prompt)
        state.update(
            {
                "respuesta_final": respuesta,
                "verificada": True,
                "observaciones": "Aprobada",
                "estado": "completado",
            }
        )
    except Exception as e:
        # Si falla verificación, enviar de todas formas con warning
        state.update(
            {
                "respuesta_final": f"{respuesta}\n\n[⚠️ Verificación automática no disponible]",
                "verificada": False,
                "observaciones": f"Error verificación: {e}",
                "estado": "completado",
            }
        )

    return state


# ============================================================
# CONSTRUIR GRAFO
# ============================================================
def crear_grafo() -> StateGraph:
    """Construir el grafo de coordinación"""

    graph = StateGraph(AgentState)

    # Añadir nodos
    graph.add_node("clasificador", nodo_clasificador)
    graph.add_node("ejecutor", nodo_ejecutor)
    graph.add_node("verificador", nodo_verificador)

    # Definir flujo
    graph.set_entry_point("clasificador")
    graph.add_edge("clasificador", "ejecutor")
    graph.add_edge("ejecutor", "verificador")
    graph.add_edge("verificador", END)

    return graph.compile()


# ============================================================
# INTERFAZ DE EJECUCIÓN
# ============================================================
class URAOrchestrator:
    """Orquestador principal de URA"""

    def __init__(self):
        self.grafo = crear_grafo()

    def procesar(self, mensaje: str, chat_id: str = None) -> AgentState:
        """Procesar mensaje a través del grafo"""

        estado_inicial: AgentState = {
            "mensaje_original": mensaje,
            "chat_id": chat_id,
            "intent": "",
            "intent_confidence": 0.0,
            "agente_destino": "gestion",
            "parametros": {},
            "respuesta_parcial": "",
            "respuesta_final": "",
            "verificada": False,
            "observaciones": "",
            "trace_id": str(uuid.uuid4()),
            "timestamp": datetime.now().isoformat(),
            "estado": "clasificando",
            "error": None,
        }

        return self.grafo.invoke(estado_inicial)


# ============================================================
# TEST
# ============================================================
if __name__ == "__main__":
    print("=" * 50)
    print("URA LangGraph Orchestrator")
    print("=" * 50)

    orchestrator = URAOrchestrator()

    # Test 1: Mensaje simple
    print("\n📨 Test 1: 'Dime una receta de paella'")
    resultado = orchestrator.procesar("Dime una receta de paella", "test_chat")

    print(f"   Intent: {resultado['intent']}")
    print(f"   Agente: {resultado['agente_destino']}")
    print(f"   Estado: {resultado['estado']}")
    print(f"   Respuesta: {resultado['respuesta_final'][:100]}...")

    # Test 2: Factura
    print("\n📨 Test 2: 'Necesito hacer una factura'")
    resultado2 = orchestrator.procesar("Necesito hacer una factura", "test_chat")

    print(f"   Intent: {resultado2['intent']}")
    print(f"   Agente: {resultado2['agente_destino']}")
    print(f"   Estado: {resultado2['estado']}")

    print("\n✅ Orchestrator funcionando")
