#!/usr/bin/env python3
"""
Auto-pruning Inteligente de URA

Elimina datos antiguos automáticamente según uso:
- Eliminar datos antiguos según relevancia
- Comprimir datos para reducir espacio en disco
- Priorizar datos más relevantes
"""

import gzip
import json
import logging
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class PruningRule:
    """Regla de pruning."""

    level_name: str
    max_age_days: int
    max_items: int
    compress_after_days: int

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "PruningRule":
        return cls(**data)


class URAAutoPruning:
    """Sistema de auto-pruning inteligente."""

    def __init__(self, config_path: str | Path = None):
        """Inicializar auto-pruning.

        Args:
            config_path: Ruta al directorio de configuración
        """
        if config_path is None:
            config_path = Path.home() / ".ura" / "pruning"
        self.config_path = Path(config_path)
        self.config_path.mkdir(parents=True, exist_ok=True)
        self.rules = self._load_rules()

    def _load_rules(self) -> dict[str, PruningRule]:
        """Cargar reglas desde disco."""
        rules = {}
        rules_file = self.config_path / "rules.json"
        if rules_file.exists():
            try:
                with open(rules_file) as f:
                    data = json.load(f)
                    for rule_data in data.get("rules", []):
                        rule = PruningRule.from_dict(rule_data)
                        rules[rule.level_name] = rule
            except Exception as e:
                logger.error(f"Error cargando reglas: {e}")
        # Si no hay reglas, crear las por defecto
        if not rules:
            rules = self._create_default_rules()

        return rules

    def _create_default_rules(self) -> dict[str, PruningRule]:
        """Crear reglas por defecto."""
        datetime.now().isoformat()

        # Niveles con datos temporales (más agresivo)
        temporal_levels = {
            "emotions": PruningRule(
                "emotions", max_age_days=7, max_items=100, compress_after_days=3
            ),
            "theory_of_mind": PruningRule(
                "theory_of_mind", max_age_days=14, max_items=200, compress_after_days=7
            ),
            "anticipation": PruningRule(
                "anticipation", max_age_days=30, max_items=500, compress_after_days=14
            ),
        }

        # Niveles con datos persistentes (menos agresivo)
        persistent_levels = {
            "personality": PruningRule(
                "personality", max_age_days=365, max_items=1000, compress_after_days=90
            ),
            "value_system": PruningRule(
                "value_system", max_age_days=365, max_items=1000, compress_after_days=90
            ),
            "goals": PruningRule("goals", max_age_days=90, max_items=500, compress_after_days=30),
        }

        return {**temporal_levels, **persistent_levels}

    def _save_rules(self):
        """Guardar reglas a disco."""
        rules_file = self.config_path / "rules.json"
        with open(rules_file, "w") as f:
            json.dump({"rules": [r.to_dict() for r in self.rules.values()]}, f, indent=2)

    def prune_level(self, level_name: str) -> int:
        """Prune un nivel específico. Retorna número de items eliminados."""
        if level_name not in self.rules:
            return 0

        rule = self.rules[level_name]
        data_file = Path.home() / ".ura" / f"{level_name}.json"

        if not data_file.exists():
            return 0

        try:
            with open(data_file) as f:
                data = json.load(f)

            # Identificar items antiguos
            cutoff_date = datetime.now() - timedelta(days=rule.max_age_days)
            items_to_remove = []

            for item in data:
                timestamp_str = item.get("timestamp", "")
                if timestamp_str:
                    try:
                        timestamp = datetime.fromisoformat(timestamp_str)
                        if timestamp < cutoff_date:
                            items_to_remove.append(item)
                    except Exception:
                        pass

            # Eliminar items antiguos
            pruned_count = len(items_to_remove)
            if pruned_count > 0:
                # Guardar backup antes de pruning
                backup_file = (
                    self.config_path
                    / f"{level_name}_backup_{datetime.now().strftime('%Y%m%d')}.json"
                )
                shutil.copy2(data_file, backup_file)

                # Eliminar items
                data = [item for item in data if item not in items_to_remove]

                # Limitar número de items
                if len(data) > rule.max_items:
                    data = data[-rule.max_items :]

                # Guardar datos pruned
                with open(data_file, "w") as f:
                    json.dump(data, f, indent=2)

            # Comprimir si es necesario
            self._compress_if_needed(level_name, data_file, rule)

            return pruned_count
        except Exception as e:
            logger.error(f"Error pruning {level_name}: {e}")
            return 0

    def _compress_if_needed(self, level_name: str, data_file: Path, rule: PruningRule):
        """Comprimir archivo si es antiguo."""
        cutoff_date = datetime.now() - timedelta(days=rule.compress_after_days)

        if data_file.stat().st_mtime < cutoff_date.timestamp():
            # Comprimir archivo
            compressed_file = data_file.with_suffix(".json.gz")

            with open(data_file, "rb") as f_in:
                with gzip.open(compressed_file, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)

            # Reemplazar original con comprimido
            data_file.unlink()
            compressed_file.rename(data_file)

    def prune_all(self) -> dict[str, int]:
        """Prune todos los niveles. Retorna dict con nivel -> items eliminados."""
        results = {}

        for level_name in self.rules:
            results[level_name] = self.prune_level(level_name)

        return results

    def get_pruning_context(self) -> str:
        """Genera contexto de pruning para el system prompt."""
        context_parts = ["AUTO-PRUNING INTELIGENTE:"]
        context_parts.append(f"- Niveles monitoreados: {len(self.rules)}")

        return "\n".join(context_parts) + "\n"


# Singleton
_ura_auto_pruning: URAAutoPruning | None = None


def get_ura_auto_pruning(config_path: str | Path = None) -> URAAutoPruning:
    """Obtener el singleton de auto-pruning de URA."""
    global _ura_auto_pruning
    if _ura_auto_pruning is None:
        _ura_auto_pruning = URAAutoPruning(config_path=config_path)
    return _ura_auto_pruning


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    pruning = get_ura_auto_pruning()

    # Prueba
    results = pruning.prune_all()
    logger.info("Auto-pruning inteligente creado")
    logger.info(f"Pruning results: {results}")
    logger.info(pruning.get_pruning_context())
