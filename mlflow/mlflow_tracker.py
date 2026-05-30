#!/usr/bin/env python3
"""
URA MLflow Tracker - Machine Learning Operations
"""

from datetime import datetime
from typing import Any

import mlflow.pyfunc
import mlflow.sklearn
from core.logging_config import get_logger

import mlflow

logger = get_logger("mlflow_tracker", log_dir="./logs")


class MLflowTracker:
    """Gestor de tracking de modelos con MLflow"""

    def __init__(self, tracking_uri: str = "http://localhost:5000", experiment_name: str = "ura"):
        """
        Inicializar tracker MLflow

        Args:
            tracking_uri: URI de MLflow tracking server
            experiment_name: Nombre del experimento
        """
        try:
            mlflow.set_tracking_uri(tracking_uri)
            mlflow.set_experiment(experiment_name)
            logger.info(f"MLflow tracker inicializado: {experiment_name}")
        except Exception as e:
            logger.error(f"Error inicializando MLflow: {e}")

    def log_ollama_request(
        self,
        model: str,
        prompt: str,
        response: str,
        duration: float,
        metadata: dict[str, Any] = None,
    ):
        """
        Log request de Ollama como run de MLflow

        Args:
            model: Modelo usado
            prompt: Prompt enviado
            response: Respuesta recibida
            duration: Duración del request
            metadata: Metadatos adicionales
        """
        with mlflow.start_run(
            run_name=f"ollama_{model}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        ):
            # Log parámetros
            mlflow.log_param("model", model)
            mlflow.log_param("prompt_length", len(prompt))

            # Log métricas
            mlflow.log_metric("duration_seconds", duration)
            mlflow.log_metric("response_length", len(response))

            # Log metadatos
            if metadata:
                for key, value in metadata.items():
                    mlflow.log_param(f"meta_{key}", str(value))

            # Log artifacts
            with open("prompt.txt", "w") as f:
                f.write(prompt)
            with open("response.txt", "w") as f:
                f.write(response)

            mlflow.log_artifact("prompt.txt")
            mlflow.log_artifact("response.txt")

            logger.info(f"Request Ollama logueado: {model}")

    def log_model_performance(self, model_name: str, metrics: dict[str, float]):
        """
        Log performance de modelo

        Args:
            model_name: Nombre del modelo
            metrics: Métricas del modelo
        """
        with mlflow.start_run(run_name=f"perf_{model_name}"):
            for metric_name, value in metrics.items():
                mlflow.log_metric(metric_name, value)

            logger.info(f"Performance logueada: {model_name}")

    def log_ab_test(
        self,
        experiment_name: str,
        variant_a: str,
        variant_b: str,
        metrics_a: dict[str, float],
        metrics_b: dict[str, float],
    ):
        """
        Log resultados de A/B test

        Args:
            experiment_name: Nombre del experimento
            variant_a: Nombre de variante A
            variant_b: Nombre de variante B
            metrics_a: Métricas de variante A
            metrics_b: Métricas de variante B
        """
        mlflow.set_experiment(experiment_name)

        # Log variante A
        with mlflow.start_run(run_name=f"ab_test_{variant_a}"):
            mlflow.log_param("variant", variant_a)
            for metric_name, value in metrics_a.items():
                mlflow.log_metric(metric_name, value)

        # Log variante B
        with mlflow.start_run(run_name=f"ab_test_{variant_b}"):
            mlflow.log_param("variant", variant_b)
            for metric_name, value in metrics_b.items():
                mlflow.log_metric(metric_name, value)

        logger.info(f"A/B test logueado: {experiment_name}")

    def get_best_model(self, metric_name: str) -> str | None:
        """
        Obtener mejor modelo basado en métrica

        Args:
            metric_name: Nombre de la métrica
        """
        try:
            experiment = mlflow.get_experiment_by_name("ura")
            runs = mlflow.search_runs(experiment_ids=[experiment.experiment_id])

            if runs:
                # Ordenar por métrica
                sorted_runs = sorted(
                    runs, key=lambda x: x.data.metrics.get(metric_name, 0), reverse=True
                )
                return sorted_runs[0].info.run_id

            return None
        except Exception as e:
            logger.error(f"Error obteniendo mejor modelo: {e}")
            return None


# Instancia global
mlflow_tracker = MLflowTracker()


if __name__ == "__main__":
    # Test MLflow tracker
    tracker = MLflowTracker()

    # Test log ollama request
    tracker.log_ollama_request(
        model="llama3.2:1b",
        prompt="Hola URA",
        response="Hola, ¿en qué puedo ayudarte?",
        duration=2.5,
        metadata={"user": "test_user"},
    )

    # Test log model performance
    tracker.log_model_performance(
        model_name="llama3.2:1b", metrics={"accuracy": 0.95, "latency": 1.2}
    )

    # Test A/B test
    tracker.log_ab_test(
        experiment_name="ab_test_models",
        variant_a="qwen2.5:7b",
        variant_b="qwen2.5:3b",
        metrics_a={"accuracy": 0.95, "latency": 2.5},
        metrics_b={"accuracy": 0.90, "latency": 1.0},
    )
