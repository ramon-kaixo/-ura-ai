#!/usr/bin/env python3
"""
URA Observability - Logging + Langfuse integrado
Combina agent logging con Langfuse y trace_step para workflow engine
"""

import json
import os
import uuid
import logging
from datetime import datetime
from functools import wraps
from pathlib import Path
from typing import TypedDict

logger = logging.getLogger(__name__)

try:
    from dotenv import load_dotenv

    _env_path = Path(__file__).parent.parent / ".env"
    if _env_path.exists():
        load_dotenv(_env_path)
except Exception:
    pass

# Configuracion
PROJECT_DIR = Path(__file__).parent.parent
LOG_PATH = PROJECT_DIR / "logs_agentes"
LOG_PATH.mkdir(exist_ok=True)
OBSERVABILITY_DIR = PROJECT_DIR / "data" / "observability"


# ============================================================
# LANGGRAPH TRACE STEP
# ============================================================
def trace_step(func):
    """Decorator to trace function execution steps."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        start = datetime.now()
        try:
            result = func(*args, **kwargs)
            int((datetime.now() - start).total_seconds() * 1000)
            OBSERVABILITY_DIR.mkdir(parents=True, exist_ok=True)
            return result
        except Exception:
            int((datetime.now() - start).total_seconds() * 1000)
            raise

    return wrapper


# ============================================================
# LANGFUSE
# ============================================================
try:
    from langfuse import Langfuse

    langfuse = Langfuse(
        public_key=os.environ.get("LANGFUSE_PUBLIC_KEY", "pk-lf-..."),
        secret_key=os.environ.get("LANGFUSE_SECRET_KEY", "sk-lf-..."),
        host=os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com"),
    )
    LANGFUSE_ENABLED = True
except:
    langfuse = None
    LANGFUSE_ENABLED = False


# ============================================================
# CLASES DE LOGGING
# ============================================================
class ExecutionLog(TypedDict):
    timestamp: str
    trace_id: str
    agente: str
    input: dict
    tool_used: str
    output: str
    estado: str
    duracion_ms: int
    Tokens: int | None
    coste: float | None


class URALogger:
    """Logger unificado para URA"""

    def __init__(self, agente: str):
        self.agente = agente
        self.log_file = LOG_PATH / f"{agente}_{datetime.now().strftime('%Y%m%d')}.jsonl"

    def log(
        self,
        input_datos: dict,
        tool_usada: str,
        output_datos: str,
        estado: str,
        metadata: dict = None,
        trace_id: str = None,
        duracion_ms: int = 0,
        tokens: int = 0,
        coste: float = 0.0,
    ):
        """Registrar ejecucion"""

        trace_id = trace_id or str(uuid.uuid4())

        registro: ExecutionLog = {
            "timestamp": datetime.now().isoformat(),
            "trace_id": trace_id,
            "agente": self.agente,
            "input": input_datos,
            "tool_used": tool_usada,
            "output": output_datos[:500] if output_datos else "",
            "estado": estado,
            "duracion_ms": duracion_ms,
            "tokens": tokens,
            "coste": coste,
        }

        with open(self.log_file, "a") as f:
            f.write(json.dumps(registro) + "\n")

        if LANGFUSE_ENABLED and langfuse:
            try:
                langfuse.trace(
                    name=self.agente, trace_id=trace_id, metadata={**registro, **(metadata or {})}
                )
            except Exception as e:
                logger.warning(f"Error silencioso en observability.registrar: {e}")
                # fallback: continuar

        return registro

    def log_inicio(self, input_datos: dict, trace_id: str = None):
        return self.log(input_datos, "ninguna", "", "inicio", trace_id=trace_id)

    def log_tool(self, tool: str, input_datos: dict):
        return self.log(input_datos, tool, "", "ejecutando")

    def log_ok(self, output: str, trace_id: str = None, duracion_ms: int = 0, tokens: int = 0):
        return self.log(
            {}, "gemma3:1b", output, "ok", trace_id=trace_id, duracion_ms=duracion_ms, tokens=tokens
        )

    def log_error(self, error: str, trace_id: str = None):
        return self.log({}, "ninguna", error, "error", trace_id=trace_id)


# ============================================================
# SISTEMA DE OBSERVABILITY
# ============================================================
class Observability:
    """Sistema de observabilidad"""

    def __init__(self):
        self.observability_dir = OBSERVABILITY_DIR
        self.observability_dir.mkdir(parents=True, exist_ok=True)
        self.traces = []
        self.metrics = []
        self.logs = []

    def agregar_trace(self, trace_id: str, servicio: str, operacion: str, duracion_ms: int) -> dict:
        trace = {
            "trace_id": trace_id,
            "servicio": servicio,
            "operacion": operacion,
            "duracion_ms": duracion_ms,
            "timestamp": datetime.now().isoformat(),
        }
        self.traces.append(trace)
        return trace

    def agregar_metrica(self, nombre: str, valor: float, etiquetas: dict = None) -> dict:
        metrica = {
            "nombre": nombre,
            "valor": valor,
            "etiquetas": etiquetas or {},
            "timestamp": datetime.now().isoformat(),
        }
        self.metrics.append(metrica)
        return metrica

    def agregar_log(self, nivel: str, mensaje: str, servicio: str) -> dict:
        log = {
            "nivel": nivel,
            "mensaje": mensaje,
            "servicio": servicio,
            "timestamp": datetime.now().isoformat(),
        }
        self.logs.append(log)
        return log

    def consultar_traces(self, servicio: str = None, desde: str = None) -> list[dict]:
        traces = self.traces
        if servicio:
            traces = [t for t in traces if t["servicio"] == servicio]
        if desde:
            traces = [t for t in traces if t["timestamp"] >= desde]
        return traces

    def consultar_metrics(self, nombre: str, ventana_segundos: int = 60) -> dict:
        metrics_recientes = [
            m
            for m in self.metrics
            if m["nombre"] == nombre
            and (datetime.now() - datetime.fromisoformat(m["timestamp"])).total_seconds()
            < ventana_segundos
        ]
        if metrics_recientes:
            valores = [m["valor"] for m in metrics_recientes]
            return {
                "nombre": nombre,
                "promedio": sum(valores) / len(valores),
                "min": min(valores),
                "max": max(valores),
                "total": len(valores),
            }
        return {"error": "No hay metricas"}

    def generar_dashboard(self) -> dict:
        return {
            "traces_totales": len(self.traces),
            "metrics_totales": len(self.metrics),
            "logs_totales": len(self.logs),
            "servicios": list({t["servicio"] for t in self.traces}),
            "timestamp": datetime.now().isoformat(),
        }


# ============================================================
# INTEGRACION CON LANGGRAPH
# ============================================================
def log_llm_call(prompt: str, model: str = "gemma3:1b", **kwargs):
    """Funcion para logging de llamadas LLM"""
    import time

    inicio = time.time()
    duracion = int((time.time() - inicio) * 1000)
    return {"model": model, "prompt": prompt[:100], "duracion_ms": duracion}


# ============================================================
# DASHBOARD DE METRICAS
# ============================================================
class MetricsDashboard:
    """Dashboard de metricas"""

    def __init__(self):
        self.logs_path = LOG_PATH

    def get_estadisticas_hoy(self) -> dict:
        fecha = datetime.now().strftime("%Y%m%d")
        total = 0
        ok = 0
        error = 0
        duracion_total = 0

        for log_file in self.logs_path.glob(f"*{fecha}.jsonl"):
            if not log_file.name.startswith("."):
                with open(log_file) as f:
                    for linea in f:
                        try:
                            reg = json.loads(linea)
                            total += 1
                            if reg.get("estado") == "ok":
                                ok += 1
                            elif reg.get("estado") == "error":
                                error += 1
                            duracion_total += reg.get("duracion_ms", 0)
                        except Exception as e:
                            logger.warning(f"Error silencioso en observability.estadisticas: {e}")
                            # fallback: continuar

        return {
            "total_ejecuciones": total,
            "exitosas": ok,
            "errores": error,
            "tasa_exito": (ok / total * 100) if total > 0 else 0,
            "duracion_promedio_ms": duracion_total // total if total > 0 else 0,
        }

    def get_top_agentes(self) -> list:
        conteo = {}
        for log_file in self.logs_path.glob("*.jsonl"):
            if not log_file.name.startswith("."):
                with open(log_file) as f:
                    for linea in f:
                        try:
                            reg = json.loads(linea)
                            agente = reg.get("agente", "unknown")
                            conteo[agente] = conteo.get(agente, 0) + 1
                        except Exception as e:
                            logger.warning(f"Error silencioso en observability.top_agentes: {e}")
                            # fallback: continuar
        return sorted(conteo.items(), key=lambda x: x[1], reverse=True)[:10]
