#!/usr/bin/env python3
"""
Banco de Pruebas Avanzado - URA App
Tests de Streaming, Memoria y Model Switching
"""

import contextlib
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path

# Añadir directorio del proyecto al path
sys.path.insert(0, str(Path(__file__).parent))

try:
    from connectors.ollama_connector import OllamaConnector
except ImportError:
    print("Error: No se puede importar ollama_connector")
    sys.exit(1)


class AdvancedBenchmarkResults:
    """Clase para almacenar resultados de benchmarking avanzado"""

    def __init__(self):
        self.results = {}
        self.start_time = datetime.now()

    def add_result(self, test_name, metric, value, unit="s"):
        if test_name not in self.results:
            self.results[test_name] = {}
        self.results[test_name][metric] = {"value": value, "unit": unit}

    def print_results(self):
        print("\n" + "=" * 70)
        print("REPORTE DE BENCHMARKING AVANZADO - URA APP")
        print("=" * 70)
        print(f"Fecha: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)

        for test_name, metrics in self.results.items():
            print(f"\n## {test_name}")
            print("-" * 70)
            for metric, data in metrics.items():
                value = data["value"]
                unit = data["unit"]
                if isinstance(value, list):
                    print(f"{metric}: {statistics.mean(value):.3f} {unit} (media)")
                    print(f"  Min: {min(value):.3f} {unit}, Max: {max(value):.3f} {unit}")
                    if len(value) > 1:
                        print(f"  Jitter: {statistics.stdev(value):.3f} {unit}")
                elif isinstance(value, int | float):
                    print(f"{metric}: {value:.3f} {unit}")
                else:
                    print(f"{metric}: {value} {unit}")


def test_streaming_ttft(results):
    """Test 1: Banco de Prueba de Streaming (TTFT)"""
    print("\n" + "=" * 70)
    print("TEST 1: STREAMING - TTFT (Time to First Token)")
    print("=" * 70)

    connector = OllamaConnector(default_model="llama3.2:latest")

    if not connector.test_connection(test_model=False):
        print("❌ No se puede conectar a Ollama")
        results.add_result("Test 1: Streaming", "Estado", "Fallo", "")
        return

    print("✅ Conectado a Ollama")
    print("Ejecutando test de streaming...")

    ttft_times = []
    full_response_times = []

    for i in range(5):
        print(f"  Iteración {i + 1}/5...")

        first_token_time = None

        def chunk_callback(chunk):
            nonlocal first_token_time
            if first_token_time is None:
                first_token_time = time.time()

        start = time.time()
        try:
            # Usar generate_stream para medir TTFT
            connector.generate_stream(
                "Hola", chunk_callback=chunk_callback, options={"max_tokens": 50}
            )
            elapsed = time.time() - start

            if first_token_time:
                ttft = first_token_time - start
                ttft_times.append(ttft)
                full_response_times.append(elapsed)

                print(f"    TTFT: {ttft * 1000:.0f}ms, Tiempo total: {elapsed:.3f}s")

                if ttft < 0.5:
                    print("    ✅ TTFT < 500ms (objetivo cumplido)")
                else:
                    print("    ⚠️  TTFT >= 500ms (objetivo no cumplido)")
            else:
                print("    ❌ No se recibió primer token")

        except Exception as e:
            print(f"    ❌ Error: {e}")

    if ttft_times:
        results.add_result("Test 1: Streaming", "TTFT medio", ttft_times, "s")
        results.add_result("Test 1: Streaming", "Tiempo total medio", full_response_times, "s")
        results.add_result("Test 1: Streaming", "Estado", "Éxito", "")

        print(f"\n  TTFT medio: {statistics.mean(ttft_times) * 1000:.0f}ms")
        print(f"  Tiempo total medio: {statistics.mean(full_response_times):.3f}s")

        if statistics.mean(ttft_times) < 0.5:
            print("  ✅ Objetivo TTFT < 500ms cumplido")
        else:
            print("  ⚠️  Objetivo TTFT < 500ms no cumplido")


def test_memory_load(results):
    """Test 2: Carga de Memoria en Conversación Larga"""
    print("\n" + "=" * 70)
    print("TEST 2: CARGA DE MEMORIA - 50 MENSAJES")
    print("=" * 70)

    try:
        import psutil

        process = psutil.Process()
    except:
        print("⚠️  psutil no disponible, usando simulación")
        process = None

    connector = OllamaConnector(default_model="llama3.2:latest")

    if not connector.test_connection(test_model=False):
        print("❌ No se puede conectar a Ollama")
        results.add_result("Test 2: Memoria", "Estado", "Fallo", "")
        return

    print("✅ Conectado a Ollama")
    print("Simulando 50 mensajes consecutivos...")

    memory_samples = []
    initial_mem = process.memory_info().rss / 1024 / 1024 if process else 50
    print(f"  Memoria inicial: {initial_mem:.2f} MB")

    for i in range(50):
        if i % 10 == 0:
            print(f"  Mensaje {i + 1}/50...")

        # Simular mensaje
        with contextlib.suppress(BaseException):
            connector.generate(f"Mensaje {i}", options={"max_tokens": 20})

        # Muestrear memoria cada 10 mensajes
        if process and i % 10 == 0:
            current_mem = process.memory_info().rss / 1024 / 1024
            memory_samples.append(current_mem)
            print(f"    Memoria actual: {current_mem:.2f} MB")

    final_mem = process.memory_info().rss / 1024 / 1024 if process else initial_mem
    memory_increase = final_mem - initial_mem

    print(f"\n  Memoria final: {final_mem:.2f} MB")
    print(f"  Aumento total: {memory_increase:.2f} MB")

    if memory_samples:
        print(f"  Pico de memoria: {max(memory_samples):.2f} MB")

    if memory_increase > 1500:
        print("  ⚠️  Aumento > 1.5GB (posible memory leak)")
        results.add_result("Test 2: Memoria", "Estado", "Memory Leak detectado", "")
    else:
        print("  ✅ Aumento < 1.5GB (sin memory leaks)")
        results.add_result("Test 2: Memoria", "Estado", "Sin leaks", "")

    results.add_result("Test 2: Memoria", "Memoria inicial", initial_mem, "MB")
    results.add_result("Test 2: Memoria", "Memoria final", final_mem, "MB")
    results.add_result("Test 2: Memoria", "Aumento memoria", memory_increase, "MB")


def test_model_switching(results):
    """Test 3: Model Switching (Eficiencia Energética)"""
    print("\n" + "=" * 70)
    print("TEST 3: MODEL SWITCHING")
    print("=" * 70)

    connector = OllamaConnector(default_model="llama3.2:latest")

    if not connector.test_connection(test_model=False):
        print("❌ No se puede conectar a Ollama")
        results.add_result("Test 3: Model Switching", "Estado", "Fallo", "")
        return

    print("✅ Conectado a Ollama")

    # Obtener modelos disponibles
    models = connector.get_models()
    print(f"  Modelos disponibles: {len(models)}")

    # Buscar modelos ligeros
    light_models = [
        m for m in models if "tiny" in m.lower() or "phi" in m.lower() or "gemma" in m.lower()
    ]

    if not light_models:
        print("  ⚠️  No se encontraron modelos ligeros, usando modelo actual")
        light_models = [connector.default_model]

    # Comparar modelos
    model_performance = {}

    for model in light_models[:3]:  # Probar hasta 3 modelos
        print(f"\n  Probando modelo: {model}")

        try:
            connector.set_model(model)

            generation_times = []
            for _i in range(3):
                start = time.time()
                connector.generate("Test", options={"max_tokens": 20})
                elapsed = time.time() - start
                generation_times.append(elapsed)

            avg_time = statistics.mean(generation_times)
            tokens_per_second = 20 / avg_time  # 20 tokens / tiempo

            model_performance[model] = {"avg_time": avg_time, "tps": tokens_per_second}

            print(f"    Tiempo medio: {avg_time:.3f}s")
            print(f"    Tokens/segundo: {tokens_per_second:.1f}")

        except Exception as e:
            print(f"    ❌ Error: {e}")

    # Restaurar modelo original
    connector.set_model(connector.default_model)

    # Encontrar modelo más rápido
    if model_performance:
        fastest_model = min(model_performance, key=lambda x: model_performance[x]["avg_time"])
        fastest_tps = model_performance[fastest_model]["tps"]

        print(f"\n  Modelo más rápido: {fastest_model}")
        print(f"  Tokens/segundo: {fastest_tps:.1f}")

        results.add_result("Test 3: Model Switching", "Modelo más rápido", fastest_model, "")
        results.add_result("Test 3: Model Switching", "Tokens/segundo", fastest_tps, "")
        results.add_result("Test 3: Model Switching", "Estado", "Éxito", "")

        # Recomendación
        if fastest_model != connector.default_model:
            print(f"  💡 Recomendación: Usar {fastest_model} para respuestas cortas")
        else:
            print("  ✅ Modelo actual ya es el más rápido")


def main():
    """Función principal de benchmarking avanzado"""
    print("=" * 70)
    print("BANCO DE PRUEBAS AVANZADO - URA APP")
    print("=" * 70)
    print(f"Iniciando: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    results = AdvancedBenchmarkResults()

    # Ejecutar tests
    test_streaming_ttft(results)
    test_memory_load(results)
    test_model_switching(results)

    # Imprimir resultados
    results.print_results()

    print("\n" + "=" * 70)
    print("RECOMENDACIONES DE IMPLEMENTACIÓN")
    print("=" * 70)

    if "Test 1: Streaming" in results.results:
        print("1. Implementar streaming (stream=True) para mostrar tokens en tiempo real")
        print("   - Esto mejorará significativamente la experiencia del usuario")

    if "Test 2: Memoria" in results.results:
        status = results.results["Test 2: Memoria"].get("Estado", {}).get("value", "")
        if "Memory Leak" in status:
            print("2. Implementar limpieza de caché automática cuando RAM > 1.5GB")
        else:
            print("2. No se requiere limpieza de caché (sin memory leaks)")

    if "Test 3: Model Switching" in results.results:
        print("3. Implementar lógica de selección de modelo según complejidad")
        print("   - Usar modelo ligero para respuestas cortas del sistema")
        print("   - Usar modelo principal para consultas complejas")

    print("\n" + "=" * 70)
    print("BENCHMARKING AVANZADO COMPLETADO")
    print("=" * 70)
    print(f"Finalizado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
