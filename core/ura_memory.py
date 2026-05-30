#!/usr/bin/env python3
"""
Memoria de URA - Capa 1: Memoria del usuario

URA recuerda:
- Preferencias del usuario
- Rutinas diarias
- Historial de decisiones
- Proyectos activos
"""

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

MEMORY_DIR = Path.home() / ".ura" / "memory"
MEMORY_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class UserPreferences:
    """Preferencias del usuario."""

    response_style: str = "direct"  # direct, detailed, casual
    language: str = "spanish"
    verbosity: str = "medium"  # low, medium, high
    code_preference: str = "python"  # python, bash, auto
    timezone: str = "Europe/Madrid"
    work_hours: str = "09:00-18:00"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UserPreferences":
        return cls(**data)


@dataclass
class DailyRoutine:
    """Rutina diaria del usuario."""

    morning_tasks: list[str] = field(default_factory=list)
    afternoon_tasks: list[str] = field(default_factory=list)
    evening_tasks: list[str] = field(default_factory=list)
    frequent_commands: list[str] = field(default_factory=list)
    frequent_questions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DailyRoutine":
        return cls(**data)


@dataclass
class DecisionRecord:
    """Registro de decisiones del usuario."""

    date: str
    decision: str
    outcome: str
    success: bool
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DecisionRecord":
        return cls(**data)


@dataclass
class ActiveProject:
    """Proyecto activo del usuario."""

    name: str
    description: str
    status: str  # active, paused, completed
    priority: str  # high, medium, low
    last_worked: str
    next_steps: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ActiveProject":
        return cls(**data)


class UserMemory:
    """Memoria del usuario - Capa 1."""

    def __init__(self) -> None:
        self.preferences_file = MEMORY_DIR / "preferences.json"
        self.routine_file = MEMORY_DIR / "routine.json"
        self.decisions_file = MEMORY_DIR / "decisions.jsonl"
        self.projects_file = MEMORY_DIR / "projects.json"

        self.preferences = self._load_preferences()
        self.routine = self._load_routine()
        self.decisions = self._load_decisions()
        self.projects = self._load_projects()

    def _load_preferences(self) -> UserPreferences:
        """Cargar preferencias del usuario."""
        if self.preferences_file.exists():
            try:
                with open(self.preferences_file) as f:
                    data = json.load(f)
                    return UserPreferences.from_dict(data)
            except Exception as e:
                logger.error(f"Error cargando preferencias: {e}")
        return UserPreferences()

    def _load_routine(self) -> DailyRoutine:
        """Cargar rutina diaria."""
        if self.routine_file.exists():
            try:
                with open(self.routine_file) as f:
                    data = json.load(f)
                    return DailyRoutine.from_dict(data)
            except Exception as e:
                logger.error(f"Error cargando rutina: {e}")
        return DailyRoutine()

    def _load_decisions(self) -> list[DecisionRecord]:
        """Cargar historial de decisiones."""
        decisions = []
        if self.decisions_file.exists():
            try:
                with open(self.decisions_file) as f:
                    for line in f:
                        if line.strip():
                            data = json.loads(line)
                            decisions.append(DecisionRecord.from_dict(data))
            except Exception as e:
                logger.error(f"Error cargando decisiones: {e}")
        return decisions

    def _load_projects(self) -> list[ActiveProject]:
        """Cargar proyectos activos."""
        projects = []
        if self.projects_file.exists():
            try:
                with open(self.projects_file) as f:
                    data = json.load(f)
                    projects = [ActiveProject.from_dict(p) for p in data]
            except Exception as e:
                logger.error(f"Error cargando proyectos: {e}")
        return projects

    def save_preferences(self) -> None:
        """Guardar preferencias."""
        with open(self.preferences_file, "w") as f:
            json.dump(self.preferences.to_dict(), f, indent=2)

    def save_routine(self) -> None:
        """Guardar rutina."""
        with open(self.routine_file, "w") as f:
            json.dump(self.routine.to_dict(), f, indent=2)

    def add_decision(self, decision: str, outcome: str, success: bool, notes: str = "") -> None:
        """Añadir decisión al historial."""
        record = DecisionRecord(
            date=date.today().isoformat(),
            decision=decision,
            outcome=outcome,
            success=success,
            notes=notes,
        )
        self.decisions.append(record)
        with open(self.decisions_file, "a") as f:
            f.write(json.dumps(record.to_dict()) + "\n")

    def add_project(self, name: str, description: str, priority: str = "medium") -> None:
        """Añadir proyecto activo."""
        project = ActiveProject(
            name=name,
            description=description,
            status="active",
            priority=priority,
            last_worked=date.today().isoformat(),
        )
        self.projects.append(project)
        self._save_projects()

    def update_project(self, name: str, **kwargs) -> None:
        """Actualizar proyecto existente."""
        for project in self.projects:
            if project.name == name:
                for key, value in kwargs.items():
                    setattr(project, key, value)
                self._save_projects()
                break

    def _save_projects(self) -> None:
        """Guardar proyectos."""
        with open(self.projects_file, "w") as f:
            json.dump([p.to_dict() for p in self.projects], f, indent=2)

    def get_summary_for_prompt(self) -> str:
        """Obtener resumen para el system prompt."""
        summary_parts = []

        # Preferencias
        summary_parts.append(
            f"👤 Preferencias: estilo {self.preferences.response_style}, idioma {self.preferences.language}"
        )

        # Proyectos activos
        active_projects = [p for p in self.projects if p.status == "active"]
        if active_projects:
            projects_str = ", ".join([p.name for p in active_projects[:3]])
            summary_parts.append(f"📁 Proyectos activos: {projects_str}")

        # Rutinas frecuentes
        if self.routine.frequent_questions:
            questions_str = ", ".join(self.routine.frequent_questions[:2])
            summary_parts.append(f"❓ Preguntas frecuentes: {questions_str}")

        # Decisiones recientes
        recent_decisions = [d for d in self.decisions if d.date == date.today().isoformat()]
        if recent_decisions:
            decisions_str = ", ".join([d.decision for d in recent_decisions[:2]])
            summary_parts.append(f"🎯 Decisiones hoy: {decisions_str}")

        return " | ".join(summary_parts)


# Singleton
_ura_memory: UserMemory | None = None


def get_ura_memory() -> UserMemory:
    """Obtener el singleton de memoria de URA."""
    global _ura_memory
    if _ura_memory is None:
        _ura_memory = UserMemory()
    return _ura_memory


# Alias para compatibilidad
def get_user_memory() -> UserMemory:
    """Obtener el singleton de memoria del usuario (alias de get_ura_memory)."""
    return get_ura_memory()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    memory = get_user_memory()

    # Prueba
    memory.add_project("URA_App", "Aplicación principal de URA", priority="high")
    memory.add_decision(
        "Usar Ollama como modelo principal", "Modelo estable y rápido", success=True
    )

    print("Memoria de usuario creada")
    print(memory.get_summary_for_prompt())
