#!/usr/bin/env python3
"""
Auto-mejora de código de URA - Nivel 18

URA mejora su propio código automáticamente:
- Detección y corrección de bugs propios
- Optimización de rendimiento autónoma
"""

import json
import logging
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

SELF_IMPROVEMENT_PATH = Path.home() / ".ura" / "self_improvement.json"
SELF_IMPROVEMENT_PATH.parent.mkdir(parents=True, exist_ok=True)


@dataclass
class Improvement:
    """Mejora de código."""

    file: str
    issue: str  # bug, optimization, refactor
    description: str
    status: str  # pending, applied, rejected
    timestamp: str
    snapshot_id: str = ""  # ID del snapshot antes de aplicar la mejora

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Improvement":
        return cls(**data)


class URASelfImprovement:
    """Gestor de auto-mejora de código de URA."""

    def __init__(self):
        self.improvements = self._load_improvements()

    def _load_improvements(self) -> list[Improvement]:
        """Cargar mejoras desde disco."""
        improvements = []
        if SELF_IMPROVEMENT_PATH.exists():
            try:
                with open(SELF_IMPROVEMENT_PATH) as f:
                    data = json.load(f)
                    improvements = [Improvement.from_dict(i) for i in data.get("improvements", [])]
            except Exception as e:
                logger.error(f"Error cargando mejoras: {e}")
        return improvements

    def _save_improvements(self):
        """Guardar mejoras a disco."""
        with open(SELF_IMPROVEMENT_PATH, "w") as f:
            json.dump({"improvements": [i.to_dict() for i in self.improvements]}, f, indent=2)

    def detect_issue(self, file: str, issue: str, description: str):
        """Detectar un problema en el código."""
        improvement = Improvement(
            file=file,
            issue=issue,
            description=description,
            status="pending",
            timestamp=datetime.now().isoformat(),
        )

        self.improvements.append(improvement)

        # Mantener solo últimas 50 mejoras
        if len(self.improvements) > 50:
            self.improvements = self.improvements[-50:]

        self._save_improvements()


def apply_improvement(self, improvement_id: int) -> bool:
    """Aplicar una mejora usando OpenClaw."""
    if not _validate_improvement_index(improvement_id):
        return False

    improvement = self.improvements[improvement_id]

    rollback = _create_rollback_snapshot(improvement)
    prompt = _build_openclaw_prompt(improvement)

    try:
        sandbox_result = _run_sandbox()
        if not sandbox_result.get("success"):
            logger.warning(f"Sandbox rechazó la mejora: {sandbox_result.get('error')}")
            return False

        openclaw_output = _execute_openclaw(prompt)
        if "SUCCESS" in openclaw_output:
            test_result = _run_tests()
            if test_result.returncode == 0:
                _mark_improvement_as_applied(improvement)
                return True
            else:
                _restore_snapshot_and_mark_failure(improvement, rollback)
        else:
            _mark_improvement_as_failed(improvement)

    except subprocess.TimeoutExpired:
        logger.error(f"Timeout aplicando mejora: {improvement.file}")
        _mark_improvement_as_failed(improvement)
    except Exception as e:
        logger.error(f"Error aplicando mejora: {e}")
        _mark_improvement_as_failed(improvement)

    return False


def _validate_improvement_index(improvement_id: int) -> bool:
    if improvement_id >= len(self.improvements):
        return False
    return True


def _create_rollback_snapshot(improvement):
    file_path = Path(improvement.file)
    if file_path.exists():
        rollback = get_ura_rollback()
        snapshot_id = rollback.create_snapshot(
            level_name="code_changes",
            data_path=file_path,
            metadata={"file": str(file_path), "improvement": improvement.description},
        )
        improvement.snapshot_id = snapshot_id
        logger.info(f"Snapshot creado antes de mejora: {snapshot_id}")
    return get_ura_rollback()


def _build_openclaw_prompt(improvement):
    prompt = f"""
Aplica esta mejora de código en el archivo {improvement.file}:

Tipo: {improvement.issue}
Descripción: {improvement.description}

Instrucciones:
1. Lee el archivo actual
2. Aplica la mejora descrita
3. Verifica que el código sigue funcionando
4. Si hay errores, revierte los cambios
5. Si tiene éxito, marca la mejora como aplicada

Responde solo con "SUCCESS" si la mejora se aplicó correctamente, o "FAILED: <razón>" si falló.
"""
    return prompt


def _run_sandbox():
    sandbox_orch = get_sandbox_orchestrator()
    return sandbox_orch._run_sandbox("mantenimiento")


def _execute_openclaw(prompt):
    result = subprocess.run(
        ["openclaw", "agent", "--agent", "main", "-m", prompt],
        capture_output=True,
        text=True,
        timeout=120,
    )
    return result.stdout if result.stdout else result.stderr


def _run_tests():
    test_result = subprocess.run(
        ["pytest", "tests/", "-q"], capture_output=True, text=True, timeout=300
    )
    return test_result


def _mark_improvement_as_applied(improvement):
    improvement.status = "applied"
    improvement.timestamp = datetime.now().isoformat()
    self._save_improvements()
    logger.info(f"Mejora aplicada exitosamente: {improvement.file} - {improvement.description}")


def _restore_snapshot_and_mark_failure(improvement, rollback):
    if improvement.snapshot_id:
        restored = rollback.restore_snapshot(improvement.snapshot_id, "code_changes")
        if restored:
            logger.info(f"Snapshot restaurado: {improvement.snapshot_id}")
        else:
            logger.error(f"No se pudo restaurar snapshot: {improvement.snapshot_id}")

    _mark_improvement_as_failed(improvement)


def _mark_improvement_as_failed(improvement):
    improvement.status = "failed"
    improvement.timestamp = datetime.now().isoformat()
    self._save_improvements()
    logger.warning(f"Mejora falló: {improvement.file} - {improvement.description}")

    def get_improvement_context(self) -> str:
        """Genera contexto de auto-mejora para el system prompt."""
        pending = [i for i in self.improvements if i.status == "pending"]

        if not pending:
            return ""

        context_parts = ["AUTO-MEJORA DE CÓDIGO:"]
        for imp in pending[:3]:
            context_parts.append(f"- {imp.file}: {imp.description} ({imp.issue})")

        return "\n".join(context_parts) + "\n"


# Singleton
_ura_self_improvement: URASelfImprovement | None = None


def get_ura_self_improvement() -> URASelfImprovement:
    """Obtener el singleton de auto-mejora de código de URA."""
    global _ura_self_improvement
    if _ura_self_improvement is None:
        _ura_self_improvement = URASelfImprovement()
    return _ura_self_improvement


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    self_improvement = get_ura_self_improvement()

    # Prueba
    self_improvement.detect_issue(
        "core/ura_diary.py", "optimization", "Reducir tiempo de escritura de diario"
    )
    print("Auto-mejora de código creada")
    print(self_improvement.get_improvement_context())
