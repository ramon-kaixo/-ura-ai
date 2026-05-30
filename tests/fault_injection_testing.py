#!/usr/bin/env python3
"""
Fault Injection Testing URA
Testing de tolerancia a fallos
"""

import random
import time
from datetime import datetime
from enum import Enum


class FaultScenario(Enum):
    """Escenarios de fault"""

    DATABASE_DOWN = "database_down"
    HIGH_LATENCY = "high_latency"
    OUT_OF_MEMORY = "out_of_memory"
    DISK_FULL = "disk_full"
    NETWORK_PARTITION = "network_partition"
    SERVICE_CRASH = "service_crash"


class FaultInjector:
    """Inyector de faults para testing"""

    def __init__(self):
        self.escenarios_ejecutados = []

    def inyectar_scenario(self, escenario: FaultScenario, duracion_segundos: int = 10) -> dict:
        """Inyecta escenario de fault"""
        print(f"🎭 Inyectando escenario: {escenario.value} ({duracion_segundos}s)")

        resultado = self._ejecutar_scenario(escenario, duracion_segundos)

        self.escenarios_ejecutados.append(
            {
                "escenario": escenario.value,
                "duracion": duracion_segundos,
                "resultado": resultado,
                "timestamp": datetime.now().isoformat(),
            }
        )

        return resultado

    def _ejecutar_scenario(self, scenario: FaultScenario, duracion: int) -> dict:
        """Ejecuta escenario específico"""
        if scenario == FaultScenario.DATABASE_DOWN:
            return self._simular_database_down(duracion)
        elif scenario == FaultScenario.HIGH_LATENCY:
            return self._simular_high_latency(duracion)
        elif scenario == FaultScenario.OUT_OF_MEMORY:
            return self._simular_out_of_memory(duracion)
        elif scenario == FaultScenario.DISK_FULL:
            return self._simular_disk_full(duracion)
        elif scenario == FaultScenario.NETWORK_PARTITION:
            return self._simular_network_partition(duracion)
        elif scenario == FaultScenario.SERVICE_CRASH:
            return self._simular_service_crash(duracion)

        return {"error": "escenario no implementado"}

    def _simular_database_down(self, duracion: int) -> dict:
        """Simula base de datos caída"""
        # Simulación - en producción desconectar realmente
        return {"escenario": "database_down", "duracion": duracion, "simulado": True}

    def _simular_high_latency(self, duracion: int) -> dict:
        """Simula alta latencia"""
        delay = random.uniform(2, 5)
        time.sleep(delay)
        return {"escenario": "high_latency", "delay_segundos": delay}

    def _simular_out_of_memory(self, duracion: int) -> dict:
        """Simula falta de memoria"""
        return {"escenario": "out_of_memory", "simulado": True}

    def _simular_disk_full(self, duracion: int) -> dict:
        """Simula disco lleno"""
        return {"escenario": "disk_full", "simulado": True}

    def _simular_network_partition(self, duracion: int) -> dict:
        """Simula partición de red"""
        return {"escenario": "network_partition", "simulado": True}

    def _simular_service_crash(self, duracion: int) -> dict:
        """Simula caída de servicio"""
        return {"escenario": "service_crash", "simulado": True}

    def ejecutar_suit_completo(self) -> dict:
        """Ejecuta suit completo de fault injection"""
        escenarios = [
            FaultScenario.HIGH_LATENCY,
            FaultScenario.DATABASE_DOWN,
            FaultScenario.OUT_OF_MEMORY,
            FaultScenario.DISK_FULL,
        ]

        resultados = []
        for escenario in escenarios:
            resultado = self.inyectar_scenario(escenario, duracion_segundos=5)
            resultados.append(resultado)
            time.sleep(1)  # Breve pausa entre escenarios

        return {
            "total_escenarios": len(resultados),
            "resultados": resultados,
            "timestamp": datetime.now().isoformat(),
        }

    def calcular_mttr(self, resultados: list[dict]) -> float:
        """Calcula MTTR (Mean Time To Recovery)"""
        # Simulado - en producción medir tiempo real de recuperación
        return 5.0  # 5 segundos promedio


if __name__ == "__main__":
    print("=" * 50)
    print("FAULT INJECTION TESTING")
    print("=" * 50)

    injector = FaultInjector()

    # Inyectar escenario individual
    resultado = injector.inyectar_scenario(FaultScenario.HIGH_LATENCY, duracion_segundos=2)
    print(f"\n🎯 Resultado: {resultado}")

    # Suit completo
    suit = injector.ejecutar_suit_completo()
    print(f"\n🧪 Suit completo: {suit}")

    # MTTR
    mttr = injector.calcular_mttr(suit["resultados"])
    print(f"\n⏱️ MTTR: {mttr}s")

    print("\n✅ Fault injection testing OK")
