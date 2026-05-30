#!/usr/bin/env python3
"""
Módulo: core/code_assistant.py
Propósito: Analiza archivos Python y propone mejoras con ID único para seguimiento.
Dependencias principales: pathlib, datetime, uuid, json
Reglas especiales: Propuestas deben ser idempotentes. No modificar archivos directamente.
"""

import json
import logging
import re
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

CODE_ASSISTANT_PATH = Path.home() / ".ura" / "code_assistant.json"
CODE_ASSISTANT_PATH.parent.mkdir(parents=True, exist_ok=True)
LOG_PATH = Path.home() / ".ura" / "logs"


@dataclass
class ErrorPattern:
    """Patrón de error recurrente."""

    pattern: str
    count: int
    first_seen: str
    last_seen: str
    file: str
    line: int = 0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ErrorPattern":
        return cls(**data)


@dataclass
class ProposedImprovement:
    """Mejora propuesta por el asistente de código."""

    id: str
    error_pattern: str
    description: str
    file: str
    suggested_fix: str
    status: str  # pending, approved, rejected, applied
    timestamp: str

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ProposedImprovement":
        return cls(**data)


class URACodeAssistant:
    """Asistente de código proactivo de URA."""

    def __init__(self):
        self.error_patterns = self._load_error_patterns()
        self.proposed_improvements = self._load_improvements()
        self.threshold = 3  # Errores recurrentes después de N ocurrencias

    def _load_error_patterns(self) -> list[ErrorPattern]:
        """Cargar patrones de error desde disco."""
        patterns = []
        if CODE_ASSISTANT_PATH.exists():
            try:
                with open(CODE_ASSISTANT_PATH) as f:
                    data = json.load(f)
                    patterns = [ErrorPattern.from_dict(p) for p in data.get("error_patterns", [])]
            except Exception as e:
                logger.error(f"Error cargando patrones de error: {e}")
        return patterns

    def _load_improvements(self) -> list[ProposedImprovement]:
        """Cargar mejoras propuestas desde disco."""
        improvements = []
        if CODE_ASSISTANT_PATH.exists():
            try:
                with open(CODE_ASSISTANT_PATH) as f:
                    data = json.load(f)
                    improvements = [
                        ProposedImprovement.from_dict(i) for i in data.get("improvements", [])
                    ]
            except Exception as e:
                logger.error(f"Error cargando mejoras: {e}")
        return improvements

    def _save_data(self):
        """Guardar patrones y mejoras a disco."""
        with open(CODE_ASSISTANT_PATH, "w") as f:
            json.dump(
                {
                    "error_patterns": [p.to_dict() for p in self.error_patterns],
                    "improvements": [i.to_dict() for i in self.proposed_improvements],
                },
                f,
                indent=2,
            )

    def analyze_logs(self, log_file: str = "ura.log") -> list[ErrorPattern]:
        """Analiza logs para detectar errores recurrentes."""
        log_path = LOG_PATH / log_file
        if not log_path.exists():
            logger.warning(f"Log file no encontrado: {log_path}")
            return []

        try:
            with open(log_path, encoding="utf-8") as f:
                lines = f.readlines()

            # Patrones de error comunes
            error_patterns = []
            for i, line in enumerate(lines):
                if "ERROR" in line or "Exception" in line or "Traceback" in line:
                    # Extraer patrón de error (simplificado)
                    error_match = re.search(r"(ERROR|Exception|Traceback).*?:\s*(.+)", line)
                    if error_match:
                        pattern = error_match.group(2)[:100]  # Primeros 100 caracteres
                        error_patterns.append(pattern)

            # Contar patrones recurrentes
            pattern_counts = Counter(error_patterns)

            # Actualizar patrones conocidos
            current_time = datetime.now().isoformat()
            for pattern, count in pattern_counts.items():
                existing = next((p for p in self.error_patterns if p.pattern == pattern), None)
                if existing:
                    existing.count += count
                    existing.last_seen = current_time
                else:
                    self.error_patterns.append(
                        ErrorPattern(
                            pattern=pattern,
                            count=count,
                            first_seen=current_time,
                            last_seen=current_time,
                            file=log_file,
                        )
                    )

            self._save_data()

            # Retornar patrones que superan el umbral
            recurrent = [p for p in self.error_patterns if p.count >= self.threshold]
            return recurrent

        except Exception as e:
            logger.error(f"Error analizando logs: {e}")
            return []

    def propose_improvement(self, error_pattern: ErrorPattern) -> ProposedImprovement:
        """Propone una mejora para un patrón de error recurrente."""
        import uuid

        improvement_id = f"improvement_{datetime.now().timestamp()}_{uuid.uuid4().hex[:8]}"

        # Generar sugerencia de mejora (simplificada)
        suggested_fix = f"Revisar el código relacionado con: {error_pattern.pattern}. Añadir validación o manejo de excepciones."

        improvement = ProposedImprovement(
            id=improvement_id,
            error_pattern=error_pattern.pattern,
            description=f"Error recurrente detectado ({error_pattern.count} veces)",
            file=error_pattern.file,
            suggested_fix=suggested_fix,
            status="pending",
            timestamp=datetime.now().isoformat(),
        )

        self.proposed_improvements.append(improvement)
        self._save_data()

        logger.info(f"Mejora propuesta: {improvement_id}")
        return improvement

    def approve_improvement(self, improvement_id: str) -> bool:
        """Aprueba una mejora y la aplica usando OpenCode."""
        improvement = next((i for i in self.proposed_improvements if i.id == improvement_id), None)
        if not improvement:
            return False

        improvement.status = "approved"
        self._save_data()

        # Aplicar mejora usando OpenCode
        try:
            from connectors.opencode_connector import OpenCodeConnector

            connector = OpenCodeConnector()

            # Construir prompt para OpenCode
            prompt = f"""
Aplica esta mejora de código:

Error recurrente: {improvement.error_pattern}
Archivo: {improvement.file}
Sugerencia: {improvement.suggested_fix}

Instrucciones:
1. Lee el archivo relevante
2. Aplica la corrección sugerida
3. Verifica que el código compile y funcione
4. Si hay errores, revierte los cambios

Responde con "APPLIED" si se aplicó correctamente, o "FAILED: <razón>" si falló.
"""

            result = connector.execute(prompt)

            if "APPLIED" in str(result):
                improvement.status = "applied"
                self._save_data()
                logger.info(f"Mejora aplicada: {improvement_id}")
                return True
            else:
                improvement.status = "rejected"
                self._save_data()
                logger.warning(f"Mejora rechazada por OpenCode: {improvement_id}")
                return False

        except Exception as e:
            logger.error(f"Error aplicando mejora con OpenCode: {e}")
            improvement.status = "rejected"
            self._save_data()
            return False

    def reject_improvement(self, improvement_id: str) -> bool:
        """Rechaza una mejora propuesta."""
        improvement = next((i for i in self.proposed_improvements if i.id == improvement_id), None)
        if not improvement:
            return False

        improvement.status = "rejected"
        self._save_data()
        logger.info(f"Mejora rechazada por usuario: {improvement_id}")
        return True

    def get_pending_improvements(self) -> list[ProposedImprovement]:
        """Obtener mejoras pendientes de aprobación."""
        return [i for i in self.proposed_improvements if i.status == "pending"]

    def get_error_summary(self) -> dict:
        """Obtener resumen de errores recurrentes."""
        return {
            "total_patterns": len(self.error_patterns),
            "recurrent_patterns": len(
                [p for p in self.error_patterns if p.count >= self.threshold]
            ),
            "pending_improvements": len(self.get_pending_improvements()),
            "applied_improvements": len(
                [i for i in self.proposed_improvements if i.status == "applied"]
            ),
        }


# Singleton
_code_assistant: URACodeAssistant | None = None


def get_code_assistant() -> URACodeAssistant:
    """Obtener el singleton del asistente de código de URA."""
    global _code_assistant
    if _code_assistant is None:
        _code_assistant = URACodeAssistant()
    return _code_assistant


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    assistant = get_code_assistant()

    print("Asistente de código proactivo creado")
    print(assistant.get_error_summary())
