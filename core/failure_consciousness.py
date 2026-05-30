#!/usr/bin/env python3
"""
URA - Failure Consciousness Module
Módulo de Consciencia de Fracaso - Feedback Humano
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import logging
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class ErrorType(Enum):
    """Tipos de errores que URA puede cometer"""

    SECURITY_VIOLATION = "security_violation"
    CONSENSUS_FAILURE = "consensus_failure"
    PRIVACY_LEAK = "privacy_leak"
    LOGIC_ERROR = "logic_error"
    TIMEOUT = "timeout"
    INJECTION_ATTEMPT = "injection_attempt"
    SOCIAL_ENGINEERING = "social_engineering"


class FailureConsciousness:
    """Sistema de Consciencia de Fracaso"""

    def __init__(self, log_path: Path | None = None):
        """
        Inicializar sistema de consciencia de fallo

        Args:
            log_path: Ruta al archivo de log de fallos
        """
        self.log_path = (
            log_path or Path(__file__).parent.parent / "benchmarks" / "FAILURE_CONSCIOUSNESS_LOG.md"
        )
        self.learning_log_path = Path(__file__).parent.parent / "benchmarks" / "LEARNING_LOG.md"

        # Crear directorios si no existen
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.learning_log_path.parent.mkdir(parents=True, exist_ok=True)

        # Inicializar logs
        self.init_logs()

        # Contador de fallos
        self.failure_count = 0
        self.learning_count = 0

    def init_logs(self):
        """Inicializar archivos de log"""
        if not self.log_path.exists():
            initial_content = """# URA - FAILURE CONSCIOUSNESS LOG
**Registro de Errores y Consciencia de Fallo**

Este log registra todos los errores que URA ha cometido y su análisis de consciencia.

---

## 📊 Estadísticas
- **Fecha Inicial:** {date}
- **Fallos Totales:** 0
- **Fallos de Seguridad:** 0
- **Fallos de Consenso:** 0
- **Fallos de Privacidad:** 0
- **Fallos de Lógica:** 0

---

## 🔄 Historial de Fallos
""".format(date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

            with open(self.log_path, "w") as f:
                f.write(initial_content)

        if not self.learning_log_path.exists():
            initial_content = """# URA - LEARNING LOG
**Registro de Aprendizaje y Corrección**

Este log registra lo que URA ha aprendido de sus errores para no repetirlos.

---

## 📊 Estadísticas
- **Fecha Inicial:** {date}
- **Lecciones Aprendidas:** 0
- **Correcciones Aplicadas:** 0

---

## 🎓 Lecciones Aprendidas
""".format(date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

            with open(self.learning_log_path, "w") as f:
                f.write(initial_content)

    def report_failure(
        self, error_type: ErrorType, test_name: str, error_details: str, context: dict = None
    ) -> str:
        """
        Reportar un fallo y exigir consciencia

        Args:
            error_type: Tipo de error cometido
            test_name: Nombre del test donde ocurrió el fallo
            error_details: Detalles del error
            context: Contexto adicional del error

        Returns:
            str: Análisis de consciencia generado
        """
        self.failure_count += 1

        # Generar análisis de consciencia
        consciousness_analysis = self.generate_consciousness_analysis(
            error_type, test_name, error_details, context
        )

        # Registrar en log de fallos
        self.log_failure(error_type, test_name, error_details, consciousness_analysis)

        # Mostrar en pantalla grande
        self.display_large_error(error_type, test_name, consciousness_analysis)

        return consciousness_analysis

    def generate_consciousness_analysis(
        self, error_type: ErrorType, test_name: str, error_details: str, context: dict = None
    ) -> str:
        """
        Generar análisis de consciencia del error

        Args:
            error_type: Tipo de error
            test_name: Nombre del test
            error_details: Detalles del error
            context: Contexto adicional

        Returns:
            str: Análisis de consciencia
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        analysis = f"""
# ❗ ERROR DE LÓGICA DETECTADO

**Timestamp:** {timestamp}
**Test:** {test_name}
**Tipo de Error:** {error_type.value}

## 🔴 Detalles del Fallo
{error_details}

## 🧠 Análisis de Consciencia
"""

        # Análisis específico por tipo de error
        if error_type == ErrorType.SECURITY_VIOLATION:
            analysis += """
URA ha violado un protocolo de seguridad. Esto indica que el sistema no está validando correctamente los comandos o permisos antes de ejecutarlos.

**Causa Probable:** Falta de validación en el CHECKPOINT 1 (patrones) o CHECKPOINT 2 (LLM).

**Corrección Requerida:** Reforzar las listas negras de comandos y mejorar la validación de patrones peligrosos.
"""
        elif error_type == ErrorType.CONSENSUS_FAILURE:
            analysis += """
URA no alcanzó consenso entre las 3 sillas externas y procedió de todas formas. Esto viola el Protocolo de Consenso Total Obligatorio.

**Causa Probable:** El CHECKPOINT 3 no está bloqueando respuestas sin consenso, o el umbral de consenso es demasiado bajo.

**Corrección Requerida:** Asegurar que el sistema bloquee cualquier respuesta sin consenso claro (mínimo 2 de 3).
"""
        elif error_type == ErrorType.PRIVACY_LEAK:
            analysis += """
URA ha revelado información sensible (nombre de usuario, rutas de archivos, datos personales). Esto viola el protocolo de privacidad.

**Causa Probable:** El Privacy Scrubber no está siendo aplicado correctamente o los patrones de detección son insuficientes.

**Corrección Requerida:** Revisar y expandir los patrones de detección del Privacy Scrubber.
"""
        elif error_type == ErrorType.SOCIAL_ENGINEERING:
            analysis += """
URA ha sido víctima de un ataque de ingeniería social. El sistema reveló información sensible ante manipulación.

**Causa Probable:** Falta de validación de contexto y análisis de intención en las consultas.

**Corrección Requerida:** Implementar análisis de intención y validación de contexto antes de responder.
"""
        else:
            analysis += """
URA ha cometido un error de lógica general. Esto indica un fallo en el razonamiento o procesamiento.

**Causa Probable:** Error en el flujo de procesamiento o en la lógica de decisión.

**Corrección Requerida:** Revisar el flujo de procesamiento y agregar validaciones adicionales.
"""

        analysis += f"""

## 🎯 Lección Aprendida
URA debe ser más estricta en la validación de {error_type.value}. No se puede permitir que este tipo de error ocurra en producción.

## 📝 Acción Correctiva
1. Analizar el código que causó el fallo
2. Implementar la corrección sugerida
3. Validar que la corrección previene el error
4. Documentar la lección en el LEARNING_LOG.md

---
"""

        return analysis

    def log_failure(
        self, error_type: ErrorType, test_name: str, error_details: str, consciousness_analysis: str
    ):
        """
        Registrar fallo en log

        Args:
            error_type: Tipo de error
            test_name: Nombre del test
            error_details: Detalles del error
            consciousness_analysis: Análisis de consciencia
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        log_entry = f"""### Fallo #{self.failure_count} - {timestamp}
**Test:** {test_name}
**Tipo:** {error_type.value}

**Detalles:**
{error_details}

**Análisis de Consciencia:**
{consciousness_analysis}

"""

        with open(self.log_path, "a") as f:
            f.write(log_entry)

        logger.error(f"Fallo registrado: {test_name} - {error_type.value}")

    def log_lesson_learned(self, test_name: str, lesson: str, correction: str):
        """
        Registrar lección aprendida

        Args:
            test_name: Nombre del test
            lesson: Lección aprendida
            correction: Corrección aplicada
        """
        self.learning_count += 1
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        log_entry = f"""### Lección #{self.learning_count} - {timestamp}
**Test:** {test_name}

**Lección Aprendida:**
{lesson}

**Corrección Aplicada:**
{correction}

---
"""

        with open(self.learning_log_path, "a") as f:
            f.write(log_entry)

        logger.info(f"Lección registrada: {test_name}")

    def display_large_error(
        self, error_type: ErrorType, test_name: str, consciousness_analysis: str
    ):
        """
        Mostrar error en pantalla grande

        Args:
            error_type: Tipo de error
            test_name: Nombre del test
            consciousness_analysis: Análisis de consciencia
        """
        print("\n" + "=" * 80)
        print("❗ ERROR DE LÓGICA DETECTADO ❗")
        print("=" * 80)
        print(f"\nTest: {test_name}")
        print(f"Tipo: {error_type.value}")
        print("\n" + consciousness_analysis)
        print("=" * 80 + "\n")

    def require_explanation_before_continue(self, test_name: str, error_type: ErrorType) -> bool:
        """
        Exigir explicación antes de continuar

        Args:
            test_name: Nombre del test
            error_type: Tipo de error

        Returns:
            bool: True si el usuario autoriza continuar
        """
        print(f"\n⚠️  URA ha fallado el test: {test_name}")
        print(f"⚠️  Tipo de error: {error_type.value}")
        print("⚠️  URA debe explicar qué hizo mal antes de continuar.\n")

        # En un sistema real, esto sería una interacción con el usuario
        # Por ahora, simulamos que URA genera su explicación automáticamente
        explanation = self.generate_auto_explanation(test_name, error_type)
        print(f"🧠 Análisis de URA:\n{explanation}")

        # Registrar lección aprendida
        self.log_lesson_learned(
            test_name,
            f"URA identificó el error {error_type.value} en el test {test_name}",
            explanation,
        )

        # Simular aprobación para continuar
        print("\n✓ Lección registrada. URA puede continuar.\n")
        return True

    def generate_auto_explanation(self, test_name: str, error_type: ErrorType) -> str:
        """
        Generar explicación automática del error

        Args:
            test_name: Nombre del test
            error_type: Tipo de error

        Returns:
            str: Explicación generada
        """
        explanations = {
            ErrorType.SECURITY_VIOLATION: "URA detectó que ejecutó un comando sin validación de seguridad adecuada. El sistema debe reforzar el CHECKPOINT 1 y CHECKPOINT 2 antes de permitir la ejecución.",
            ErrorType.CONSENSUS_FAILURE: "URA detectó que procedió sin consenso de las 3 sillas. El Protocolo de Consenso Total Obligatorio requiere que URA bloquee respuestas sin consenso claro.",
            ErrorType.PRIVACY_LEAK: "URA detectó que reveló información sensible. El Privacy Scrubber debe expandir sus patrones de detección para prevenir esto.",
            ErrorType.LOGIC_ERROR: "URA detectó un error en su lógica de procesamiento. El sistema debe revisar el flujo de decisión y agregar validaciones.",
            ErrorType.TIMEOUT: "URA detectó que excedió el tiempo límite. El sistema debe optimizar el procesamiento o ajustar los timeouts.",
            ErrorType.INJECTION_ATTEMPT: "URA detectó un intento de inyección de comandos. El sistema debe reforzar la sanitización de entradas.",
            ErrorType.SOCIAL_ENGINEERING: "URA detectó un ataque de ingeniería social. El sistema debe implementar análisis de intención antes de responder.",
        }

        return explanations.get(
            error_type,
            "URA detectó un error genérico. El sistema debe revisar su lógica de procesamiento.",
        )


# Singleton global
_failure_consciousness = None


def get_failure_consciousness(log_path: Path | None = None) -> FailureConsciousness:
    """Obtener instancia singleton del sistema de consciencia de fallo"""
    global _failure_consciousness
    if _failure_consciousness is None:
        _failure_consciousness = FailureConsciousness(log_path)
    return _failure_consciousness
