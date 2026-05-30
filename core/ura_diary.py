#!/usr/bin/env python3
"""
Diario de URA - Nivel 1

URA mantiene un diario autónomo:
- Escribe cada noche
- Lee cada mañana
- Mantiene contexto temporal
"""

import datetime
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DIARY_PATH = Path("logs/ura_diary.jsonl")


class URAdiary:
    """Diario autónomo de URA — escribe cada noche, lee cada mañana."""

    def __init__(self) -> None:
        """Inicializar diario."""
        self.diary_path = DIARY_PATH
        self.diary_path.parent.mkdir(parents=True, exist_ok=True)

    def escribir_entrada_diaria(self) -> dict[str, Any]:
        """Genera y guarda la entrada del día."""
        hoy = datetime.date.today().isoformat()

        try:
            from core.semantic_memory import semantic_memory_manager

            memorias = semantic_memory_manager.search(
                "conversación tarea error reparación", limit=20
            )
            resumen_memorias = [m.get("texto", "") for m in memorias]
        except Exception:
            resumen_memorias = []

        entrada: dict[str, Any] = {
            "fecha": hoy,
            "hora": datetime.datetime.now().isoformat(),
            "memorias_del_dia": resumen_memorias[:10],
            "pendientes": [],
            "aprendizajes": [],
        }

        with open(self.diary_path, "a") as f:
            f.write(json.dumps(entrada, ensure_ascii=False) + "\n")

        logger.info(f"Diario escrito: {hoy}")
        return {"ok": True, "fecha": hoy}

    def leer_ultima_entrada(self) -> dict[str, Any]:
        """Lee la última entrada del diario para contexto de arranque."""
        if not self.diary_path.exists():
            return {"ok": False, "error": "Sin diario previo"}
        try:
            lineas = self.diary_path.read_text().strip().split("\n")
            ultima = json.loads(lineas[-1])
            return {"ok": True, "entrada": ultima}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def contexto_para_arranque(self) -> str:
        """Genera texto de contexto para incluir en el system prompt."""
        entrada = self.leer_ultima_entrada()
        if not entrada["ok"]:
            return ""
        e = entrada["entrada"]
        return f"""
MEMORIA DEL DÍA ANTERIOR ({e["fecha"]}):
- Conversaciones recordadas: {len(e["memorias_del_dia"])}
- Pendientes: {", ".join(e["pendientes"]) if e["pendientes"] else "ninguno"}
"""


# Singleton
_ura_diary: URAdiary | None = None


def get_ura_diary() -> URAdiary:
    """Obtener el singleton de diario de URA."""
    global _ura_diary
    if _ura_diary is None:
        _ura_diary = URAdiary()
    return _ura_diary
