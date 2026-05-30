#!/usr/bin/env python3
"""
URA - Prueba de Estabilidad del Workflow Engine
Verifica que el workflow engine no se bloquee ni entre en loops infinitos
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "core"))

import logging
import time

from workflow_engine import URAWorkflow

# Configurar logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def test_simple_greeting():
    """Prueba 1: Saludo simple"""
    print("=" * 60)
    print("PRUEBA 1 - SALUDO SIMPLE")
    print("=" * 60)

    engine = URAWorkflow()

    try:
        start_time = time.time()
        response = engine.process("Hola")
        elapsed = time.time() - start_time

        print(f"\n✨ Respuesta: {response[:100]}...")
        print(f"⏱️ Tiempo de respuesta: {elapsed:.2f}s")

        if elapsed < 30:  # Should complete in less than 30 seconds
            print("\n✅ PRUEBA 1 PASADA: Saludo respondió en tiempo razonable")
            return True
        else:
            print("\n❌ PRUEBA 1 FALLIDA: Tiempo de respuesta excesivo")
            return False

    except Exception as e:
        print(f"\n❌ PRUEBA 1 FALLIDA: Error: {e}")
        return False


def test_technical_request():
    """Prueba 2: Petición técnica"""
    print("\n" + "=" * 60)
    print("PRUEBA 2 - PETICIÓN TÉCNICA")
    print("=" * 60)

    engine = URAWorkflow()

    try:
        start_time = time.time()
        response = engine.process("Busca presupuestos de fumigación")
        elapsed = time.time() - start_time

        print(f"\n✨ Respuesta: {response[:100]}...")
        print(f"⏱️ Tiempo de respuesta: {elapsed:.2f}s")

        if elapsed < 30:  # Should complete in less than 30 seconds
            print("\n✅ PRUEBA 2 PASADA: Petición técnica respondió en tiempo razonable")
            return True
        else:
            print("\n❌ PRUEBA 2 FALLIDA: Tiempo de respuesta excesivo")
            return False

    except Exception as e:
        print(f"\n❌ PRUEBA 2 FALLIDA: Error: {e}")
        return False


def test_consecutive_requests():
    """Prueba 3: Peticiones consecutivas"""
    print("\n" + "=" * 60)
    print("PRUEBA 3 - PETICIONES CONSECUTIVAS")
    print("=" * 60)

    engine = URAWorkflow()

    requests = ["Hola", "Busca archivos", "¿Cómo estás?", "Ejecuta comando"]

    try:
        for i, request in enumerate(requests, 1):
            print(f"\n📝 Petición {i}: '{request}'")
            start_time = time.time()
            response = engine.process(request)
            elapsed = time.time() - start_time
            print(f"   ✨ Respuesta: {response[:50]}...")
            print(f"   ⏱️ Tiempo: {elapsed:.2f}s")

            if elapsed > 30:
                print(f"\n❌ PRUEBA 3 FALLIDA: Petición {i} tomó demasiado tiempo")
                return False

        print("\n✅ PRUEBA 3 PASADA: Todas las peticiones respondieron en tiempo razonable")
        return True

    except Exception as e:
        print(f"\n❌ PRUEBA 3 FALLIDA: Error: {e}")
        return False


if __name__ == "__main__":
    print("\n🚦 PRUEBA DE ESTABILIDAD DEL WORKFLOW ENGINE 🚦")
    print("Verificando que el sistema no se bloquee ni entre en loops infinitos\n")

    test1_passed = test_simple_greeting()
    test2_passed = test_technical_request()
    test3_passed = test_consecutive_requests()

    print("\n" + "=" * 60)
    print("RESUMEN DE PRUEBAS")
    print("=" * 60)
    print(f"Prueba 1 (Saludo Simple): {'✅ PASADA' if test1_passed else '❌ FALLIDA'}")
    print(f"Prueba 2 (Petición Técnica): {'✅ PASADA' if test2_passed else '❌ FALLIDA'}")
    print(f"Prueba 3 (Peticiones Consecutivas): {'✅ PASADA' if test3_passed else '❌ FALLIDA'}")

    all_passed = test1_passed and test2_passed and test3_passed
    print(f"\n{'✅ TODAS LAS PRUEBAS PASADAS' if all_passed else '❌ ALGUNAS PRUEBAS FALLARON'}")
    print("=" * 60)

    if all_passed:
        print("\n📋 INSTRUCCIONES PARA EL USUARIO:")
        print("1. Reinicia URA.app")
        print("2. Prueba con 'Hola'")
        print("3. Prueba con 'Busca presupuestos de fumigación'")
        print("4. Verifica que el sistema responda a ambas peticiones")

    sys.exit(0 if all_passed else 1)
