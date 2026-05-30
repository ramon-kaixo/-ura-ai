#!/usr/bin/env python3
"""
Alertas Proactivas Avanzado URA
Predicción de fallos y alertas inteligentes
"""

import sqlite3
import statistics
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "board.db"


class AlertasProactivasAvanzado:
    """Alertas proactivas avanzadas"""

    def __init__(self):
        self.db_path = DB_PATH

    def predecir_fallo_agente(self, agente: str) -> dict:
        """Predice fallo de un agente basado en tendencias"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        # Obtener métricas últimas 24h
        c.execute(
            """
            SELECT valor, timestamp FROM metricas_agente
            WHERE agente = ? AND metrica = 'tiempo_ejecucion'
            AND timestamp > datetime('now', '-1 day')
            ORDER BY timestamp
        """,
            (agente,),
        )

        valores = [row[0] for row in c.fetchall()]
        conn.close()

        if len(valores) < 10:
            return {"prediccion": "insuficiente_datos", "riesgo": "desconocido"}

        # Calcular tendencia
        if len(valores) >= 3:
            primera_mitad = valores[: len(valores) // 2]
            segunda_mitad = valores[len(valores) // 2 :]

            avg_primera = statistics.mean(primera_mitad)
            avg_segunda = statistics.mean(segunda_mitad)

            tendencia = (avg_segunda - avg_primera) / avg_primera if avg_primera > 0 else 0

            if tendencia > 0.3:  # 30% aumento
                return {"prediccion": "fallo_probable", "riesgo": "alto", "tendencia": tendencia}
            elif tendencia > 0.1:
                return {"prediccion": "fallo_posible", "riesgo": "medio", "tendencia": tendencia}

        return {"prediccion": "estable", "riesgo": "bajo", "tendencia": 0}

    def detectar_anomalia_comportamiento(self, agente: str) -> dict:
        """Detecta anomalías en comportamiento"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        # Tasa de fallos última hora vs última semana
        c.execute(
            """
            SELECT COUNT(*) FROM metricas_agente
            WHERE agente = ? AND exito = FALSE
            AND timestamp > datetime('now', '-1 hour')
        """,
            (agente,),
        )
        fallos_hora = c.fetchone()[0]

        c.execute(
            """
            SELECT COUNT(*) FROM metricas_agente
            WHERE agente = ? AND exito = FALSE
            AND timestamp > datetime('now', '-7 days')
        """,
            (agente,),
        )
        fallos_semana = c.fetchone()[0]

        conn.close()

        # Tasa esperada por hora
        tasa_esperada = fallos_semana / (7 * 24) if fallos_semana > 0 else 0

        if fallos_hora > tasa_esperada * 3:  # 3x tasa esperada
            return {"anomalia": "detectada", "tipo": "aumento_fallos", "severidad": "alta"}
        elif fallos_hora > tasa_esperada * 2:
            return {"anomalia": "detectada", "tipo": "aumento_fallos", "severidad": "media"}

        return {"anomalia": "no_detectada"}

    def correlar_multiples_metricas(self, agente: str) -> dict:
        """Correla múltiples métricas para alertas inteligentes"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        # Tiempo de ejecución vs tasa de fallos
        c.execute(
            """
            SELECT AVG(valor) FROM metricas_agente
            WHERE agente = ? AND metrica = 'tiempo_ejecucion'
            AND timestamp > datetime('now', '-1 day')
        """,
            (agente,),
        )
        avg_tiempo = c.fetchone()[0] or 0

        c.execute(
            """
            SELECT COUNT(*) FROM metricas_agente
            WHERE agente = ? AND exito = FALSE
            AND timestamp > datetime('now', '-1 day')
        """,
            (agente,),
        )
        fallos = c.fetchone()[0]

        conn.close()

        # Si tiempo alto y fallos altos = alerta crítica
        if avg_tiempo > 2.0 and fallos > 5:
            return {
                "correlacion": "tiempo_alto_fallos_altos",
                "alerta": "critica",
                "avg_tiempo": avg_tiempo,
                "fallos": fallos,
            }

        return {"correlacion": "normal"}


if __name__ == "__main__":
    print("=" * 50)
    print("ALERTAS PROACTIVAS AVANZADO")
    print("=" * 50)

    alertas = AlertasProactivasAvanzado()

    # Predicción de fallo
    prediccion = alertas.predecir_fallo_agente("programador")
    print(f"\n🔮 Predicción programador: {prediccion}")

    # Anomalía de comportamiento
    anomalia = alertas.detectar_anomalia_comportamiento("programador")
    print(f"\n📊 Anomalía comportamiento: {anomalia}")

    # Correlación
    correlacion = alertas.correlar_multiples_metricas("programador")
    print(f"\n🔗 Correlación métricas: {correlacion}")

    print("\n✅ Alertas proactivas avanzado OK")
