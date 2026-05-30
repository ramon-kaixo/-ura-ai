#!/usr/bin/env python3
"""
core/repair/root_cause.py - Root cause analysis functionality for auto-repair
"""

import logging
from datetime import datetime

from core.model_config import get_active_model

logger = logging.getLogger(__name__)

# ML availability flag (must match the one in error_auto_repair.py)
try:
    pass

    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False
    logger.warning("scikit-learn no disponible, predicción ML deshabilitada")


def analyze_root_cause_with_llm(instance, error_message: str, error_type: str) -> str:
    """Analizar causa raíz del error usando LLM (Ollama)"""
    try:
        # Intentar usar Ollama para análisis
        import requests

        prompt = f"""
        Analiza la siguiente error y proporciona la causa raíz y recomendaciones:

        Tipo de error: {error_type}
        Mensaje de error: {error_message}

        Proporciona:
        1. Causa raíz probable
        2. Recomendaciones para prevenirlo
        3. Posibles soluciones adicionales

        Responde de forma concisa y técnica.
        """

        # Intentar conectar con Ollama
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={"model": get_active_model(), "prompt": prompt, "stream": False},
            timeout=30,
        )

        if response.status_code == 200:
            result = response.json()
            analysis = result.get("response", "No se pudo obtener análisis")
            logger.info("Análisis de causa raíz completado con LLM")
            return analysis
        else:
            logger.warning("Ollama no respondió correctamente")
            return _get_fallback_root_cause(instance, error_type, error_message)

    except Exception as e:
        logger.warning(f"Error analizando causa raíz con LLM: {e}")
        return _get_fallback_root_cause(instance, error_type, error_message)


def _get_fallback_root_cause(instance, error_type: str, error_message: str) -> str:
    """Obtener análisis de causa raíz fallback (sin LLM)"""
    fallback_causes = {
        "missing_module": "El módulo no está instalado en el entorno virtual o Python path incorrecto",
        "ollama": "El servicio Ollama no está corriendo o no responde en el puerto 11434",
        "redis": "El servicio Redis no está corriendo o hay problemas de conexión",
        "missing_file": "El archivo o directorio no existe o no tiene permisos de acceso",
        "import_error": "Error de importación - posible problema con estructura de módulos o dependencias",
        "permission": "Permisos insuficientes para acceder al recurso",
        "key_error": "Intento de acceder a una clave que no existe en un diccionario",
        "attribute_error": "Intento de acceder a un atributo que no existe en el objeto",
        "type_error": "Operación con tipo de dato incorrecto",
    }

    cause = fallback_causes.get(error_type, "Causa desconocida")
    recommendation = f"Causa: {cause}\nRecomendación: Verificar configuración y dependencias"

    return recommendation


def predict_errors(instance) -> list[str]:
    """Predecir errores probables basado en historial"""
    # Usar ML si está disponible y entrenado
    if ML_AVAILABLE and instance.ml_model and instance.config.get("use_ml_prediction", False):
        return predict_errors_ml(instance)

    # Fallback a predicción basada en reglas
    return predict_errors_rule_based(instance)


def predict_errors_rule_based(instance) -> list[str]:
    """Predecir errores probables basado en reglas (fallback)"""
    history = instance.get_repair_history()
    error_counts = {}
    error_patterns = {}

    for entry in history:
        error_type = entry.get("error_type", "unknown")
        timestamp = entry.get("timestamp", "")

        # Contar ocurrencias
        error_counts[error_type] = error_counts.get(error_type, 0) + 1

        # Analizar patrones temporales (últimas 24 horas)
        try:
            dt = datetime.fromisoformat(timestamp)
            hours_ago = (datetime.now() - dt).total_seconds() / 3600

            if hours_ago <= 24:
                if error_type not in error_patterns:
                    error_patterns[error_type] = []
                error_patterns[error_type].append(hours_ago)
        except Exception:
            pass

    # Predecir errores probables
    predicted = []

    for error_type, count in error_counts.items():
        # Si ocurrió 3+ veces, es probable que ocurra de nuevo
        if count >= 3:
            predicted.append(error_type)

        # Si ocurrió 2+ veces en las últimas 24 horas, es muy probable
        if error_type in error_patterns and len(error_patterns[error_type]) >= 2:
            if error_type not in predicted:
                predicted.append(error_type)

    return sorted(predicted, key=lambda x: error_counts.get(x, 0), reverse=True)


def predict_errors_ml(instance) -> list[str]:
    """Predecir errores probables usando ML"""
    if not ML_AVAILABLE or instance.ml_model is None:
        return predict_errors_rule_based(instance)

    try:
        history = instance.get_repair_history()

        if len(history) < 5:
            return predict_errors_rule_based(instance)

        # Obtener últimos errores
        recent_errors = history[-5:]
        X_texts = [entry.get("error_message", "") for entry in recent_errors]

        # Vectorizar
        X = instance.vectorizer.transform(X_texts)

        # Predecir
        predictions = instance.ml_model.predict(X)
        probabilities = instance.ml_model.predict_proba(X)

        # Decodificar etiquetas
        predicted_types = instance.label_encoder.inverse_transform(predictions)

        # Obtener errores más probables (probabilidad > 0.5)
        likely_errors = []
        for _i, (error_type, prob) in enumerate(zip(predicted_types, probabilities, strict=False)):
            max_prob = prob.max()
            if max_prob > 0.5:
                likely_errors.append(error_type)

        return list(set(likely_errors))  # Eliminar duplicados

    except Exception as e:
        logger.warning(f"Error en predicción ML: {e}")
        return predict_errors_rule_based(instance)
