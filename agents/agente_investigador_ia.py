#!/usr/bin/env python3
"""
agents/agente_investigador_ia.py - Agente investigador de nuevas herramientas y modelos de IA
Ejecutado semanalmente: detecta nuevos modelos Ollama, busca novedades, benchmarkea candidatos.
NO cambia el modelo activo — solo recomienda.
"""

import json
import logging
import time
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

ROOT = Path(__file__).parent.parent
RESEARCH_LOG = ROOT / "data" / "ia_research_log.json"
UPGRADE_LOG = ROOT / "data" / "model_upgrade_suggestions.json"
BENCHMARK_FILE = ROOT / "data" / "benchmark_questions.json"

OLLAMA_API = "http://localhost:11434"
BUSQUEDAS_IA = [
    # ── Agentes IA — fundamentos ─────────────────────────────
    "AI agents architecture design patterns 2025",
    "tipos de agentes IA RPA autónomos cognitivos",
    "multi-agent systems coordination orchestration best practices",
    "AI agent frameworks comparison LangGraph CrewAI AutoGen 2025",
    "how to build AI agents step by step guide",
    "agent memory systems RAG vector databases implementation",
    "AI agent tool use function calling best practices",
    "agent communication protocols inter-agent messaging",
    # ── Agentes especializados ────────────────────────────────
    "gastronomic AI agents restaurant automation",
    "AI cooking agents recipe generation menu planning",
    "design AI agents creative automation graphic design",
    "marketing AI agents social media content automation",
    "financial AI agents accounting bookkeeping automation",
    "legal AI agents compliance document review automation",
    "HR AI agents payroll workforce management automation",
    # ── Técnicas avanzadas ────────────────────────────────────
    "AI agent planning reasoning ReAct pattern implementation",
    "agent self-reflection improvement techniques",
    "AI agent security sandboxing validation guardrails",
    "agentes IA especializados por dominio mejores prácticas",
    "AI agent evaluation benchmarking metrics 2025",
    "agent orchestration supervisor pattern hierarchical",
    # ── Infraestructura y despliegue ──────────────────────────
    "deploying AI agents locally Ollama open source",
    "agents on edge devices Mac Mini local deployment",
    "AI agent monitoring logging observability",
    "agent error handling retry patterns circuit breaker",
    # ── Tendencias ────────────────────────────────────────────
    "new open source LLM 2025",
    "new AI automation tools open source",
    "best small language model 2025",
    "multimodal AI genetics latest research 2025",
    "LangGraph AutoGen CrewAI comparison 2025",
]


# ── utilidades Ollama ─────────────────────────────────────────────────────────


def _ollama_tags() -> list[str]:
    """Lista modelos disponibles en Ollama local."""
    try:
        with urllib.request.urlopen(f"{OLLAMA_API}/api/tags", timeout=5) as r:  # nosec B310
            data = json.loads(r.read())
            return [m["name"] for m in data.get("models", [])]
    except Exception:
        return []


def _ollama_generate(modelo: str, prompt: str, timeout: int = 30) -> str:
    """Genera respuesta con un modelo Ollama."""
    payload = json.dumps(
        {
            "model": modelo,
            "prompt": prompt,
            "stream": False,
            "options": {"num_predict": 200, "temperature": 0.1},
        }
    ).encode()
    try:
        req = urllib.request.Request(
            f"{OLLAMA_API}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:  # nosec B310
            return json.loads(r.read()).get("response", "")
    except Exception as e:
        logger.warning("Ollama generate falló para %s: %s", modelo, e)
        return ""


# ── benchmark ─────────────────────────────────────────────────────────────────


def _benchmark_modelo(modelo: str) -> dict[str, Any]:
    """
    Ejecuta las 10 preguntas estándar contra un modelo.
    Devuelve puntuación 0-100 basada en respuestas no vacías y longitud razonable.
    """
    if not BENCHMARK_FILE.exists():
        return {"modelo": modelo, "score": 0, "error": "benchmark_questions.json no encontrado"}

    preguntas = json.loads(BENCHMARK_FILE.read_text())["preguntas"]
    correctas = 0
    tiempos = []

    for p in preguntas:
        t0 = time.time()
        respuesta = _ollama_generate(modelo, p["pregunta"])
        elapsed = time.time() - t0
        tiempos.append(elapsed)
        # criterio básico: respuesta no vacía y al menos 20 palabras
        if respuesta and len(respuesta.split()) >= 20:
            correctas += 1

    score = int((correctas / len(preguntas)) * 100)
    return {
        "modelo": modelo,
        "score": score,
        "correctas": correctas,
        "total": len(preguntas),
        "tiempo_medio_s": round(sum(tiempos) / len(tiempos), 2) if tiempos else 0,
        "timestamp": datetime.now().isoformat(),
    }


# ── búsqueda de novedades ─────────────────────────────────────────────────────


def _buscar_novedades() -> list[dict]:
    """Busca noticias sobre nuevas herramientas de IA usando buscador_tendencias."""
    try:
        from core.buscadores.buscador_tendencias import BuscadorTendencias

        bt = BuscadorTendencias()
        tendencias = bt.analizar_tendencias()
        return [{"fuente": "buscador_tendencias", "resultado": str(t)} for t in tendencias[:5]]
    except Exception as e:
        logger.warning("buscador_tendencias falló: %s", e)
        return []


# ── agente principal ──────────────────────────────────────────────────────────


class AgenteInvestigadorIA:
    """Investiga novedades de IA semanalmente y recomienda upgrades cuando son mejores."""

    def ejecutar(self) -> dict[str, Any]:
        logger.info("Iniciando investigación semanal de IA...")
        timestamp = datetime.now().isoformat()

        resultado: dict[str, Any] = {
            "timestamp": timestamp,
            "modelos_disponibles": [],
            "modelo_activo": "",
            "score_modelo_activo": 0,
            "candidatos_evaluados": [],
            "novedades": [],
            "recomendaciones": [],
        }

        # modelo activo actual
        try:
            from core.model_config import get_active_model

            modelo_activo = get_active_model()
        except Exception:
            modelo_activo = "qwen2.5:7b-instruct"
        resultado["modelo_activo"] = modelo_activo

        # modelos disponibles en Ollama
        modelos = _ollama_tags()
        resultado["modelos_disponibles"] = modelos
        logger.info("Modelos Ollama disponibles: %s", modelos)

        # benchmark del modelo activo (referencia)
        if modelo_activo in modelos:
            logger.info("Benchmarkeando modelo activo: %s", modelo_activo)
            bench_activo = _benchmark_modelo(modelo_activo)
            resultado["score_modelo_activo"] = bench_activo["score"]
        else:
            bench_activo = {"score": 0}
            logger.warning("Modelo activo %s no encontrado en Ollama", modelo_activo)

        # evaluar candidatos (modelos que no son el activo)
        candidatos = [m for m in modelos if m != modelo_activo]
        for candidato in candidatos[:3]:  # máximo 3 para no tardar demasiado
            logger.info("Evaluando candidato: %s", candidato)
            bench = _benchmark_modelo(candidato)
            resultado["candidatos_evaluados"].append(bench)

            mejora = bench["score"] - bench_activo["score"]
            if mejora > 10:
                recomendacion = {
                    "modelo": candidato,
                    "score": bench["score"],
                    "score_actual": bench_activo["score"],
                    "mejora_puntos": mejora,
                    "mensaje": (
                        f"El modelo {candidato} supera al actual ({modelo_activo}) "
                        f"en {mejora} puntos ({bench_activo['score']} → {bench['score']}). "
                        f"Considera cambiarlo en Configuración → Modelo."
                    ),
                }
                resultado["recomendaciones"].append(recomendacion)
                logger.info("RECOMENDACIÓN: %s", recomendacion["mensaje"])

        # búsqueda de novedades externas
        resultado["novedades"] = _buscar_novedades()

        # guardar logs
        RESEARCH_LOG.parent.mkdir(parents=True, exist_ok=True)
        existing = []
        if RESEARCH_LOG.exists():
            try:
                existing = json.loads(RESEARCH_LOG.read_text())
            except Exception:
                existing = []
        existing.append(resultado)
        existing = existing[-12:]  # conservar últimas 12 semanas
        RESEARCH_LOG.write_text(json.dumps(existing, indent=2, ensure_ascii=False))

        if resultado["recomendaciones"]:
            UPGRADE_LOG.write_text(
                json.dumps(resultado["recomendaciones"], indent=2, ensure_ascii=False)
            )

        logger.info(
            "Investigación completada. Recomendaciones: %d", len(resultado["recomendaciones"])
        )
        return resultado

    def procesar(self, texto: str) -> str:
        """Procesar consulta para AgenteInvestigadorIA."""
        texto.lower()
        return "Puedo investigar modelos de IA, herramientas y tendencias. ¿Qué tema de IA necesitas investigar?"

    def ejecutar(self, texto: str) -> str:
        """Ejecutar acción para AgenteInvestigadorIA."""
        return self.procesar(texto)

    def consultar(self, texto: str) -> str:
        """Consultar información para AgenteInvestigadorIA."""
        return self.procesar(texto)

    def responder(self, texto: str) -> str:
        """Responder pregunta para AgenteInvestigadorIA."""
        return self.procesar(texto)


# singleton
agente_investigador_ia = AgenteInvestigadorIA()

if __name__ == "__main__":
    r = agente_investigador_ia.ejecutar()
    print("\n=== INVESTIGACIÓN IA ===")
    print(f"Modelo activo: {r['modelo_activo']} ({r['score_modelo_activo']}/100)")
    print(f"Modelos disponibles: {r['modelos_disponibles']}")
    if r["recomendaciones"]:
        for rec in r["recomendaciones"]:
            print(f"\n💡 {rec['mensaje']}")
    else:
        print("\n✅ El modelo actual es el mejor disponible.")
