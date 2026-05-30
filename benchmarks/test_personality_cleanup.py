#!/usr/bin/env python3
"""
URA - Prueba de Limpieza de Personalidad
Valida que el sistema elimine hipocresía de IA y priorice datos técnicos
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "core"))

import logging

from workflow_engine import URAWorkflowEngine, clean_human_garbage

# Configurar logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def test_clean_human_garbage():
    """Prueba 1: Filtro de Basura Humana elimina frases hipócritas"""
    print("=" * 60)
    print("PRUEBA 1 - FILTRO DE BASURA HUMANA")
    print("=" * 60)

    # Respuesta con hipocresía
    response_with_garbage = """Como modelo de lenguaje, he encontrado el archivo que buscas.
Es importante recordar que no soy un experto en presupuestos de plagas.
El archivo está en ~/Documents/presupuesto_cucarachas.xlsx.
Espero que esto te sea de ayuda. Si necesitas algo más, no dudes en preguntar."""

    print("\n📝 Respuesta original (con basura):")
    print(response_with_garbage)

    cleaned = clean_human_garbage(response_with_garbage)

    print("\n✨ Respuesta limpia:")
    print(cleaned)

    # Verificar que las frases basura fueron eliminadas
    garbage_phrases = [
        "Como modelo de lenguaje",
        "Es importante recordar",
        "no soy un experto",
        "Espero que esto te sea de ayuda",
        "Si necesitas algo más",
    ]
    found_garbage = [phrase for phrase in garbage_phrases if phrase in cleaned]

    if not found_garbage:
        print("\n✅ PRUEBA 1 PASADA: Todas las frases basura fueron eliminadas")
        return True
    else:
        print(f"\n❌ PRUEBA 1 FALLIDA: Frases basura encontradas: {found_garbage}")
        return False


def test_extract_technical_data():
    """Prueba 2: Extracción de datos técnicos (Data First)"""
    print("\n" + "=" * 60)
    print("PRUEBA 2 - JERARQUÍA DE DATOS (DATA FIRST)")
    print("=" * 60)

    engine = URAWorkflowEngine()

    # Texto con datos técnicos
    text_with_data = """El presupuesto de cucarachas está en ~/Documents/presupuesto_2024.xlsx.
El precio total es $450.00 por el tratamiento completo.
La fecha del servicio es 15/05/2024.
El archivo tiene un tamaño de 2.5 MB."""

    print("\n📝 Texto original:")
    print(text_with_data)

    technical_data = engine.extract_technical_data(text_with_data)

    print("\n📊 Datos técnicos extraídos:")
    print(technical_data)

    # Verificar que se extrajeron los datos
    has_data = any(
        keyword in technical_data for keyword in ["Rutas:", "Precios:", "Fechas:", "Tamaños:"]
    )

    if has_data:
        print("\n✅ PRUEBA 2 PASADA: Datos técnicos extraídos correctamente")
        return True
    else:
        print("\n❌ PRUEBA 2 FALLIDA: No se extrajeron datos técnicos")
        return False


def test_conduct_violation():
    """Prueba 3: Modo Cero Excusas detecta violaciones de conducta"""
    print("\n" + "=" * 60)
    print("PRUEBA 3 - MODO CERO EXCUSAS")
    print("=" * 60)

    engine = URAWorkflowEngine()

    # Respuesta con excusas
    response_with_excuses = """Lo siento, pero no puedo acceder a ese archivo.
Tengo una limitación que me impide abrir archivos de presupuesto.
No tengo acceso a ~/Documents/."""

    print("\n📝 Respuesta con excusas:")
    print(response_with_excuses)

    has_violation = engine.check_conduct_violation(response_with_excuses)

    print(f"\n🚨 Violación de conducta detectada: {has_violation}")

    if has_violation:
        print("\n✅ PRUEBA 3 PASADA: Modo Cero Excusas detectó violación")
    else:
        print("\n❌ PRUEBA 3 FALLIDA: No se detectó la violación")

    return has_violation


def test_regenerate_strict_response():
    """Prueba 4: Regeneración estricta usando solo ficha técnica"""
    print("\n" + "=" * 60)
    print("PRUEBA 4 - REGENERACIÓN ESTRICTA")
    print("=" * 60)

    engine = URAWorkflowEngine()

    # Ficha de instrucción técnica simulada
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

    user_request = "Busca el presupuesto de cucarachas"

    print("\n📋 Ficha de Instrucción Técnica:")
    print(f"   Operación: {instruction_sheet.get('operation_type')}")
    print(f"   Herramientas: {instruction_sheet.get('tools_needed')}")

    strict_response = engine.regenerate_strict_response(instruction_sheet, user_request)

    print("\n✨ Respuesta regenerada (estricta):")
    print(strict_response)

    # Verificar que la respuesta no contiene excusas
    has_excuses = engine.check_conduct_violation(strict_response)

    if not has_excuses and "OPERACIÓN EJECUTADA" in strict_response:
        print("\n✅ PRUEBA 4 PASADA: Respuesta estricta sin excusas")
        return True
    else:
        print("\n❌ PRUEBA 4 FALLIDA: Respuesta estricta contiene excusas")
        return False


def test_full_cleanup_pipeline():
    """Prueba 5: Pipeline completo de limpieza"""
    print("\n" + "=" * 60)
    print("PRUEBA 5 - PIPELINE COMPLETO DE LIMPIEZA")
    print("=" * 60)

    # Respuesta con hipocresía y datos técnicos
    response_with_issues = """Como modelo de lenguaje, he analizado tu solicitud.
Es importante recordar que no soy un experto en presupuestos.
El archivo está en ~/Documents/presupuesto_cucarachas.xlsx.
El precio es $450.00 y la fecha es 15/05/2024.
Espero que esto te sea de ayuda. Si necesitas algo más, no dudes en preguntar."""

    print("\n📝 Respuesta original (con problemas):")
    print(response_with_issues)

    # Aplicar limpieza
    cleaned = clean_human_garbage(response_with_issues)

    print("\n✨ Respuesta limpia:")
    print(cleaned)

    # Verificar limpieza
    has_garbage = any(
        phrase in cleaned
        for phrase in [
            "Como modelo de lenguaje",
            "Es importante recordar",
            "no soy un experto",
            "Espero que esto te sea de ayuda",
        ]
    )
    has_data = any(
        keyword in cleaned for keyword in ["presupuesto_cucarachas.xlsx", "$450.00", "15/05/2024"]
    )

    if not has_garbage and has_data:
        print("\n✅ PRUEBA 5 PASADA: Pipeline completo funcionó correctamente")
        return True
    else:
        print("\n❌ PRUEBA 5 FALLIDA: Pipeline no funcionó correctamente")
        print(f"   Tiene basura: {has_garbage}")
        print(f"   Tiene datos: {has_data}")
        return False


if __name__ == "__main__":
    print("\n🧹 PRUEBA DE LIMPIEZA DE PERSONALIDAD URA 🧹")
    print("Validando eliminación de hipocresía y priorización de datos\n")

    test1_passed = test_clean_human_garbage()
    test2_passed = test_extract_technical_data()
    test3_passed = test_conduct_violation()
    test4_passed = test_regenerate_strict_response()
    test5_passed = test_full_cleanup_pipeline()

    print("\n" + "=" * 60)
    print("RESUMEN DE PRUEBAS")
    print("=" * 60)
    print(f"Prueba 1 (Filtro Basura): {'✅ PASADA' if test1_passed else '❌ FALLIDA'}")
    print(f"Prueba 2 (Data First): {'✅ PASADA' if test2_passed else '❌ FALLIDA'}")
    print(f"Prueba 3 (Cero Excusas): {'✅ PASADA' if test3_passed else '❌ FALLIDA'}")
    print(f"Prueba 4 (Regeneración): {'✅ PASADA' if test4_passed else '❌ FALLIDA'}")
    print(f"Prueba 5 (Pipeline): {'✅ PASADA' if test5_passed else '❌ FALLIDA'}")

    all_passed = test1_passed and test2_passed and test3_passed and test4_passed and test5_passed
    print(f"\n{'✅ TODAS LAS PRUEBAS PASADAS' if all_passed else '❌ ALGUNAS PRUEBAS FALLARON'}")
    print("=" * 60)

    sys.exit(0 if all_passed else 1)
