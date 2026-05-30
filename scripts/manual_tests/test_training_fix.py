#!/usr/bin/env python3
"""
Prueba de TrainingOrchestrator después de las correcciones.

Instancia TrainingOrchestrator(max_queries=10, concurrency=2),
carga semillas del seed_pipeline, corre night_training(max_queries=10)
y muestra self.stats.
"""

import asyncio
import logging
import sys

sys.path.insert(0, "/Users/ramonesnaola/URA/ura_ia_1972")

from core.training_orchestrator import TrainingOrchestrator


async def main():
    """Ejecuta prueba de entrenamiento."""
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s: %(message)s"
    )

    print("=== Prueba de TrainingOrchestrator ===")
    print("Parámetros: max_queries=10, concurrency=2\n")

    try:
        # Instanciar TrainingOrchestrator
        orchestrator = TrainingOrchestrator(max_queries=10, concurrency=2)
        print("✅ TrainingOrchestrator instanciado correctamente")
        print(f"   - max_queries: {orchestrator.max_queries}")
        print(f"   - concurrency: {orchestrator.concurrency}")
        print(f"   - query_timeout: {orchestrator.query_timeout}s")
        print(f"   - responses_dir: {orchestrator.responses_dir}")
        print(f"   - reports_dir: {orchestrator.reports_dir}\n")

        # Ejecutar night_training
        print("Ejecutando night_training(max_queries=10)...")
        await orchestrator.night_training(max_queries=10)
        print("\n✅ night_training completado\n")

        # Mostrar estadísticas
        print("=== Estadísticas ===")
        print(f"Total queries: {orchestrator.stats['total_queries']}")
        print(f"Exitosas: {orchestrator.stats['successful']}")
        print(f"Fallidas: {orchestrator.stats['failed']}")
        print(f"Descompuestas: {orchestrator.stats['decomposed']}")
        print(f"Duración: {orchestrator.stats['duration']:.2f}s")
        print(f"Start time: {orchestrator.stats['start_time']}")
        print(f"End time: {orchestrator.stats['end_time']}\n")

        # Verificar si hubo éxito
        if orchestrator.stats["successful"] > 0:
            print("✅ Prueba exitosa: se procesaron queries correctamente")
        elif orchestrator.stats["total_queries"] == 0:
            print("⚠️  Prueba sin queries: no había semillas para procesar")
        else:
            print("❌ Prueba con errores: todas las queries fallaron")

        return 0

    except RuntimeError as e:
        if "Toshiba no montado" in str(e):
            print(f"❌ Error: {e}")
            print("El disco Toshiba no está montado. Abortando prueba.")
            return 1
        else:
            raise
    except Exception as e:
        print(f"❌ Error inesperado: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
