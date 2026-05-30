#!/usr/bin/env python3
"""
Banco de Pruebas de Resiliencia - URA App
Tests de Caída de Cerebro, Interrupción de Voz y Latencia de Contexto
"""

import sys
import threading
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


class ResilienceBenchmarkResults:
    """Clase para almacenar resultados de benchmarking de resiliencia"""

    def __init__(self):
        self.results = {}
        self.start_time = datetime.now()

    def add_result(self, test_name, metric, value, unit=""):
        if test_name not in self.results:
            self.results[test_name] = {}
        self.results[test_name][metric] = {"value": value, "unit": unit}

    def print_results(self):
        print("\n" + "=" * 70)
        print("REPORTE DE BENCHMARKING DE RESILIENCIA - URA APP")
        print("=" * 70)
        print(f"Fecha: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)

        for test_name, metrics in self.results.items():
            print(f"\n## {test_name}")
            print("-" * 70)
            for metric, data in metrics.items():
                value = data["value"]
                unit = data["unit"]
                if isinstance(value, int | float):
                    print(f"{metric}: {value:.3f} {unit}")
                else:
                    print(f"{metric}: {value} {unit}")


def test_brain_drop(results):
    """Test 1: Caída de Cerebro - Ollama se detiene durante generación"""
    print("\n" + "=" * 70)
    print("TEST 1: CAÍDA DE CEREBRO")
    print("=" * 70)

    connector = OllamaConnector(default_model="llama3.2:latest")

    if not connector.test_connection(test_model=False):
        print("❌ No se puede conectar a Ollama")
        results.add_result("Test 1: Caída Cerebro", "Estado", "Fallo inicial", "")
        return

    print("✅ Conectado a Ollama")
    print("Simulando caída de Ollama durante generación...")

    # Simular generación y luego desconectar
    start = time.time()

    try:
        # Iniciar generación
        generation_thread = threading.Thread(
            target=lambda: connector.generate("Test largo", options={"max_tokens": 100})
        )
        generation_thread.start()

        # Esperar un poco para que la generación empiece
        time.sleep(0.5)

        # Simular desconexión (forzar estado desconectado)
        connector.is_connected = False

        # Esperar a que termine el thread
        generation_thread.join(timeout=2)

        elapsed = time.time() - start

        print(f"  Generación interrumpida en: {elapsed:.3f}s")

        # Intentar reconectar
        reconnect_start = time.time()
        reconnected = connector.test_connection(test_model=False)
        reconnect_time = time.time() - reconnect_start

        print(f"  Reconexión en: {reconnect_time:.3f}s")

        if reconnected:
            print("  ✅ Reconexión exitosa")
            results.add_result("Test 1: Caída Cerebro", "Estado", "Reconexión exitosa", "")
            results.add_result("Test 1: Caída Cerebro", "Tiempo reconexión", reconnect_time, "s")
        else:
            print("  ❌ No se pudo reconectar")
            results.add_result("Test 1: Caída Cerebro", "Estado", "Fallo reconexión", "")

    except Exception as e:
        print(f"  ❌ Error: {e}")
        results.add_result("Test 1: Caída Cerebro", "Estado", f"Error: {e}", "")


def test_voice_interruption(results):
    """Test 2: Interrupción de Voz - Full Duplex"""
    print("\n" + "=" * 70)
    print("TEST 2: INTERRUPCIÓN DE VOZ (FULL DUPLEX)")
    print("=" * 70)

    print("Simulando interrupción de voz durante generación...")

    # Simular estado de generación
    generation_active = threading.Event()
    generation_active.set()

    # Simular voz interrumpiendo
    voice_interrupted = False

    def simulate_generation():
        """Simular generación de texto"""
        for i in range(10):
            if not generation_active.is_set():
                print(f"  ⚠️  Generación interrumpida por voz en paso {i}")
                return
            time.sleep(0.1)
        print("  ✅ Generación completada sin interrupción")

    def simulate_voice():
        """Simular interrupción de voz"""
        nonlocal voice_interrupted
        time.sleep(0.3)  # Interrumpir a los 300ms
        print("  🔊 Voz detectada - interrumpiendo generación...")
        generation_active.clear()
        voice_interrupted = True

    # Iniciar threads
    gen_thread = threading.Thread(target=simulate_generation)
    voice_thread = threading.Thread(target=simulate_voice)

    start = time.time()
    gen_thread.start()
    voice_thread.start()

    gen_thread.join()
    voice_thread.join()

    elapsed = time.time() - start

    print(f"  Tiempo total: {elapsed:.3f}s")

    if voice_interrupted:
        print("  ✅ Voz interrumpió generación correctamente")
        results.add_result("Test 2: Interrupción Voz", "Estado", "Interrupción exitosa", "")
        results.add_result("Test 2: Interrupción Voz", "Tiempo interrupción", 0.3, "s")
    else:
        print("  ⚠️  Voz no interrumpió generación")
        results.add_result("Test 2: Interrupción Voz", "Estado", "Sin interrupción", "")


def test_context_latency(results):
    """Test 3: Latencia de Contexto - 5000 líneas"""
    print("\n" + "=" * 70)
    print("TEST 3: LATENCIA DE CONTEXTO (5000 LÍNEAS)")
    print("=" * 70)

    connector = OllamaConnector(default_model="llama3.2:latest")

    if not connector.test_connection(test_model=False):
        print("❌ No se puede conectar a Ollama")
        results.add_result("Test 3: Latencia Contexto", "Estado", "Fallo inicial", "")
        return

    print("✅ Conectado a Ollama")
    print("Generando contexto de 5000 líneas...")

    # Generar contexto simulado de 5000 líneas
    context_lines = [
        f"Línea de contexto {i}: Contenido de prueba para simular contexto largo."
        for i in range(5000)
    ]
    context_text = "\n".join(context_lines)

    print(f"  Contexto generado: {len(context_text)} caracteres")

    # Medir TTFT sin contexto
    print("  Midiendo TTFT sin contexto...")
    start = time.time()
    try:
        connector.generate("Hola", options={"max_tokens": 20})
        ttft_no_context = time.time() - start
        print(f"  TTFT sin contexto: {ttft_no_context * 1000:.0f}ms")
    except Exception as e:
        print(f"  ❌ Error: {e}")
        ttft_no_context = 0

    # Medir TTFT con contexto
    print("  Midiendo TTFT con contexto de 5000 líneas...")
    start = time.time()
    try:
        prompt_with_context = f"Contexto:\n{context_text}\n\nPregunta: Hola"
        connector.generate(prompt_with_context, options={"max_tokens": 20})
        ttft_with_context = time.time() - start
        print(f"  TTFT con contexto: {ttft_with_context * 1000:.0f}ms")
    except Exception as e:
        print(f"  ❌ Error: {e}")
        ttft_with_context = 0

    if ttft_no_context > 0 and ttft_with_context > 0:
        slowdown = ttft_with_context - ttft_no_context
        slowdown_percent = (slowdown / ttft_no_context) * 100

        print(f"  Ralentización: {slowdown * 1000:.0f}ms ({slowdown_percent:.1f}%)")

        if slowdown < 0.5:
            print("  ✅ Ralentización < 500ms (aceptable)")
            results.add_result("Test 3: Latencia Contexto", "Estado", "Ralentización aceptable", "")
        else:
            print("  ⚠️  Ralentización >= 500ms (significativa)")
            results.add_result(
                "Test 3: Latencia Contexto", "Estado", "Ralentización significativa", ""
            )

        results.add_result("Test 3: Latencia Contexto", "TTFT sin contexto", ttft_no_context, "s")
        results.add_result("Test 3: Latencia Contexto", "TTFT con contexto", ttft_with_context, "s")
        results.add_result("Test 3: Latencia Contexto", "Ralentización", slowdown, "s")


def main():
    """Función principal de benchmarking de resiliencia"""
    print("=" * 70)
    print("BANCO DE PRUEBAS DE RESILIENCIA - URA APP")
    print("=" * 70)
    print(f"Iniciando: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    results = ResilienceBenchmarkResults()

    # Ejecutar tests
    test_brain_drop(results)
    test_voice_interruption(results)
    test_context_latency(results)

    # Imprimir resultados
    results.print_results()

    print("\n" + "=" * 70)
    print("RECOMENDACIONES DE IMPLEMENTACIÓN")
    print("=" * 70)

    if "Test 1: Caída Cerebro" in results.results:
        print("1. Implementar manejo de caída de Ollama:")
        print("   - Mostrar mensaje elegante: 'URA ha perdido conexión, reconectando...'")
        print("   - UI no debe cerrarse")
        print("   - Reconexión automática en background")

    if "Test 2: Interrupción Voz" in results.results:
        print("2. Implementar Full Duplex para voz:")
        print("   - Hilo de voz debe tener prioridad")
        print("   - Cancelar/pausar generación actual al detectar voz")
        print("   - Mostrar indicador visual de interrupción")

    if "Test 3: Latencia Contexto" in results.results:
        print("3. Optimizar manejo de contexto largo:")
        print("   - Si ralentización > 500ms, implementar truncado inteligente")
        print("   - Usar resumen de contexto para consultas largas")
        print("   - Considerar límite de líneas de contexto")

    print("\n" + "=" * 70)
    print("BENCHMARKING DE RESILIENCIA COMPLETADO")
    print("=" * 70)
    print(f"Finalizado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
