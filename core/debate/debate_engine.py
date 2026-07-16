#!/usr/bin/env python3
"""debate_engine.py — SDA: Sistema de Debate entre Agentes.

Arquitectura:
  - primary (qwen2.5-coder:14b): razonador técnico, evalúa el plan
  - auditor (llama3.2:3b): abogado del diablo, busca fallos adversariales

Uso:
  echo '{"plan": "...", "author": "code", "context": {...}}' | python3 debate_engine.py
  python3 debate_engine.py --plan /tmp/ura_debate/plan.json

Salida (stdout):
  {"consensus": 0.85, "primary_score": 0.9, "auditor_score": 0.8,
   "primary_reason": "...", "auditor_reason": "...", "verdict": "CONSENSUS",
   "plan_unified": "..."}
"""

import asyncio
import json
import logging
import sys
from pathlib import Path

from core.debate.lockfile import DebateLock
from core.logs.guardian_logger import log_event
from motor.core.llm import generate

logger = logging.getLogger("ura.debate")

CONFIG_PATH = Path(__file__).parent / "committee_config.json"


def load_config() -> dict:
    with open(CONFIG_PATH) as f:
        return json.load(f)


def validar_esquema_salida(raw_output: str, schema_dict: dict | None = None) -> bool:
    if not schema_dict:
        return True
    try:
        clean = raw_output.strip()
        if "```json" in clean:
            clean = clean.split("```json")[1].split("```")[0].strip()
        elif "```" in clean:
            clean = clean.split("```")[1].split("```")[0].strip()
        data = json.loads(clean)
        for k, v in schema_dict.items():
            if k not in data:
                log_event(
                    "schema_validation_failed",
                    model="",
                    file="",
                    reason=f"Missing key: {k}",
                    attempts=0,
                    penalty="",
                    sandbox_errors=[],
                    complexity=0,
                    temperature=0.0,
                    result_type="warning",
                )
                return False
            if isinstance(v, type) and not isinstance(data[k], v):
                log_event(
                    "schema_validation_failed",
                    model="",
                    file="",
                    reason=f"Key {k}: expected {v.__name__}, got {type(data[k]).__name__}",
                    attempts=0,
                    penalty="",
                    sandbox_errors=[],
                    complexity=0,
                    temperature=0.0,
                    result_type="warning",
                )
                return False
        return True
    except (json.JSONDecodeError, Exception) as e:
        log_event(
            "schema_validation_failed",
            model="",
            file="",
            reason=str(e),
            attempts=0,
            penalty="",
            sandbox_errors=[],
            complexity=0,
            temperature=0.0,
            result_type="warning",
        )
        return False


def build_primary_prompt(plan_text: str, context: dict | None = None) -> str:
    ctx = json.dumps(context, indent=2) if context else "No disponible"
    return f"""Eres un arquitecto de software senior. Analiza el siguiente plan técnico.

CONTEXTO DEL SISTEMA:
{ctx}

PLAN A ANALIZAR:
{plan_text}

Evalúa:
1. Viabilidad técnica (VRAM disponible, servicios activos)
2. Claridad y completitud de los pasos
3. Riesgos de regresión o efectos colaterales
4. Alineación con la arquitectura existente

Responde EXACTAMENTE en JSON:
{{"score": 0.0-1.0, "reason": "explicación breve", "risks": ["riesgo1"], "suggestions": ["mejora1"]}}
"""


def build_auditor_prompt(plan_text: str, context: dict | None = None) -> str:
    ctx = json.dumps(context, indent=2) if context else "No disponible"
    return f"""Eres un ABOGADO DEL DIABLO. Tu trabajo es encontrar fallos en el plan.

CONTEXTO DEL SISTEMA:
{ctx}

PLAN A REVISAR:
{plan_text}

ACTÚA COMO ADVERSARIO:
1. Identifica riesgos críticos de VRAM, race conditions o puntos de fallo
2. Busca suposiciones no declaradas o pasos ambiguos
3. Señala dependencias externas que podrían fallar
4. Sé estricto y crítico — tu función es evitar implementaciones prematuras

IMPORTANTE: Solo marca requires_human=true si encuentras DOS O MÁS riesgos críticos
simultáneos que puedan causar fallo de sistema (ej: VRAM insuficiente + race condition).
Un solo riesgo menor NO justifica arbitraje humano.

Responde EXACTAMENTE en JSON:
{{"score": 0.0-1.0, "reason": "explicación de fallos encontrados", "risks": ["fallo1", "fallo2"], "requires_human": true/false}}
"""


async def call_ollama(
    model: str,
    prompt: str,
    temperature: float = 0.1,
    max_tokens: int = 2048,
) -> dict | None:
    try:
        raw = await asyncio.to_thread(
            generate,
            prompt,
            model=model,
            options={"temperature": temperature, "num_predict": max_tokens},
        )
        if raw.startswith("Error:"):
            logger.warning("[DEBATE] Error en modelo %s: %s", model, raw)
            return None
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1] if "\n" in cleaned else cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned.rsplit("\n", 1)[0] if "\n" in cleaned else cleaned[:-3]
        cleaned = cleaned.strip()
        parsed = json.loads(cleaned)
        default_schema = {"score": float, "reason": str, "risks": list}
        if not validar_esquema_salida(cleaned, default_schema):
            logger.warning("[DEBATE] Schema validation failed for %s", model)
            return None
        return parsed
    except (json.JSONDecodeError, Exception) as e:
        logger.warning("[DEBATE] Error en %s: %s", model, e)
        return None


async def run_debate(
    plan_text: str,
    context: dict | None = None,
    config: dict | None = None,
) -> dict:
    if config is None:
        config = load_config()

    primary_cfg = config["models"]["primary"]
    auditor_cfg = config["models"]["auditor"]
    threshold = config["consensus_threshold"]

    tasks = [
        call_ollama(
            primary_cfg["name"],
            build_primary_prompt(plan_text, context),
            temperature=primary_cfg["temperature"],
            max_tokens=primary_cfg["max_tokens"],
        ),
        call_ollama(
            auditor_cfg["name"],
            build_auditor_prompt(plan_text, context),
            temperature=auditor_cfg["temperature"],
            max_tokens=auditor_cfg["max_tokens"],
        ),
    ]
    results = await asyncio.gather(*tasks)

    primary_result, auditor_result = results

    primary_score = primary_result.get("score", 0.0) if primary_result else 0.0
    auditor_score = auditor_result.get("score", 0.0) if auditor_result else 0.0
    consensus = min(primary_score, auditor_score)

    if primary_result is None or auditor_result is None:
        verdict = "INCOMPLETE"
        plan_unified = plan_text
    elif consensus >= threshold and not auditor_result.get("requires_human", False):
        verdict = "CONSENSUS"
        plan_unified = plan_text
        if primary_result.get("suggestions"):
            plan_unified += "\n\n# Mejoras sugeridas:\n" + "\n".join(
                f"- {s}" for s in primary_result["suggestions"][:3]
            )
    else:
        verdict = "HUMAN_ARBITRATION"
        plan_unified = plan_text

    return {
        "consensus": round(consensus, 2),
        "primary_score": primary_score,
        "auditor_score": auditor_score,
        "primary_reason": primary_result.get("reason", "") if primary_result else "timeout/error",
        "auditor_reason": auditor_result.get("reason", "") if auditor_result else "timeout/error",
        "primary_risks": primary_result.get("risks", []) if primary_result else [],
        "auditor_risks": auditor_result.get("risks", []) if auditor_result else [],
        "verdict": verdict,
        "plan_unified": plan_unified,
    }


async def main_async() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "--plan":
        plan_path = sys.argv[2]
        with open(plan_path) as f:
            data = json.load(f)
    else:
        data = json.loads(sys.stdin.read())

    plan_text = data.get("plan", "")
    context = data.get("context")

    with DebateLock():
        result = await run_debate(plan_text, context)

    logger.info(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("verdict") == "CONSENSUS" else 1


def main() -> None:
    exit_code = asyncio.run(main_async())
    sys.exit(exit_code)


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    main()
