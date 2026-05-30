#!/usr/bin/env python3
"""
Banco de Pruebas Maestro - URA App
Test de Stress e Integración Multicéntrica
"""

import json
import sys
import time
from datetime import datetime
from pathlib import Path

# Añadir directorio del proyecto al path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from terminal_gateway import TerminalGateway

    from connectors.ollama_connector import OllamaConnector
except ImportError as e:
    print(f"Error importando módulos: {e}")
    sys.exit(1)


class MasterTestResults:
    """Clase para almacenar resultados del Banco de Pruebas Maestro"""

    def __init__(self):
        self.results = {}
        self.start_time = datetime.now()

    def add_result(self, test_name, metric, value, unit=""):
        if test_name not in self.results:
            self.results[test_name] = {}
        self.results[test_name][metric] = {"value": value, "unit": unit}

    def print_results(self):
        print("\n" + "=" * 70)
        print("REPORTE DEL BANCO DE PRUEBAS MAESTRO - URA APP")
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

    def save_to_json(self, filepath):
        """Guardar resultados en archivo JSON"""
        with open(filepath, "w") as f:
            json.dump(
                {"timestamp": self.start_time.isoformat(), "results": self.results}, f, indent=2
            )


def test_cross_action(results):
    """Test 1: Acción Cruzada (Terminal + Voz + IA)"""
    print("\n" + "=" * 70)
    print("TEST 1: ACCIÓN CRUZADA (TERMINAL + VOZ + IA)")
    print("=" * 70)

    gateway = TerminalGateway()
    connector = OllamaConnector(default_model="llama3.2:latest")

    print(
        "Simulando: 'URA, busca archivos de log en la carpeta de benchmarks y dime cuánta RAM libre tengo'"
    )

    # Paso 1: Buscar archivos de log
    start = time.time()
    benchmarks_dir = Path(__file__).parent
    success1, output1, error1 = gateway.execute_read_only_command(f"ls {benchmarks_dir}/*.log")
    time1 = time.time() - start
    print(f"  Comando 1 (ls logs): {time1:.3f}s - {'✅' if success1 else '❌'}")

    # Paso 2: Ver RAM libre
    start = time.time()
    success2, output2, error2 = gateway.execute_read_only_command("vm_stat")
    time2 = time.time() - start
    print(f"  Comando 2 (RAM): {time2:.3f}s - {'✅' if success2 else '❌'}")

    # Paso 3: Procesar con IA (simulado)
    if connector.test_connection(test_model=False):
        try:
            start = time.time()
            combined = f"Logs: {output1[:100] if output1 else 'none'}\nRAM: {output2[:100] if output2 else 'none'}"
            connector.generate(
                "Resume esto brevemente: " + combined, model="gemma3:1b", options={"max_tokens": 30}
            )
            time3 = time.time() - start
            print(f"  Motor Turbo (procesamiento): {time3:.3f}s - ✅")
            results.add_result("Test 1: Acción Cruzada", "Tiempo Terminal 1", time1, "s")
            results.add_result("Test 1: Acción Cruzada", "Tiempo Terminal 2", time2, "s")
            results.add_result("Test 1: Acción Cruzada", "Tiempo IA", time3, "s")
            results.add_result("Test 1: Acción Cruzada", "Estado", "Éxito", "")
        except Exception as e:
            print(f"  ❌ Error en IA: {e}")
            results.add_result("Test 1: Acción Cruzada", "Estado", "Fallo IA", "")
    else:
        print("  ⚠️  Ollama no disponible")
        results.add_result("Test 1: Acción Cruzada", "Estado", "Ollama no disponible", "")


def test_sandboxing_security(results):
    """Test 2: Seguridad Sandboxing"""
    print("\n" + "=" * 70)
    print("TEST 2: SEGURIDAD SANDBOXING")
    print("=" * 70)

    gateway = TerminalGateway()

    print("Intentando inyectar comando prohibido: rm -rf /")

    # Simular callback de confirmación que rechaza
    def reject_confirmation(command, reason):
        print(f"  ⚠️  Comando peligroso detectado: {reason}")
        print(f"  Comando: {command}")
        print("  ❌ Confirmación rechazada por seguridad")
        return False

    gateway.confirmation_callback = reject_confirmation

    start = time.time()
    success, output, error = gateway.execute_command("rm -rf /")
    elapsed = time.time() - start

    print(f"  Tiempo de respuesta: {elapsed:.3f}s")

    if not success and "cancelado" in str(error).lower():
        print("  ✅ Sistema de seguridad funcionó correctamente")
        results.add_result("Test 2: Sandboxing", "Estado", "Seguridad activa", "")
        results.add_result("Test 2: Sandboxing", "Tiempo respuesta", elapsed, "s")
    else:
        print("  ⚠️  Posible fallo en seguridad")
        results.add_result("Test 2: Sandboxing", "Estado", "Fallo seguridad", "")


def test_audit_performance(results):
    """Test 3: Rendimiento de Auditoría (20 consultas)"""
    print("\n" + "=" * 70)
    print("TEST 3: RENDIMIENTO DE AUDITORÍA (20 CONSULTAS)")
    print("=" * 70)

    try:
        import psutil

        process = psutil.Process()
    except:
        print("⚠️  psutil no disponible")
        process = None

    gateway = TerminalGateway()

    initial_mem = process.memory_info().rss / 1024 / 1024 if process else 50
    print(f"  Memoria inicial: {initial_mem:.2f} MB")

    print("  Ejecutando 20 consultas rápidas...")
    times = []

    for i in range(20):
        start = time.time()
        success, output, error = gateway.execute_read_only_command("pwd")
        elapsed = time.time() - start
        times.append(elapsed)

        if i % 5 == 0:
            print(f"    Consulta {i + 1}/20: {elapsed:.3f}s")

    final_mem = process.memory_info().rss / 1024 / 1024 if process else 50
    memory_increase = final_mem - initial_mem

    avg_time = sum(times) / len(times)
    max_time = max(times)
    min_time = min(times)

    print(f"\n  Tiempo medio: {avg_time:.3f}s")
    print(f"  Tiempo mínimo: {min_time:.3f}s")
    print(f"  Tiempo máximo: {max_time:.3f}s")
    print(f"  Memoria final: {final_mem:.2f} MB")
    print(f"  Aumento memoria: {memory_increase:.2f} MB")

    # Verificar log
    from pathlib import Path

    terminal_log = Path(__file__).parent / "terminal_commands.log"
    if terminal_log.exists():
        log_size = terminal_log.stat().st_size
        print(f"  terminal_commands.log: {log_size} bytes")
        results.add_result("Test 3: Auditoría", "Log tamaño", log_size, "bytes")
    else:
        print("  ❌ terminal_commands.log no existe")

    if memory_increase < 50:
        print("  ✅ Aumento de memoria < 50MB (objetivo cumplido)")
        results.add_result("Test 3: Auditoría", "Estado", "Éxito", "")
    else:
        print("  ⚠️  Aumento de memoria >= 50MB")
        results.add_result("Test 3: Auditoría", "Estado", "Memoria alta", "")

    results.add_result("Test 3: Auditoría", "Tiempo medio", avg_time, "s")
    results.add_result("Test 3: Auditoría", "Aumento memoria", memory_increase, "MB")


def test_gateway_resilience(results):
    """Test 4: Resiliencia del Gateway (timeout)"""
    print("\n" + "=" * 70)
    print("TEST 4: RESILIENCIA DEL GATEWAY (TIMEOUT)")
    print("=" * 70)

    gateway = TerminalGateway()

    print("Simulando comando colgado: sleep 60")

    start = time.time()
    success, output, error = gateway.execute_command("sleep 60")
    elapsed = time.time() - start

    print(f"  Tiempo de respuesta: {elapsed:.3f}s")

    if elapsed < 35:  # Debe timeout antes de 30s + overhead
        print(f"  ✅ Timeout funcionó correctamente (se detuvo en {elapsed:.3f}s)")
        results.add_result("Test 4: Resiliencia", "Estado", "Timeout activo", "")
        results.add_result("Test 4: Resiliencia", "Tiempo respuesta", elapsed, "s")
    else:
        print(f"  ❌ Timeout no funcionó (se tardó {elapsed:.3f}s)")
        results.add_result("Test 4: Resiliencia", "Estado", "Timeout falló", "")


def main():
    """Función principal del Banco de Pruebas Maestro"""
    print("=" * 70)
    print("BANCO DE PRUEBAS MAESTRO - URA APP")
    print("Test de Stress e Integración Multicéntrica")
    print("=" * 70)
    print(f"Iniciando: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    results = MasterTestResults()

    # Ejecutar tests
    test_cross_action(results)
    test_sandboxing_security(results)
    test_audit_performance(results)
    test_gateway_resilience(results)

    # Imprimir resultados
    results.print_results()

    # Guardar resultados en JSON
    results_file = Path(__file__).parent / "master_test_results.json"
    results.save_to_json(results_file)
    print(f"\n✅ Resultados guardados en: {results_file}")

    print("\n" + "=" * 70)
    print("BANCO DE PRUEBAS MAESTRO COMPLETADO")
    print("=" * 70)
    print(f"Finalizado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
