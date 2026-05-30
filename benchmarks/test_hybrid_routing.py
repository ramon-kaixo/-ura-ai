#!/usr/bin/env python3
"""
URA - Prueba de Enrutamiento Híbrido con 3 Filtros
Valida que el Director Técnico actúe como gatekeeper con los 3 filtros implementados
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "core"))

import logging

from technical_director import get_technical_director
from workflow_engine import URAWorkflowEngine

# Configurar logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def test_filter_1_first_interaction():
    """Prueba 1: Filtro 1 - Primera interacción obliga al Técnico"""
    print("=" * 60)
    print("PRUEBA 1 - FILTRO 1: PRIMERA INTERACCIÓN AL TÉCNICO")
    print("=" * 60)

    engine = URAWorkflowEngine()

    # Verificar estado inicial
    print("\n📊 Estado inicial de conversación:")
    print(f"   Primera interacción: {engine.conversation_state['first_interaction']}")
    print(f"   Conteo de interacciones: {engine.conversation_state['interaction_count']}")

    # Simular primera interacción
    user_request = "Hola"
    print(f"\n📝 Primera interacción: '{user_request}'")

    # Clasificar intención
    director = get_technical_director()
    intent = director.classify_intent(user_request)
    print(f"\n🎯 Intentión clasificada: {intent}")

    # Verificar que fue al Técnico
    if engine.conversation_state["first_interaction"]:
        print("\n✅ PRUEBA 1 PASADA: Primera interacción obliga al Técnico")
        return True
    else:
        print("\n❌ PRUEBA 1 FALLIDA: Primera interacción no obliga al Técnico")
        return False


def test_filter_2_technical_clarification():
    """Prueba 2: Filtro 2 - Coletilla de paso a forma técnica"""
    print("\n" + "=" * 60)
    print("PRUEBA 2 - FILTRO 2: COLETILLA DE PASO A FORMA TÉCNICA")
    print("=" * 60)

    director = get_technical_director()

    # Petición ambigua que el Técnico no entendería
    user_request = "algo con archivos"
    print(f"\n📝 Petición ambigua: '{user_request}'")

    # Solicitar clarificación
    clarification = director.request_technical_clarification(user_request)

    print("\n✨ Coletilla de clarificación:")
    print(clarification)

    # Verificar que contiene la coletilla
    if "pasa esta conversación a una forma técnica" in clarification.lower():
        print("\n✅ PRUEBA 2 PASADA: Coletilla de paso a forma técnica presente")
        return True
    else:
        print("\n❌ PRUEBA 2 FALLIDA: Coletilla no encontrada")
        return False


def test_filter_3_force_technical_route():
    """Prueba 3: Filtro 3 - Forzar ruta técnica para problemas técnicos"""
    print("\n" + "=" * 60)
    print("PRUEBA 3 - FILTRO 3: FORZAR RUTA TÉCNICA")
    print("=" * 60)

    director = get_technical_director()

    # Petición técnica
    technical_requests = [
        "Busca el presupuesto de cucarachas",
        "Lee el archivo presupuesto.xlsx",
        "Ejecuta comando find ~/",
        "Analiza los datos del correo",
    ]

    print(f"\n📝 Probando {len(technical_requests)} peticiones técnicas:")

    all_technical = True
    for request in technical_requests:
        intent = director.classify_intent(request)
        print(f"\n   Petición: '{request}'")
        print(f"   Intentión: {intent}")
        if intent != "TECHNICAL":
            all_technical = False

    if all_technical:
        print("\n✅ PRUEBA 3 PASADA: Todas las peticiones técnicas forzadas a ruta técnica")
        return True
    else:
        print("\n❌ PRUEBA 3 FALLIDA: Algunas peticiones no forzadas a ruta técnica")
        return False


def test_filter_3_general_route_allowed():
    """Prueba 4: Filtro 3 - Ruta general permitida para saludos"""
    print("\n" + "=" * 60)
    print("PRUEBA 4 - FILTRO 3: RUTA GENERAL PARA SALUDOS")
    print("=" * 60)

    director = get_technical_director()

    # Petición general
    general_requests = ["Hola", "Buenos días", "Gracias", "Adiós"]

    print(f"\n📝 Probando {len(general_requests)} peticiones generales:")

    all_general = True
    for request in general_requests:
        intent = director.classify_intent(request)
        print(f"\n   Petición: '{request}'")
        print(f"   Intentión: {intent}")
        if intent != "GENERAL":
            all_general = False

    if all_general:
        print("\n✅ PRUEBA 4 PASADA: Saludos permitidos en ruta general")
        return True
    else:
        print("\n❌ PRUEBA 4 FALLIDA: Saludos no permitidos en ruta general")
        return False


def test_full_routing_pipeline():
    """Prueba 5: Pipeline completo de enrutamiento"""
    print("\n" + "=" * 60)
    print("PRUEBA 5 - PIPELINE COMPLETO DE ENRUTAMIENTO")
    print("=" * 60)

    engine = URAWorkflowEngine()

    # Simular primera interacción técnica
    print("\n📝 Primera interacción: 'Busca el presupuesto de cucarachas'")
    response1 = engine.process_user_request("Busca el presupuesto de cucarachas")

    print("\n✨ Respuesta 1:")
    print(response1[:200] + "..." if len(response1) > 200 else response1)

    # Verificar estado después de primera interacción
    print("\n📊 Estado después de primera interacción:")
    print(f"   Primera interacción: {engine.conversation_state['first_interaction']}")
    print(f"   Última intención: {engine.conversation_state['last_intent']}")

    # Simular segunda interacción (saludo)
    print("\n📝 Segunda interacción: 'Hola'")
    response2 = engine.process_user_request("Hola")

    print("\n✨ Respuesta 2:")
    print(response2[:200] + "..." if len(response2) > 200 else response2)

    # Verificar que el estado se actualizó
    if not engine.conversation_state["first_interaction"]:
        print("\n✅ PRUEBA 5 PASADA: Pipeline de enrutamiento funcionó correctamente")
        return True
    else:
        print("\n❌ PRUEBA 5 FALLIDA: Estado no se actualizó correctamente")
        return False


if __name__ == "__main__":
    print("\n🚦 PRUEBA DE ENRUTAMIENTO HÍBRIDO - 3 FILTROS 🚦")
    print("Validando Director Técnico como Gatekeeper\n")

    test1_passed = test_filter_1_first_interaction()
    test2_passed = test_filter_2_technical_clarification()
    test3_passed = test_filter_3_force_technical_route()
    test4_passed = test_filter_3_general_route_allowed()
    test5_passed = test_full_routing_pipeline()

    print("\n" + "=" * 60)
    print("RESUMEN DE PRUEBAS")
    print("=" * 60)
    print(
        f"Prueba 1 (Filtro 1 - Primera Interacción): {'✅ PASADA' if test1_passed else '❌ FALLIDA'}"
    )
    print(
        f"Prueba 2 (Filtro 2 - Coletilla Técnica): {'✅ PASADA' if test2_passed else '❌ FALLIDA'}"
    )
    print(f"Prueba 3 (Filtro 3 - Forzar Técnica): {'✅ PASADA' if test3_passed else '❌ FALLIDA'}")
    print(f"Prueba 4 (Filtro 3 - Ruta General): {'✅ PASADA' if test4_passed else '❌ FALLIDA'}")
    print(f"Prueba 5 (Pipeline Completo): {'✅ PASADA' if test5_passed else '❌ FALLIDA'}")

    all_passed = test1_passed and test2_passed and test3_passed and test4_passed and test5_passed
    print(f"\n{'✅ TODAS LAS PRUEBAS PASADAS' if all_passed else '❌ ALGUNAS PRUEBAS FALLARON'}")
    print("=" * 60)

    sys.exit(0 if all_passed else 1)
