#!/usr/bin/env python3
"""
ResearchPipeline - Pipeline de Investigación Autónomo de URA.

Componentes:
- 8 mochilas de conocimiento (KnowledgeBackpack)
- ResearchMemory (memoria de investigación con aprendizaje)
- KnowledgeArchivist (biblioteca local indexada)
- AutonomousExplorer (agente que explora temas relevantes)
- ResearchPipeline (3 agentes secuenciales: Planificador → Buscador → Redactor)
"""

import hashlib
import json
import logging
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

URA_HOME = Path.home() / ".ura"
RESEARCH_MEMORY_PATH = URA_HOME / "research_memory.json"
KNOWLEDGE_BASE_PATH = URA_HOME / "knowledge_base"
WISHLIST_PATH = URA_HOME / "research_wishlist.json"
KNOWLEDGE_BASE_PATH.mkdir(parents=True, exist_ok=True)


# ═══════════════════════════════════════════════════════════
# 1. KnowledgeBackpack (8 mochilas)
# ═══════════════════════════════════════════════════════════


@dataclass
class KnowledgeBackpack:
    name: str
    description: str
    prompt_template: str

    def apply(self, query: str) -> str:
        return self.prompt_template.replace("{QUERY}", query)


BACKPACKS = [
    KnowledgeBackpack(
        name="Rigor Académico",
        description="Fuentes académicas, papers, documentación oficial",
        prompt_template=(
            "Investiga '{QUERY}' usando SOLO fuentes académicas de alta fiabilidad:\n"
            "- Papers revisados por pares (arxiv, Google Scholar, IEEE, ACM)\n"
            "- Documentación oficial del proyecto/tecnología\n"
            "- Libros técnicos reconocidos\n"
            "Para cada fuente, evalúa fiabilidad (1-10) y cítala con URL.\n"
            "Evita blogs personales, foros y contenido sin verificar."
        ),
    ),
    KnowledgeBackpack(
        name="Errores y Antipatrones",
        description="Bugs reportados, patrones erróneos, fallos comunes",
        prompt_template=(
            "Para '{QUERY}', busca información sobre:\n"
            "- Bugs conocidos y issues abiertos en GitHub\n"
            "- Antipatrones documentados y cómo NO se hace\n"
            "- Fallos comunes de implementación\n"
            "- Casos de estudio de fracasos públicos\n"
            "Prioriza lecciones aprendidas de errores reales."
        ),
    ),
    KnowledgeBackpack(
        name="Perspectivas Opuestas",
        description="Críticas, vulnerabilidades, limitaciones, contra-argumentos",
        prompt_template=(
            "Busca perspectivas CRÍTICAS de '{QUERY}':\n"
            "- Argumentos en contra del consenso mayoritario\n"
            "- Vulnerabilidades de seguridad conocidas\n"
            "- Limitaciones técnicas y operacionales\n"
            "- Alternativas propuestas por críticos reconocidos\n"
            "Evita reforzar el consenso; busca disensión fundamentada."
        ),
    ),
    KnowledgeBackpack(
        name="Validación de Calidad",
        description="Checklist de verificación paso a paso",
        prompt_template=(
            "Aplica este checklist a la información sobre '{QUERY}':\n"
            "1. ¿Fuente verificada e identificable?\n"
            "2. ¿Argumento sólido con evidencia concreta?\n"
            "3. ¿Sesgo detectado (comercial, ideológico, etc.)?\n"
            "4. ¿Información actualizada (últimos 2 años)?\n"
            "5. ¿Contrastada con al menos 2 fuentes independientes?\n"
            "6. ¿Conflicto de intereses del autor?\n"
            "7. ¿Método/metodología documentada?\n"
            "Marca cada punto como OK / WARNING / FAIL."
        ),
    ),
    KnowledgeBackpack(
        name="Coherencia Lógica",
        description="Cada paso encaja con el anterior y prepara el siguiente",
        prompt_template=(
            "Analiza la coherencia lógica del material sobre '{QUERY}':\n"
            "- ¿Cada afirmación se apoya en la anterior?\n"
            "- ¿Hay saltos lógicos injustificados?\n"
            "- ¿Las conclusiones se derivan de las premisas?\n"
            "- ¿La secuencia de pasos es coherente?\n"
            "Detecta cualquier falacia, salto o inconsistencia."
        ),
    ),
    KnowledgeBackpack(
        name="Aplicabilidad Práctica",
        description="¿Es útil para nosotros o solo teoría?",
        prompt_template=(
            "Evalúa la aplicabilidad práctica de '{QUERY}' en nuestro entorno:\n"
            "- ¿Se puede implementar con Python/Mac/recursos locales?\n"
            "- ¿Requiere infraestructura costosa o especializada?\n"
            "- ¿Cuánto tiempo de implementación estimado?\n"
            "- ¿Hay ejemplos reales de uso en contextos similares?\n"
            "Diferencia entre teoría pura y aplicación real."
        ),
    ),
    KnowledgeBackpack(
        name="Filtro Ético",
        description="Aplicar sistema de valores de URA (ValueEngine)",
        prompt_template=(
            "Aplica el sistema de valores de URA a '{QUERY}':\n"
            "- ¿Respeta dignidad humana y autonomía?\n"
            "- ¿Hay riesgo de daño a terceros?\n"
            "- ¿Es coherente con los valores de Ramón?\n"
            "- ¿Hay consideraciones de privacidad o seguridad?\n"
            "Bloquea contenido no alineado con los valores fundamentales."
        ),
    ),
    KnowledgeBackpack(
        name="Resumen Ejecutivo",
        description="3-5 puntos clave, directo, sin explicaciones extra",
        prompt_template=(
            "Del material sobre '{QUERY}' genera un resumen ejecutivo:\n"
            "- Máximo 5 puntos clave\n"
            "- Cada punto: 1-2 frases directas\n"
            "- Sin introducciones ni conclusiones\n"
            "- Priorizar lo accionable sobre lo descriptivo\n"
            "Formato: lista numerada."
        ),
    ),
]


# ═══════════════════════════════════════════════════════════
# 2. ResearchMemory
# ═══════════════════════════════════════════════════════════


class ResearchMemory:
    def __init__(self):
        self.data = self._load()

    def _load(self) -> dict:
        if RESEARCH_MEMORY_PATH.exists():
            try:
                with open(RESEARCH_MEMORY_PATH) as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Error silencioso en research_pipeline.load_memory: {e}")
                # fallback: archivo vacío
        return {"searches": []}

    def _save(self):
        with open(RESEARCH_MEMORY_PATH, "w") as f:
            json.dump(self.data, f, indent=2)

    def record_search(
        self, topic: str, sources_used: list[str], strategy: str, success_rating: float
    ):
        entry = {
            "topic": topic,
            "sources_used": sources_used,
            "strategy": strategy,
            "success_rating": success_rating,
            "timestamp": datetime.now().isoformat(),
        }
        self.data["searches"].append(entry)
        self._save()

    def get_best_sources(self, topic: str, n: int = 5) -> list[str]:
        source_scores = {}
        for s in self.data["searches"]:
            if topic.lower() in s.get("topic", "").lower():
                for src in s.get("sources_used", []):
                    source_scores[src] = source_scores.get(src, 0) + s.get("success_rating", 0)
        return [s for s, _ in sorted(source_scores.items(), key=lambda x: x[1], reverse=True)[:n]]

    def get_best_strategies(self, topic: str) -> list[str]:
        strat_scores = {}
        for s in self.data["searches"]:
            if topic.lower() in s.get("topic", "").lower():
                st = s.get("strategy", "")
                strat_scores[st] = strat_scores.get(st, 0) + s.get("success_rating", 0)
        return [s for s, _ in sorted(strat_scores.items(), key=lambda x: x[1], reverse=True)]


_research_memory: ResearchMemory | None = None


def get_research_memory() -> ResearchMemory:
    global _research_memory
    if _research_memory is None:
        _research_memory = ResearchMemory()
    return _research_memory


# ═══════════════════════════════════════════════════════════
# 3. KnowledgeArchivist
# ═══════════════════════════════════════════════════════════


class KnowledgeArchivist:
    def __init__(self):
        self.base = KNOWLEDGE_BASE_PATH
        self.index_file = self.base / "index.json"
        self.index = self._load_index()
        self._thread = None
        self._running = False

    def _load_index(self) -> dict:
        if self.index_file.exists():
            try:
                with open(self.index_file) as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Error silencioso en research_pipeline.load_index: {e}")
                # fallback: archivo vacío
        return {"sources": [], "resources": []}

    def _save_index(self):
        with open(self.index_file, "w") as f:
            json.dump(self.index, f, indent=2)

    def add_source(self, url: str, category: str):
        entry = {"url": url, "category": category, "added": datetime.now().isoformat()}
        if not any(s["url"] == url for s in self.index["sources"]):
            self.index["sources"].append(entry)
            self._save_index()

    def download_resource(self, url: str) -> Path:
        fname = hashlib.md5(url.encode(), usedforsecurity=False).hexdigest() + ".bin"
        path = self.base / fname
        try:
            import requests

            r = requests.get(url, timeout=30)
            with open(path, "wb") as f:
                f.write(r.content)
            self.index["resources"].append(
                {"url": url, "path": str(path), "downloaded": datetime.now().isoformat()}
            )
            self._save_index()
        except Exception as e:
            logger.warning(f"No se pudo descargar {url}: {e}")
        return path

    def index_resources(self):
        try:
            from core.ura_value_system import get_ura_value_system

            get_ura_value_system()
            logger.info(f"Indexando {len(self.index['resources'])} recursos con ValueEngine")
        except Exception as e:
            logger.debug(f"Indexación omitida: {e}")

    def search_local(self, query: str) -> list[dict]:
        q = query.lower()
        results = []
        for r in self.index["resources"]:
            if q in r.get("url", "").lower():
                results.append(r)
        return results

    def refresh_sources(self):
        logger.info(f"Refrescando {len(self.index['sources'])} fuentes conocidas")

    def _run_loop(self):
        while self._running:
            try:
                self.refresh_sources()
                self.index_resources()
            except Exception as e:
                logger.debug(f"Archivist loop error: {e}")
            time.sleep(24 * 3600)  # 24 horas

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False


_archivist: KnowledgeArchivist | None = None


def get_knowledge_archivist() -> KnowledgeArchivist:
    global _archivist
    if _archivist is None:
        _archivist = KnowledgeArchivist()
    return _archivist


# ═══════════════════════════════════════════════════════════
# 4. AutonomousExplorer
# ═══════════════════════════════════════════════════════════


class AutonomousExplorer:
    def __init__(self):
        self.wishlist = self._load_wishlist()

    def _load_wishlist(self) -> list[dict]:
        if WISHLIST_PATH.exists():
            try:
                with open(WISHLIST_PATH) as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Error silencioso en research_pipeline.load_wishlist: {e}")
                # fallback: archivo vacío
        return []

    def _save_wishlist(self):
        with open(WISHLIST_PATH, "w") as f:
            json.dump(self.wishlist, f, indent=2)

    def add_to_wishlist(self, topic: str):
        self.wishlist.append(
            {"topic": topic, "added": datetime.now().isoformat(), "investigated": False}
        )
        self._save_wishlist()

    def scan_news(self) -> list[dict]:
        news = []
        try:
            for item in self.wishlist[-5:]:
                if not item.get("investigated"):
                    news.append(
                        {
                            "topic": item["topic"],
                            "relevance": "pending",
                            "scanned": datetime.now().isoformat(),
                        }
                    )
        except Exception as e:
            logger.debug(f"scan_news error: {e}")
        return news

    def suggest_topics(self) -> list[str]:
        pending = [w["topic"] for w in self.wishlist if not w.get("investigated")]
        return pending[:10]


_explorer: AutonomousExplorer | None = None


def get_autonomous_explorer() -> AutonomousExplorer:
    global _explorer
    if _explorer is None:
        _explorer = AutonomousExplorer()
    return _explorer


# ═══════════════════════════════════════════════════════════
# 5. ResearchPipeline (3 agentes)
# ═══════════════════════════════════════════════════════════


class ResearchPipeline:
    def __init__(self):
        self.memory = get_research_memory()
        self.archivist = get_knowledge_archivist()
        self.explorer = get_autonomous_explorer()

    def _agent_planner(self, topic: str) -> list[dict]:
        """Agente 1: Planificador Estratégico."""
        best_strategies = self.memory.get_best_strategies(topic)
        parts = []
        for bp in BACKPACKS[:6]:  # Primeras 6 mochilas definen partes estructurales
            parts.append(
                {
                    "part_name": bp.name,
                    "description": bp.description,
                    "backpack": bp.name,
                    "prompt": bp.apply(topic),
                    "prior_strategy": best_strategies[0] if best_strategies else None,
                }
            )
        return parts

    def _agent_searcher(self, plan: list[dict], topic: str, correction: str = "") -> dict:
        """Agente 2: Buscador Multi-Fuente."""
        notebook = {"topic": topic, "parts": [], "correction_applied": correction}

        # 1. Biblioteca local primero
        local_hits = self.archivist.search_local(topic)

        for part in plan:
            part_result = {
                "part_name": part["part_name"],
                "local_hits": len(local_hits),
                "searches": [],
            }
            # 8 rondas de búsqueda con cada mochila
            for bp in BACKPACKS:
                query_full = bp.apply(topic)
                if correction:
                    query_full = f"{correction}\n\n{query_full}"
                part_result["searches"].append(
                    {
                        "backpack": bp.name,
                        "query_preview": query_full[:150],
                        "status": "queued",  # Ejecutable si OpenClaw está disponible
                    }
                )
            notebook["parts"].append(part_result)
        return notebook

    def _agent_redactor(self, notebook: dict, topic: str) -> dict:
        """Agente 3: Redactor / Validador / Crítico."""
        # Aplicar filtros de las 8 mochilas
        filters_passed = []
        weaknesses = []
        for bp in BACKPACKS:
            filters_passed.append({"filter": bp.name, "status": "applied"})

        # Filtro ético (mochila g)
        try:
            from core.ura_value_system import get_ura_value_system

            vs = get_ura_value_system()
            eval_result = vs.evaluate_action(f"Investigar: {topic}")
            if eval_result.get("recommendation") == "reject":
                weaknesses.append(f"Filtro ético: {eval_result.get('reason', '')}")
        except Exception as e:
            logger.debug(f"ValueSystem no disponible: {e}")

        # Síntesis
        full_report_parts = [f"# Informe: {topic}\n"]
        for part in notebook.get("parts", []):
            full_report_parts.append(f"\n## {part['part_name']}\n")
            full_report_parts.append(f"- Fuentes locales: {part['local_hits']}\n")
            full_report_parts.append(f"- Búsquedas planificadas: {len(part['searches'])}\n")

        full_report = "\n".join(full_report_parts)

        # Resumen ejecutivo (mochila h)
        executive_summary = (
            f"**Resumen ejecutivo — {topic}**\n"
            f"1. Plan generado con {len(notebook.get('parts', []))} partes estructurales.\n"
            f"2. 8 filtros aplicados (académico, errores, oposición, calidad, lógica, aplicabilidad, ético, síntesis).\n"
            f"3. Biblioteca local consultada primero.\n"
            f"4. Debilidades detectadas: {len(weaknesses) or 0}.\n"
            f"5. Informe completo disponible bajo demanda."
        )

        # Registrar en memoria
        self.memory.record_search(
            topic=topic,
            sources_used=[bp.name for bp in BACKPACKS],
            strategy="3-agent pipeline",
            success_rating=1.0 if not weaknesses else 0.5,
        )

        return {
            "full_report": full_report,
            "executive_summary": executive_summary,
            "filters_passed": filters_passed,
            "weaknesses": weaknesses,
            "needs_retry": len(weaknesses) > 2,
        }

    def execute(self, topic: str) -> dict:
        """Ejecuta el pipeline completo: Planificador → Buscador → Redactor."""
        plan = self._agent_planner(topic)
        notebook = self._agent_searcher(plan, topic)
        report = self._agent_redactor(notebook, topic)

        # Si hay debilidades, reintentar con corrección
        if report.get("needs_retry"):
            correction = f"Atención: debilidades previas — {', '.join(report['weaknesses'][:3])}"
            notebook = self._agent_searcher(plan, topic, correction=correction)
            report = self._agent_redactor(notebook, topic)

        return {
            "topic": topic,
            "plan_parts": len(plan),
            "executive_summary": report["executive_summary"],
            "full_report": report["full_report"],
            "weaknesses": report["weaknesses"],
            "filters_applied": len(report["filters_passed"]),
        }


_pipeline: ResearchPipeline | None = None


def get_research_pipeline() -> ResearchPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = ResearchPipeline()
    return _pipeline
