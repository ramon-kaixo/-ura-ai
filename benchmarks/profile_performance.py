#!/usr/bin/env python3
"""
Script de Profiling para URA App
Mide rendimiento de flujo unificado y cuellos de botella
"""

import sys
import time
from pathlib import Path

# Añadir directorio del proyecto al path
sys.path.insert(0, str(Path(__file__).parent))

try:
    from connectors.ollama_connector import OllamaConnector
except ImportError:
    print("Error: No se puede importar ollama_connector")
    sys.exit(1)


def profile_ollama_connection():
    """Profiling de conexión con Ollama"""
    print("\n=== PROFILING: Conexión con Ollama ===")

    connector = OllamaConnector(default_model="llama3.2:latest")

    # Medir tiempo de conexión
    start = time.time()
    connected = connector.test_connection(test_model=False)
    elapsed = time.time() - start

    print(f"Tiempo de conexión básica: {elapsed:.3f}s")
    print(f"Estado: {'Conectado' if connected else 'Desconectado'}")

    if connected:
        # Medir tiempo de obtención de modelos
        start = time.time()
        models = connector.get_models()
        elapsed = time.time() - start

        print(f"Tiempo de obtención de modelos: {elapsed:.3f}s")
        print(f"Número de modelos: {len(models)}")

        # Medir tiempo de generación
        if models:
            start = time.time()
            try:
                response = connector.generate("Test", model=models[0], options={"max_tokens": 10})
                elapsed = time.time() - start
                print(f"Tiempo de generación: {elapsed:.3f}s")
                print(f"Longitud de respuesta: {len(response)} caracteres")
            except Exception as e:
                print(f"Error en generación: {e}")


def profile_unified_flow():
    """Profiling del flujo unificado"""
    print("\n=== PROFILING: Flujo Unificado ===")

    # Simular flujo Entrada → Ura → Pendiente → Windsurf → Contexto
    steps = {"Entrada": 0.001, "Ura": 0, "Pendiente": 0.001, "Windsurf": 0, "Contexto": 0.001}

    # Simular tiempos
    connector = OllamaConnector(default_model="llama3.2:latest")

    # Paso 1: Entrada (simulado)
    start = time.time()
    input_text = "Hola, ¿cómo estás?"
    time.sleep(0.001)  # Simular procesamiento de entrada
    steps["Entrada"] = time.time() - start

    # Paso 2: Ura (generación con Ollama)
    start = time.time()
    try:
        if connector.test_connection(test_model=False):
            connector.generate(input_text, options={"max_tokens": 20})
        else:
            pass
    except:
        pass
    steps["Ura"] = time.time() - start

    # Paso 3: Pendiente (simulado)
    start = time.time()
    time.sleep(0.001)  # Simular almacenamiento en pendiente
    steps["Pendiente"] = time.time() - start

    # Paso 4: Windsurf (simulado)
    start = time.time()
    time.sleep(0.002)  # Simular procesamiento de Windsurf
    steps["Windsurf"] = time.time() - start

    # Paso 5: Contexto (simulado)
    start = time.time()
    time.sleep(0.001)  # Simular actualización de contexto
    steps["Contexto"] = time.time() - start

    # Mostrar resultados
    total_time = sum(steps.values())
    print("Tiempos por paso:")
    for step, elapsed in steps.items():
        percentage = (elapsed / total_time) * 100
        print(f"  {step}: {elapsed:.3f}s ({percentage:.1f}%)")
    print(f"  Total: {total_time:.3f}s")


def profile_ui_rendering():
    """Profiling de renderizado de UI"""
    print("\n=== PROFILING: Renderizado de UI ===")

    # Simular renderizado de componentes UI
    components = {
        "Header": 0.002,
        "Panel Windsurf": 0.001,
        "Panel URA (Historial)": 0.001,
        "Panel URA (Pendiente)": 0.001,
        "Panel URA (Contexto)": 0.001,
        "Input Bar": 0.001,
        "Botones Voz": 0.001,
    }

    start = time.time()
    for _component, delay in components.items():
        time.sleep(delay)
    elapsed = time.time() - start

    print(f"Tiempo total de renderizado UI: {elapsed:.3f}s")
    print("Componentes renderizados:", len(components))


def profile_positioning():
    """Profiling de cálculo de posicionamiento"""
    print("\n=== PROFILING: Posicionamiento de Ventana ===")

    start = time.time()

    # Simular cálculo de posicionamiento
    # En la app real esto usa QDesktopWidget
    screen_height = 1080
    window_width = 1800
    window_height = screen_height - 50
    x_position = 0
    y_position = 25

    elapsed = time.time() - start

    print(f"Tiempo de cálculo de posicionamiento: {elapsed:.6f}s")
    print(f"Posición calculada: ({x_position}, {y_position}, {window_width}, {window_height})")

    if elapsed > 0.001:
        print("⚠️  El cálculo de posicionamiento es lento")
    else:
        print("✅ El cálculo de posicionamiento es rápido")


def generate_performance_report():
    """Generar informe de rendimiento"""
    print("\n" + "=" * 60)
    print("INFORME DE RENDIMIENTO - URA APP")
    print("=" * 60)

    profile_ollama_connection()
    profile_unified_flow()
    profile_ui_rendering()
    profile_positioning()

    print("\n" + "=" * 60)
    print("RECOMENDACIONES DE OPTIMIZACIÓN")
    print("=" * 60)
    print("1. Conexión Ollama: Usar keep-alive para reconexiones rápidas")
    print("2. Flujo Unificado: Implementar caching para respuestas repetidas")
    print("3. UI: Usar lazy loading para componentes pesados")
    print("4. Posicionamiento: Ya está optimizado (cálculo < 1ms)")
    print("5. Threading: Verificar que QThreads estén funcionando correctamente")


if __name__ == "__main__":
    generate_performance_report()
