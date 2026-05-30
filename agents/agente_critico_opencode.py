#!/usr/bin/env python3
"""
AGENTE CRÍTICO OPENCODE — Revisa código y detecta errores.

Analiza código fuente buscando:
- Errores de sintaxis y linting
- Patrones problemáticos (hardcoded secrets, SQL injection, etc.)
- Código muerto o duplicado
- Problemas de seguridad
- Complejidad excesiva

Integra con Ollama para análisis semántico cuando está disponible.
"""

import ast
import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

SISTEMA = Path(__file__).parent.parent
LOG_DIR = SISTEMA / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG = LOG_DIR / "critico_opencode.log"

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
MODELO_REVISION = os.environ.get("MODELO_REVISION", "qwen2.5-coder:14b")

PATRONES_PELIGROSOS = [
    {
        "patron": r"password\s*=\s*['\"](?!{).+['\"]",
        "severidad": "critica",
        "desc": "Contraseña hardcoded",
    },
    {
        "patron": r"api[_-]?key\s*=\s*['\"](?!{).+['\"]",
        "severidad": "critica",
        "desc": "API key hardcoded",
    },
    {
        "patron": r"secret\s*=\s*['\"](?!{).+['\"]",
        "severidad": "critica",
        "desc": "Secret hardcoded",
    },
    {"patron": r"eval\s*\(", "severidad": "alta", "desc": "Uso de eval()"},
    {"patron": r"exec\s*\(", "severidad": "alta", "desc": "Uso de exec()"},
    {
        "patron": r"subprocess\..*shell\s*=\s*True",
        "severidad": "alta",
        "desc": "Shell injection posible",
    },
    {"patron": r"os\.system\s*\(", "severidad": "alta", "desc": "os.system() - usar subprocess"},
    {
        "patron": r"\.format\(.*\).*(?:SELECT|INSERT|UPDATE|DELETE)",
        "severidad": "critica",
        "desc": "SQL injection via format",
    },
    {
        "patron": r"f['\"].*(?:SELECT|INSERT|UPDATE|DELETE).*{",
        "severidad": "critica",
        "desc": "SQL injection via f-string",
    },
    {"patron": r"except\s*:\s*$", "severidad": "media", "desc": "Except genérico sin tipo"},
    {
        "patron": r"except\s+Exception\s*:\s*\n\s*pass",
        "severidad": "media",
        "desc": "Exception silenciada",
    },
    {"patron": r"# ?TODO", "severidad": "info", "desc": "TODO pendiente"},
    {"patron": r"# ?FIXME", "severidad": "media", "desc": "FIXME pendiente"},
    {"patron": r"# ?HACK", "severidad": "media", "desc": "HACK en código"},
    {"patron": r"print\s*\(", "severidad": "info", "desc": "print() en producción (usar logger)"},
    {"patron": r"import pdb", "severidad": "alta", "desc": "Debugger importado"},
    {"patron": r"breakpoint\(\)", "severidad": "alta", "desc": "Breakpoint en código"},
]


def _log(msg: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG, "a") as f:
        f.write(f"[{ts}] {msg}\n")
    logger.info(msg)


class AgenteCriticoOpenCode:
    """Revisa código y detecta errores, vulnerabilidades y malas prácticas."""

    def __init__(self) -> None:
        self.resultados: list[dict] = []

    def analizar_archivo(self, filepath: str) -> dict:
        """Analiza un archivo Python completo."""
        path = Path(filepath)
        if not path.exists():
            return {"ok": False, "error": f"Archivo no existe: {filepath}"}

        _log(f"Analizando: {filepath}")
        contenido = path.read_text(encoding="utf-8", errors="ignore")
        lineas = contenido.split("\n")

        resultado = {
            "archivo": str(path),
            "timestamp": datetime.now().isoformat(),
            "lineas": len(lineas),
            "problemas": [],
            "metricas": {},
        }

        resultado["problemas"].extend(self._buscar_patrones(contenido, lineas))
        resultado["problemas"].extend(self._verificar_sintaxis(filepath, contenido))
        resultado["metricas"] = self._calcular_metricas(contenido, lineas)

        resultado["resumen"] = {
            "total": len(resultado["problemas"]),
            "criticos": sum(1 for p in resultado["problemas"] if p["severidad"] == "critica"),
            "altos": sum(1 for p in resultado["problemas"] if p["severidad"] == "alta"),
            "medios": sum(1 for p in resultado["problemas"] if p["severidad"] == "media"),
            "info": sum(1 for p in resultado["problemas"] if p["severidad"] == "info"),
        }

        _log(
            f"Análisis completo: {resultado['resumen']['total']} problemas ({resultado['resumen']['criticos']} críticos)"
        )
        return resultado

    def _buscar_patrones(self, contenido: str, lineas: list) -> list:
        """Busca patrones peligrosos en el código."""
        problemas = []
        for patron_def in PATRONES_PELIGROSOS:
            for i, linea in enumerate(lineas, 1):
                if linea.strip().startswith("#"):
                    if patron_def["desc"] not in (
                        "TODO pendiente",
                        "FIXME pendiente",
                        "HACK en código",
                    ):
                        continue
                if re.search(patron_def["patron"], linea, re.IGNORECASE):
                    problemas.append(
                        {
                            "linea": i,
                            "severidad": patron_def["severidad"],
                            "tipo": "patron",
                            "descripcion": patron_def["desc"],
                            "codigo": linea.strip()[:100],
                        }
                    )
        return problemas

    def _verificar_sintaxis(self, filepath: str, contenido: str) -> list:
        """Verifica sintaxis Python con ast."""
        problemas = []
        if not filepath.endswith(".py"):
            return problemas

        try:
            ast.parse(contenido)
        except SyntaxError as e:
            problemas.append(
                {
                    "linea": e.lineno or 0,
                    "severidad": "critica",
                    "tipo": "sintaxis",
                    "descripcion": f"Error de sintaxis: {e.msg}",
                    "codigo": (e.text or "").strip()[:100],
                }
            )
        return problemas

    def _calcular_metricas(self, contenido: str, lineas: list) -> dict:
        """Calcula métricas del código."""
        lineas_codigo = [l for l in lineas if l.strip() and not l.strip().startswith("#")]
        lineas_comentario = [l for l in lineas if l.strip().startswith("#")]
        funciones = re.findall(r"^\s*def\s+\w+", contenido, re.MULTILINE)
        clases = re.findall(r"^\s*class\s+\w+", contenido, re.MULTILINE)
        imports = re.findall(r"^(?:from|import)\s+", contenido, re.MULTILINE)

        return {
            "lineas_total": len(lineas),
            "lineas_codigo": len(lineas_codigo),
            "lineas_comentario": len(lineas_comentario),
            "funciones": len(funciones),
            "clases": len(clases),
            "imports": len(imports),
            "ratio_comentarios": round(
                len(lineas_comentario) / max(len(lineas_codigo), 1) * 100, 1
            ),
        }

    def analizar_directorio(self, directorio: str, extensiones: list | None = None) -> dict:
        """Analiza todos los archivos de un directorio."""
        path = Path(directorio)
        if not path.is_dir():
            return {"ok": False, "error": f"No es un directorio: {directorio}"}

        extensiones = extensiones or [".py"]
        archivos = []
        for ext in extensiones:
            archivos.extend(path.rglob(f"*{ext}"))

        # Excluir __pycache__, .git, venv, node_modules
        archivos = [
            a
            for a in archivos
            if not any(
                p in str(a) for p in ["__pycache__", ".git", "venv", "node_modules", ".mypy_cache"]
            )
        ]

        _log(f"Analizando directorio {directorio}: {len(archivos)} archivos")

        resultados = []
        total_problemas = 0
        for archivo in sorted(archivos):
            res = self.analizar_archivo(str(archivo))
            if res.get("problemas"):
                resultados.append(res)
                total_problemas += len(res["problemas"])

        return {
            "directorio": str(path),
            "archivos_analizados": len(archivos),
            "archivos_con_problemas": len(resultados),
            "total_problemas": total_problemas,
            "resultados": resultados,
        }

    def revision_con_ia(self, filepath: str) -> dict:
        """Solicita revisión de código a Ollama."""
        path = Path(filepath)
        if not path.exists():
            return {"ok": False, "error": f"Archivo no existe: {filepath}"}

        contenido = path.read_text(encoding="utf-8", errors="ignore")
        if len(contenido) > 8000:
            contenido = contenido[:8000] + "\n\n... (truncado)"

        prompt = f"""Revisa este código Python y reporta:
1. Bugs o errores lógicos
2. Problemas de seguridad
3. Sugerencias de mejora
4. Código muerto

Archivo: {path.name}
```python
{contenido}
```

Responde en formato JSON con la estructura:
{{"bugs": [...], "seguridad": [...], "mejoras": [...], "codigo_muerto": [...]}}"""

        try:
            req = Request(
                f"{OLLAMA_URL}/api/generate",
                data=json.dumps(
                    {"model": MODELO_REVISION, "prompt": prompt, "stream": False}
                ).encode(),
                headers={"Content-Type": "application/json"},
            )
            with urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read())
                return {"ok": True, "revision": data.get("response", ""), "modelo": MODELO_REVISION}
        except Exception as e:
            _log(f"Error en revisión IA: {e}")
            return {"ok": False, "error": str(e)}

    def ejecutar(self, tarea: str = "analizar", **kwargs) -> dict:
        """Punto de entrada principal."""
        _log(f"Ejecutando: {tarea}")

        if tarea == "analizar":
            target = kwargs.get("archivo") or kwargs.get("directorio", str(SISTEMA))
            if Path(target).is_file():
                return self.analizar_archivo(target)
            return self.analizar_directorio(target)
        elif tarea == "revision_ia":
            return self.revision_con_ia(kwargs.get("archivo", ""))

        return {"error": f"Tarea desconocida: {tarea}"}


def ejecutar(tarea: str = "analizar", **kwargs) -> dict:
    """Función de entrada para el orquestador."""
    agente = AgenteCriticoOpenCode()
    return agente.ejecutar(tarea, **kwargs)


if __name__ == "__main__":
    import sys

    target = sys.argv[1] if len(sys.argv) > 1 else str(SISTEMA / "agents")
    resultado = ejecutar("analizar", directorio=target)
    print(json.dumps(resultado, indent=2, default=str, ensure_ascii=False))
