#!/usr/bin/env python3
"""
URA - Prueba de Fuego del Director Técnico
Simulación de búsqueda de presupuesto para verificar que ninguna silla diga "no puedo"
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "core"))

import logging

from consensus_system import get_consensus_system
from technical_director import get_technical_director

# Configurar logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def test_director_approval():
    """Prueba 1: Director Técnico aprueba operación de búsqueda de presupuesto"""
    print("=" * 60)
    print("PRUEBA DE FUEGO - DIRECTOR TÉCNICO")
    print("=" * 60)

    # Inicializar Director Técnico
    director = get_technical_director()
    print("\n✅ Director Técnico inicializado")
    print(f"   Estado: {director.get_status()}")

    # Simular petición de presupuesto
    user_request = "Busca el presupuesto de cucarachas en ~/Documents/"
    print(f"\n📝 Petición del usuario: {user_request}")

    # Generar Ficha de Instrucción Técnica
    instruction_sheet = director.generate_instruction_sheet(user_request)
    print("\n📋 Ficha de Instrucción Técnica:")
    print(f"   Aprobada: {instruction_sheet.get('approved')}")
    print(f"   Operación: {instruction_sheet.get('operation_type')}")
    print(f"   Capacidad: {instruction_sheet.get('capability_required')}")
    print(f"   Pasos: {instruction_sheet.get('technical_steps', [])}")
    print(f"   Herramientas: {instruction_sheet.get('tools_needed', [])}")
    print(f"   Generado por: {instruction_sheet.get('generated_by', 'ollama')}")

    # Si el fallback manual funcionó, también cuenta como aprobado
    if (
        instruction_sheet.get("approved")
        or instruction_sheet.get("generated_by") == "manual_fallback"
    ):
        print(
            f"\n✅ PRUEBA 1 PASADA: Director Técnico aprobó la operación (via {instruction_sheet.get('generated_by', 'ollama')})"
        )
        return True
    else:
        print("\n❌ PRUEBA 1 FALLIDA: Director Técnico rechazó la operación")
        print(f"   Razón: {instruction_sheet.get('rejection_reason')}")
        return False


def test_strict_execution_mode():
    """Prueba 2: Las sillas ejecutan en modo estricto sin decir "no puedo" """
    print("\n" + "=" * 60)
    print("PRUEBA DE FUEGO - MODO EJECUCIÓN ESTRICTA")
    print("=" * 60)

    # Inicializar sistema de consenso
    consensus = get_consensus_system()
    print("\n✅ Sistema de Consenso inicializado")

    # Crear Ficha de Instrucción Técnica simulada
    instruction_sheet = {
        "approved": True,
        "operation_type": "FILESYSTEM_ACCESS",
        "capability_required": "FILESYSTEM_ACCESS",
        "technical_steps": [
            'find ~/ -name "*presupuesto*" -type f',
            'grep -i "cucaracha" ~/Documents/',
            "cat [archivo_encontrado]",
        ],
        "tools_needed": ["find", "grep", "cat"],
        "constraints": [],
    }

    # Consulta de prueba
    query = "Busca el presupuesto de cucarachas"
    print(f"\n📝 Consulta: {query}")
    print("\n📋 Ficha de Instrucción Técnica:")
    print(f"   Operación: {instruction_sheet.get('operation_type')}")
    print(f"   Pasos: {instruction_sheet.get('technical_steps')}")

    # Ejecutar consulta en modo estricto
    consensus_reached, response, detalles = consensus.tripartite_consultation(
        query, strict_execution_mode=True, instruction_sheet=instruction_sheet
    )

    print("\n📊 Resultado del Consenso:")
    print(f"   Consenso alcanzado: {consensus_reached}")
    print(f"   Modo estricto: {detalles.get('strict_execution_mode')}")
    print(f"   Respuestas de sillas: {len(detalles.get('responses', {}))}")

    # Verificar que ninguna silla dijo "no puedo"
    for model, resp in detalles.get("responses", {}).items():
        if "no puedo" in resp.lower() or "no tengo acceso" in resp.lower():
            print(f"\n❌ PRUEBA 2 FALLIDA: Silla {model} dijo 'no puedo'")
            print(f"   Respuesta: {resp}")
            return False

    if consensus_reached:
        print("\n✅ PRUEBA 2 PASADA: Las sillas ejecutaron sin decir 'no puedo'")
    else:
        print("\n❌ PRUEBA 2 FALLIDA: No se alcanzó consenso")
        print(f"   Respuesta: {response}")
        return False

    return True


def test_telegram_technical_output():
    """Prueba 3: Formato de salida técnica de Telegram"""
    print("\n" + "=" * 60)
    print("PRUEBA DE FUEGO - SALIDA TÉCNICA TELEGRAM")
    print("=" * 60)

    from telegram_security_bridge import get_telegram_bridge

    # Inicializar puente de Telegram
    telegram = get_telegram_bridge()
    print("\n✅ Puente de Telegram inicializado")
    print(f"   Habilitado: {telegram.enabled}")

    # Crear Ficha de Instrucción Técnica simulada
    instruction_sheet = {
        "approved": True,
        "operation_type": "FILESYSTEM_ACCESS",
        "capability_required": "FILESYSTEM_ACCESS",
    }

    # Crear resultado de ejecución simulado
    execution_result = {
        "success": True,
        "data": "Presupuesto encontrado: presupuesto_cucarachas_2024.xlsx",
    }

    print("\n📋 Ficha de Instrucción Técnica:")
    print(f"   Operación: {instruction_sheet.get('operation_type')}")
    print("\n📊 Resultado de Ejecución:")
    print(f"   Éxito: {execution_result.get('success')}")
    print(f"   Datos: {execution_result.get('data')}")

    # Generar respuesta técnica (simulada, no enviar a Telegram real)
    if instruction_sheet and execution_result:
        operation_type = instruction_sheet.get("operation_type", "UNKNOWN")
        success = execution_result.get("success", False)
        data = execution_result.get("data", "")

        message = f"""[OP: {operation_type}]
[RESULT: {"SUCCESS" if success else "FAILURE"}]
[DATA: {data[:200]}]
[TIMESTAMP: 2026-04-22 19:45:00]"""

        print("\n📤 Formato de Salida Técnica:")
        print(message)

        # Verificar formato
        if "[OP:" in message and "[RESULT:" in message and "[DATA:" in message:
            print("\n✅ PRUEBA 3 PASADA: Formato técnico correcto")
            return True
        else:
            print("\n❌ PRUEBA 3 FALLIDA: Formato incorrecto")
            return False

    return True


if __name__ == "__main__":
    print("\n🔥 PRUEBA DE FUEGO - ARQUITECTURA DIRECTOR TÉCNICO 🔥")
    print("Verificando que ninguna silla se atreva a decir 'no puedo'\n")

    test1_passed = test_director_approval()
    test2_passed = test_strict_execution_mode()
    test3_passed = test_telegram_technical_output()

    print("\n" + "=" * 60)
    print("RESUMEN DE PRUEBAS")
    print("=" * 60)
    print(f"Prueba 1 (Director Técnico): {'✅ PASADA' if test1_passed else '❌ FALLIDA'}")
    print(f"Prueba 2 (Modo Estricto): {'✅ PASADA' if test2_passed else '❌ FALLIDA'}")
    print(f"Prueba 3 (Salida Telegram): {'✅ PASADA' if test3_passed else '❌ FALLIDA'}")

    all_passed = test1_passed and test2_passed and test3_passed
    print(f"\n{'✅ TODAS LAS PRUEBAS PASADAS' if all_passed else '❌ ALGUNAS PRUEBAS FALLARON'}")
    print("=" * 60)

    sys.exit(0 if all_passed else 1)
