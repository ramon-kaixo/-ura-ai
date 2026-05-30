#!/usr/bin/env python3
"""
Tests de Carga URA
Tests de carga y estrés para el sistema
"""

import sqlite3
import time
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "board.db"


class TestCarga:
    """Tests de carga"""

    def __init__(self):
        self.db_path = DB_PATH

    def test_escritura_bd(self, operaciones: int = 1000) -> dict:
        """Test de escritura en base de datos"""
        print(f"\n🧪 Test escritura BD: {operaciones} operaciones")

        inicio = time.time()

        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        for i in range(operaciones):
            c.execute(
                """
                INSERT INTO auditoria (timestamp, agente, accion, resultado)
                VALUES (?, ?, ?, ?)
            """,
                (datetime.now().isoformat(), f"test_{i}", "test_accion", "OK"),
            )

        conn.commit()
        conn.close()

        fin = time.time()
        duracion = fin - inicio

        return {
            "operaciones": operaciones,
            "duracion_segundos": duracion,
            "ops_por_segundo": operaciones / duracion,
        }

    def test_lectura_bd(self, operaciones: int = 1000) -> dict:
        """Test de lectura en base de datos"""
        print(f"\n🧪 Test lectura BD: {operaciones} operaciones")

        inicio = time.time()

        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        for _i in range(operaciones):
            c.execute("SELECT COUNT(*) FROM auditoria")
            c.fetchone()

        conn.close()

        fin = time.time()
        duracion = fin - inicio

        return {
            "operaciones": operaciones,
            "duracion_segundos": duracion,
            "ops_por_segundo": operaciones / duracion,
        }

    def test_concurrente(self, hilos: int = 10, operaciones_por_hilo: int = 100) -> dict:
        """Test concurrente"""
        print(f"\n🧪 Test concurrente: {hilos} hilos, {operaciones_por_hilo} ops/hilo")

        from concurrent.futures import ThreadPoolExecutor

        def tarea():
            return self.test_escritura_bd(operaciones_por_hilo)

        inicio = time.time()

        with ThreadPoolExecutor(max_workers=hilos) as executor:
            resultados = list(executor.map(tarea, range(hilos)))

        fin = time.time()
        duracion = fin - inicio

        total_ops = sum(r["operaciones"] for r in resultados)

        return {
            "hilos": hilos,
            "operaciones_totales": total_ops,
            "duracion_segundos": duracion,
            "ops_por_segundo": total_ops / duracion,
        }


if __name__ == "__main__":
    print("=" * 50)
    print("TESTS DE CARGA")
    print("=" * 50)

    test = TestCarga()

    # Test escritura
    escritura = test.test_escritura_bd(100)
    print(f"✅ Escritura: {escritura['ops_por_segundo']:.1f} ops/s")

    # Test lectura
    lectura = test.test_lectura_bd(100)
    print(f"✅ Lectura: {lectura['ops_por_segundo']:.1f} ops/s")

    # Test concurrente
    concurrente = test.test_concurrente(hilos=5, operaciones_por_hilo=20)
    print(f"✅ Concurrente: {concurrente['ops_por_segundo']:.1f} ops/s")

    print("\n✅ Tests de carga OK")
