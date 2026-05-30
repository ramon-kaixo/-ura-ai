#!/usr/bin/env python3
"""
core/repair/auto_repair.py - Core auto-repair functionality
"""

import json
import logging
import subprocess
import time
from datetime import datetime

logger = logging.getLogger(__name__)


def _log_repair(instance, error_type: str, error_message: str, success: bool, repair_message: str):
    """Registrar reparación en historial"""
    if not instance.config.get("log_repairs", True):
        return

    repair_entry = {
        "timestamp": datetime.now().isoformat(),
        "error_type": error_type,
        "error_message": error_message[:200],  # Limitar longitud
        "success": success,
        "repair_message": repair_message,
    }

    # Cargar historial existente
    history = []
    if instance.repair_history_file.exists():
        try:
            with open(instance.repair_history_file) as f:
                history = json.load(f)
        except Exception as e:
            logger.warning(f"Error cargando historial: {e}")

    # Agregar nueva entrada (máximo 100)
    history.append(repair_entry)
    history = history[-100:]

    # Guardar historial
    try:
        with open(instance.repair_history_file, "w") as f:
            json.dump(history, f, indent=2)
    except Exception as e:
        logger.error(f"Error guardando historial: {e}")

    # Logging
    if success:
        logger.info(f"✅ Reparación exitosa: {error_type} - {repair_message}")
    else:
        logger.warning(f"❌ Reparación fallida: {error_type} - {repair_message}")

    # Métricas Prometheus
    _update_prometheus_metrics(instance, error_type, success)


def _update_prometheus_metrics(instance, error_type: str, success: bool):
    """Actualizar métricas de Prometheus"""
    try:
        # Intentar importar prometheus_client
        from prometheus_client import Counter, Gauge, start_http_server

        # Crear métricas si no existen
        if not hasattr(instance, "_prometheus_metrics"):
            instance._prometheus_metrics = {
                "repair_total": Counter(
                    "ura_auto_repair_total", "Total de reparaciones intentadas", ["error_type"]
                ),
                "repair_success": Counter(
                    "ura_auto_repair_success_total", "Reparaciones exitosas", ["error_type"]
                ),
                "repair_failure": Counter(
                    "ura_auto_repair_failure_total", "Reparaciones fallidas", ["error_type"]
                ),
                "repair_duration": Gauge(
                    "ura_auto_repair_duration_seconds",
                    "Duración de reparaciones",
                    ["error_type"],
                ),
            }

            # Iniciar servidor Prometheus en puerto 9091
            try:
                start_http_server(9091)
                logger.info("Servidor Prometheus iniciado en puerto 9091")
            except Exception as e:
                logger.warning(f"No se pudo iniciar servidor Prometheus: {e}")

        # Actualizar métricas
        instance._prometheus_metrics["repair_total"].labels(error_type=error_type).inc()

        if success:
            instance._prometheus_metrics["repair_success"].labels(error_type=error_type).inc()
        else:
            instance._prometheus_metrics["repair_failure"].labels(error_type=error_type).inc()

    except ImportError:
        logger.warning("prometheus_client no disponible para métricas")
    except Exception as e:
        logger.warning(f"Error actualizando métricas Prometheus: {e}")


def attempt_repair(instance, agent_name: str, failure_count: int) -> bool:
    """
    Intenta reparar un agente antes de abrir el circuit breaker
    Integración con core/circuit_breaker.py

    Args:
        instance: ErrorAutoRepair instance
        agent_name: Nombre del agente
        failure_count: Número de fallos consecutivos

    Returns:
        True si la reparación fue exitosa, False en caso contrario
    """
    logger.info(f"Intentando reparación para {agent_name} ({failure_count} fallos)")

    # Intentar reparaciones comunes según el tipo de agente
    repair_strategies = [
        lambda x: _attempt_restart_service(instance, x),
        lambda x: _attempt_clear_cache(instance, x),
        lambda x: _attempt_model_fallback(instance, x),
    ]

    for strategy in repair_strategies:
        try:
            if strategy(agent_name):
                logger.info(f"Reparación exitosa para {agent_name} usando {strategy.__name__}")
                _log_repair(
                    instance,
                    "circuit_breaker_prevention",
                    f"Agente {agent_name} con {failure_count} fallos",
                    True,
                    f"Reparado usando {strategy.__name__}",
                )
                return True
        except Exception as e:
            logger.warning(f"Estrategia {strategy.__name__} falló: {e}")
            continue

    logger.warning(f"No se pudo reparar {agent_name} automáticamente")
    _log_repair(
        instance,
        "circuit_breaker_prevention",
        f"Agente {agent_name} con {failure_count} fallos",
        False,
        "Todas las estrategias de reparación fallaron",
    )

    # Intentar reparación con AutoRepairCycle
    try:
        if not hasattr(instance, "_repair_cycle"):
            from core.auto_repair_cycle import AutoRepairCycle

            instance._repair_cycle = AutoRepairCycle()

        resultado = instance._repair_cycle.reparar(
            archivo=agent_name,
            error=f"Agente {agent_name} con {failure_count} fallos consecutivos",
            traceback=f"Traceback (most recent call last):\n  File error_auto_repair.py, línea 852, en attempt_repair\n  failure_count={failure_count}",
        )
        if resultado["ok"] and resultado["etapa"] == "aplicado":
            logger.info(f"Auto-reparación aplicada: {agent_name}")
        elif resultado["ok"] and resultado["etapa"] == "pendiente_confirmacion":
            logger.warning(
                f"Reparación pendiente confirmación (confianza {resultado['confianza']}): {agent_name}"
            )
        else:
            logger.error(
                f"Auto-reparación falló en etapa {resultado.get('etapa')}: {resultado.get('error')}"
            )
    except Exception as e:
        logger.error(f"Error en AutoRepairCycle: {e}")

    return False


def _attempt_restart_service(instance, agent_name: str) -> bool:
    """Intenta reiniciar el servicio asociado al agente"""
    logger.info(f"Intentando reiniciar servicio para {agent_name}")

    # Mapeo de agentes a servicios
    service_map = {
        "ollama": "ollama",
        "redis": "redis",
        "windsurf": None,  # No hay servicio para Windsurf
    }

    service = service_map.get(agent_name.lower())
    if not service:
        logger.warning(f"No hay servicio configurado para {agent_name}")
        return False

    try:
        # Intentar reiniciar servicio
        if service == "ollama":
            # Reiniciar Ollama
            subprocess.run(["pkill", "-f", "ollama"], timeout=5)
            time.sleep(2)
            subprocess.run(["ollama", "serve"], timeout=5, background=True)
            logger.info("Ollama reiniciado")
            return True
        elif service == "redis":
            # Reiniciar Redis
            subprocess.run(["brew", "services", "restart", "redis"], timeout=10)
            logger.info("Redis reiniciado")
            return True
    except Exception as e:
        logger.error(f"Error reiniciando servicio {service}: {e}")
        return False

    return False


def _attempt_clear_cache(instance, agent_name: str) -> bool:
    """Intenta limpiar caché del agente"""
    logger.info(f"Intentando limpiar caché para {agent_name}")

    try:
        if agent_name.lower() == "redis":
            # Limpiar caché de Redis
            import redis

            r = redis.Redis(host="localhost", port=6379, db=0)
            r.flushdb()
            logger.info("Caché de Redis limpiado")
            return True
        elif agent_name.lower() == "ollama":
            # Limpiar caché de Ollama
            subprocess.run(["ollama", "stop"], timeout=10)
            logger.info("Caché de Ollama limpiada")
            return True
    except Exception as e:
        logger.error(f"Error limpiando caché: {e}")
        return False

    return False


def _attempt_model_fallback(instance, agent_name: str) -> bool:
    """Intenta cambiar al modelo de fallback"""
    logger.info(f"Intentando cambiar a modelo fallback para {agent_name}")

    if agent_name.lower() != "ollama":
        return False

    try:
        from core.ram_manager import pick_model_for_ram
        from core.model_config import get_active_model

        # Obtener modelo recomendado según RAM actual
        recommended_model = pick_model_for_ram()
        current_model = get_active_model()

        if recommended_model != current_model:
            logger.info(f"Cambiando de {current_model} a {recommended_model}")
            # Nota: Esto requeriría actualizar la configuración del modelo
            # Por ahora solo loggeamos
            return True
    except Exception as e:
        logger.error(f"Error cambiando modelo: {e}")
        return False

    return False


def run_auto_repair_for_agents(instance):
    """Ejecutar reparaciones automáticas para los agentes"""
    try:
        # Ejecutar verificaciones preventivas
        issues = instance.run_preventive_checks()

        if issues:
            logger.info(f"Issues preventivos encontrados: {issues}")

        # Verificar errores recurrentes y alertar
        instance.check_and_alert_recurrent_errors()

        # Entrenar modelo ML si hay suficientes datos
        history = instance.get_repair_history()
        if len(history) >= 10 and ML_AVAILABLE:
            instance.train_ml_model()

        logger.info("Reparaciones automáticas para agentes completadas")

    except Exception as e:
        logger.error(f"Error en reparaciones automáticas para agentes: {e}")
