#!/usr/bin/env python3
"""
agente_lenguaje.py — Agente de Lenguaje Unificador de URA
==========================================================
Responsabilidades:
  1. Registrar todos los agentes activos del sistema
  2. Asignar vocabulario específico a cada agente desde arquitectura/vocabulario/
  3. Incorporar conocimiento de arquitectura/aprendizaje/ultimo/
  4. Ensamblar resultados de múltiples agentes en una respuesta coherente
  5. Entregar al orquestador respuestas enriquecidas con vocabulario controlado

Uso como módulo:
    from agente_lenguaje import AgenteLenguaje
    al = AgenteLenguaje()
    respuesta = al.ensamblar([{"agente": "tecnico", "resultado": "..."}, ...], tarea="título")

Uso directo:
    python3 agente_lenguaje.py --estado          # muestra registro actual
    python3 agente_lenguaje.py --incorporar      # incorpora vocabulario de aprendizaje
    python3 agente_lenguaje.py --ensamblar FILE  # ensambla resultados desde JSON
"""

import logging

logger = logging.getLogger(__name__)
import json
import os
import time
import urllib.request
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Rutas base
# ---------------------------------------------------------------------------

DEFAULT_BASE = Path(__file__).resolve().parents[1]
BASE = Path(os.environ.get("URA_BASE_DIR", str(DEFAULT_BASE))).expanduser()
ARCH = BASE / "arquitectura"
VOC_DIR = ARCH / "vocabulario"
APRENDIZAJE = ARCH / "aprendizaje" / "ultimo"
REGISTRO = ARCH / "registro"
REGISTRO.mkdir(parents=True, exist_ok=True)

REGISTRO_AGENTES_JSON = REGISTRO / "agentes_activos.json"
LOG_FILE = BASE / "logs" / "agente_lenguaje.log"
OLLAMA_URL = "http://localhost:11434"

# ---------------------------------------------------------------------------
# Vocabulario por tipo de agente
# ---------------------------------------------------------------------------

# Mapeo: sección del orquestador → archivos de vocabulario aplicables
VOCABULARIO_POR_TIPO: dict[str, list[str]] = {
    "tecnica": ["tecnico.txt"],
    "operaciones": ["tecnico.txt"],
    "seguridad": ["tecnico.txt"],
    "instalacion": ["tecnico.txt"],
    "mantenimiento": ["tecnico.txt"],
    "verificacion": ["tecnico.txt"],
    "gestion": ["conductor.txt"],
    "comunicacion": ["conductor.txt"],
    "manuales": ["conductor.txt"],
    "trazabilidad": ["conductor.txt"],
    "creativa": ["creativo.txt"],
    "marketing": ["creativo.txt"],
    "investigacion": ["tecnico.txt", "conductor.txt"],
    "ensamblado": ["tecnico.txt", "conductor.txt", "creativo.txt"],
    "lenguaje": ["tecnico.txt", "conductor.txt", "creativo.txt"],
    "backup": ["tecnico.txt"],
    "contexto": ["contexto.txt", "conductor.txt"],
    "prioridades": ["conductor.txt"],
    "alertas": ["tecnico.txt"],
    "camaras": ["tecnico.txt"],
}

# Modelos Ollama asociados a cada sección
MODELO_POR_TIPO: dict[str, str] = {
    "tecnica": "tecnico",
    "operaciones": "operaciones",
    "seguridad": "policia",  # deepseek-r1:7b
    "instalacion": "instalador",
    "mantenimiento": "mantenimiento",
    "verificacion": "verificador",
    "gestion": "gestion",
    "comunicacion": "comunicacion",
    "manuales": "manuales",
    "trazabilidad": "trazabilidad",
    "creativa": "creativa",
    "marketing": "marketing",
    "investigacion": "buscador",  # llama3.2:3b
    "ensamblado": "ensamblador",
    "lenguaje": "lenguaje",
    "backup": "backup",
    "contexto": "contexto",
    "prioridades": "subagente",  # llama3.2:1b
    "alertas": "alertas",
    "camaras": "camaras",
}

# Registro completo de agentes del sistema
DEFINICION_AGENTES = [
    # (nombre_modelo, tipo, descripcion)
    ("principal", "gestion", "Decisor central — clasifica y enruta tareas"),
    ("policia", "seguridad", "Validación de seguridad con razonamiento profundo (deepseek-r1:7b)"),
    ("buscador", "investigacion", "Síntesis de búsquedas web (llama3.2:3b)"),
    ("subagente", "prioridades", "Clasificaciones y decisiones atómicas (llama3.2:1b)"),
    ("tecnico", "tecnica", "Tareas técnicas, DevOps, Python, sistema"),
    ("operaciones", "operaciones", "Operaciones del sistema y procesos"),
    ("seguridad", "seguridad", "Análisis de seguridad profundo (4.7GB legacy)"),
    ("instalador", "instalacion", "Instalación de software y dependencias"),
    ("mantenimiento", "mantenimiento", "Mantenimiento preventivo y correctivo"),
    ("verificador", "verificacion", "Verificación de resultados y validación"),
    ("gestion", "gestion", "Gestión de proyectos y recursos"),
    ("comunicacion", "comunicacion", "Comunicaciones y redacción"),
    ("manuales", "manuales", "Documentación y manuales"),
    ("trazabilidad", "trazabilidad", "Registro de trazabilidad y auditoría"),
    ("creativa", "creativa", "Tareas creativas y diseño"),
    ("marketing", "marketing", "Marketing y comunicación externa"),
    ("investigador", "investigacion", "Investigación académica y técnica"),
    ("ensamblador", "ensamblado", "Ensamblado y síntesis de resultados"),
    ("lenguaje", "lenguaje", "Vocabulario controlado y coherencia lingüística"),
    ("backup", "backup", "Copias de seguridad"),
    ("contexto", "contexto", "Gestión de contexto conversacional"),
    ("prioridades", "prioridades", "Priorización de tareas"),
    ("alertas", "alertas", "Sistema de alertas y notificaciones"),
    ("gerente", "gestion", "Gerencia y supervisión de agentes"),
    ("validador", "verificacion", "Validación final de propuestas"),
    ("recepcionista", "comunicacion", "Recepción y enrutamiento inicial"),
    ("camaras", "camaras", "Monitorización visual y detección"),
]


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------


def log(msg: str, nivel: str = "INFO"):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    linea = f"[{ts}] [{nivel}] {msg}"
    print(linea, flush=True)
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(linea + "\n")


def ollama_disponible() -> bool:
    try:
        with urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=3) as r:  # nosec B310
            return r.status == 200
    except Exception:
        return False


def ollama_modelos_activos() -> set[str]:
    """Devuelve el conjunto de modelos disponibles en Ollama."""
    try:
        with urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=5) as r:  # nosec B310
            data = json.loads(r.read())
        return {m["name"].split(":")[0] for m in data.get("models", [])}
    except Exception:
        return set()


def ollama_chat(modelo: str, system: str, mensaje: str, timeout: int = 30) -> str | None:
    payload = json.dumps(
        {
            "model": modelo,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": mensaje},
            ],
            "stream": False,
        }
    ).encode()
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # nosec B310
            return json.loads(resp.read())["message"]["content"].strip()
    except Exception as e:
        log(f"ollama_chat error modelo={modelo}: {e}", "ERROR")
        return None


# ---------------------------------------------------------------------------
# Gestor de Vocabulario
# ---------------------------------------------------------------------------


class GestorVocabulario:
    """Carga, gestiona y actualiza vocabularios por tipo de agente."""

    def __init__(self):
        self._cache: dict[str, list[str]] = {}
        self._terminos_globales: list[str] = []
        self._cargar_todo()

    def _cargar_todo(self):
        """Carga todos los archivos de vocabulario."""
        for f in VOC_DIR.glob("*.txt"):
            nombre = f.stem  # "tecnico", "conductor", "creativo"
            terminos = [
                l.strip()
                for l in f.read_text(encoding="utf-8").splitlines()
                if l.strip() and not l.startswith("#")
            ]
            self._cache[nombre] = terminos
        log(f"Vocabularios cargados: {list(self._cache.keys())}")

    def para_tipo(self, tipo: str) -> list[str]:
        """Devuelve la lista de términos aplicable a un tipo de agente."""
        archivos = VOCABULARIO_POR_TIPO.get(tipo, ["tecnico.txt"])
        terminos: list[str] = []
        for arch in archivos:
            nombre = Path(arch).stem
            terminos.extend(self._cache.get(nombre, []))
        return list(dict.fromkeys(terminos))  # deduplicado preservando orden

    def terminos_globales(self) -> list[str]:
        return self._terminos_globales

    def incorporar_aprendizaje(self) -> int:
        """
        Lee vocabulario_extraido.txt del último ciclo de aprendizaje y añade
        los términos nuevos al vocabulario técnico. Devuelve nº de términos añadidos.
        """
        voc_extraido = APRENDIZAJE / "vocabulario_extraido.txt"
        if not voc_extraido.exists():
            log("No hay vocabulario_extraido.txt en ultimo/", "WARN")
            return 0

        nuevos = [
            l.strip()
            for l in voc_extraido.read_text(encoding="utf-8").splitlines()
            if l.strip() and not l.startswith("#")
        ]

        tecnico_path = VOC_DIR / "tecnico.txt"
        existentes = set(self._cache.get("tecnico", []))
        añadidos = [t for t in nuevos if t not in existentes and len(t) > 2]

        if añadidos:
            with open(tecnico_path, "a", encoding="utf-8") as f:
                f.write("\n# — incorporado desde aprendizaje semanal —\n")
                f.write("\n".join(añadidos) + "\n")
            self._cache.setdefault("tecnico", []).extend(añadidos)
            self._terminos_globales.extend(añadidos)
            log(f"Vocabulario técnico enriquecido: +{len(añadidos)} términos")
        else:
            log("Vocabulario ya actualizado — sin términos nuevos")

        return len(añadidos)

    def construir_contexto_vocabulario(self, tipo: str) -> str:
        """Construye el bloque de contexto de vocabulario para inyectar en prompts."""
        terminos = self.para_tipo(tipo)
        if not terminos:
            return ""
        return (
            "\nVOCABULARIO CONTROLADO DEL SISTEMA URA "
            "(usa preferentemente estos términos en tus respuestas):\n"
            + ", ".join(terminos[:60])  # límite para no inflar el prompt
        )


# ---------------------------------------------------------------------------
# Registro de Agentes
# ---------------------------------------------------------------------------


class RegistroAgentes:
    """Mantiene el registro de estado de todos los agentes del sistema."""

    def __init__(self, gestor_voc: GestorVocabulario):
        self._voc = gestor_voc
        self._registro: dict[str, dict] = {}
        self._cargar_o_inicializar()

    def _cargar_o_inicializar(self):
        if REGISTRO_AGENTES_JSON.exists():
            try:
                self._registro = json.loads(REGISTRO_AGENTES_JSON.read_text(encoding="utf-8"))
                log(f"Registro cargado: {len(self._registro)} agentes")
                return
            except Exception as e:
                logger.warning(f"Error silencioso en agente_lenguaje.load_registry: {e}")
                # fallback: archivo vacío

        # Primera vez — construir desde DEFINICION_AGENTES
        for nombre, tipo, desc in DEFINICION_AGENTES:
            self._registro[nombre] = {
                "nombre": nombre,
                "tipo": tipo,
                "descripcion": desc,
                "modelo": MODELO_POR_TIPO.get(tipo, nombre),
                "vocabulario": self._voc.para_tipo(tipo),
                "estado": "desconocido",
                "ultimo_ping": None,
            }
        self._guardar()
        log(f"Registro inicializado: {len(self._registro)} agentes")

    def _guardar(self):
        REGISTRO_AGENTES_JSON.write_text(
            json.dumps(self._registro, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def actualizar_estados(self) -> dict[str, str]:
        """Ping a Ollama y actualiza estado de cada agente. Devuelve {nombre: estado}."""
        activos = ollama_modelos_activos()
        ahora = datetime.now().isoformat()
        estados: dict[str, str] = {}

        for nombre, info in self._registro.items():
            base = info.get("modelo", nombre)
            estado = "activo" if base in activos or nombre in activos else "inactivo"
            self._registro[nombre]["estado"] = estado
            self._registro[nombre]["ultimo_ping"] = ahora
            estados[nombre] = estado

        self._guardar()
        n_activos = sum(1 for e in estados.values() if e == "activo")
        log(f"Estado actualizado: {n_activos}/{len(estados)} agentes activos")
        return estados

    def registrar(self, nombre: str, modelo: str, tipo: str, descripcion: str = ""):
        """Registra un nuevo agente o actualiza uno existente."""
        self._registro[nombre] = {
            "nombre": nombre,
            "tipo": tipo,
            "descripcion": descripcion,
            "modelo": modelo,
            "vocabulario": self._voc.para_tipo(tipo),
            "estado": "registrado",
            "ultimo_ping": datetime.now().isoformat(),
        }
        self._guardar()
        log(f"Agente registrado: {nombre} (modelo={modelo}, tipo={tipo})")

    def obtener(self, nombre: str) -> dict | None:
        return self._registro.get(nombre)

    def listar(self, solo_activos: bool = False) -> list[dict]:
        agentes = list(self._registro.values())
        if solo_activos:
            agentes = [a for a in agentes if a.get("estado") == "activo"]
        return agentes

    def vocabulario_de(self, nombre: str) -> list[str]:
        info = self._registro.get(nombre, {})
        return info.get("vocabulario", [])

    def exportar_resumen(self) -> str:
        """Texto compacto del estado del registro para inyectar en prompts."""
        activos = [a["nombre"] for a in self.listar() if a.get("estado") == "activo"]
        inactivos = [a["nombre"] for a in self.listar() if a.get("estado") != "activo"]
        return (
            f"AGENTES ACTIVOS ({len(activos)}): {', '.join(activos[:15])}\n"
            f"AGENTES INACTIVOS ({len(inactivos)}): {', '.join(inactivos[:10])}"
        )


# ---------------------------------------------------------------------------
# Ensamblador de Resultados
# ---------------------------------------------------------------------------


class EnsambladorResultados:
    """
    Toma outputs de múltiples agentes y construye una respuesta única, coherente
    y con vocabulario controlado usando el modelo `ensamblador` de Ollama.
    """

    def __init__(self, gestor_voc: GestorVocabulario, registro: RegistroAgentes):
        self._voc = gestor_voc
        self._registro = registro

    def ensamblar(
        self,
        resultados: list[dict],
        tarea: str = "",
        tipo: str = "ensamblado",
        usar_llm: bool = True,
    ) -> str:
        """
        Parámetros:
            resultados  — lista de {"agente": str, "resultado": str, "ok": bool}
            tarea       — título de la tarea original
            tipo        — tipo de tarea (para elegir vocabulario)
            usar_llm    — si True usa el modelo ensamblador; si False, concatenación simple

        Devuelve: str con la respuesta ensamblada
        """
        if not resultados:
            return "[AgenteLenguaje] Sin resultados que ensamblar."

        # Filtrar solo los exitosos
        exitosos = [r for r in resultados if r.get("ok", True)]
        if not exitosos:
            errores = [r.get("resultado", "") for r in resultados]
            return f"[AgenteLenguaje] Todos los agentes fallaron. Errores: {'; '.join(errores[:3])}"

        # Si solo hay un resultado y es corto, devolver directamente
        if len(exitosos) == 1 and len(exitosos[0].get("resultado", "")) < 600:
            resultado = exitosos[0]["resultado"]
            return self._aplicar_vocabulario(resultado, tipo)

        if not usar_llm or not ollama_disponible():
            return self._ensamblar_simple(exitosos, tipo)

        return self._ensamblar_con_llm(exitosos, tarea, tipo)

    def _ensamblar_simple(self, resultados: list[dict], tipo: str) -> str:
        """Concatenación estructurada sin LLM."""
        partes = []
        for r in resultados:
            agente = r.get("agente", "agente")
            texto = r.get("resultado", "").strip()
            if texto:
                partes.append(f"[{agente}] {texto}")
        combinado = "\n\n".join(partes)
        return self._aplicar_vocabulario(combinado, tipo)

    def _ensamblar_con_llm(self, resultados: list[dict], tarea: str, tipo: str) -> str:
        """Usa el modelo `ensamblador` para sintetizar."""
        ctx_vocab = self._voc.construir_contexto_vocabulario(tipo)
        ctx_agentes = self._registro.exportar_resumen()

        # Construir el bloque de resultados
        bloque = "\n\n".join(
            f"--- Agente {r.get('agente', '?')} ---\n{r.get('resultado', '').strip()}"
            for r in resultados
        )

        system = (
            "Eres el ENSAMBLADOR del sistema URA. "
            "Recibes los resultados de varios agentes especializados sobre la misma tarea "
            "y los sintetizas en una respuesta única, coherente y sin redundancias. "
            "Mantén los hechos concretos, elimina duplicados, resuelve contradicciones "
            "priorizando el agente más especializado. Responde en español." + ctx_vocab
        )

        mensaje = (
            f"TAREA: {tarea}\n\n"
            f"RESULTADOS DE LOS AGENTES:\n{bloque}\n\n"
            f"CONTEXTO DEL SISTEMA:\n{ctx_agentes}\n\n"
            "Sintetiza los resultados anteriores en una respuesta final concisa y coherente."
        )

        respuesta = ollama_chat("ensamblador", system, mensaje, timeout=60)

        if not respuesta:
            log("Ensamblador LLM no respondió — usando fallback simple", "WARN")
            return self._ensamblar_simple(resultados, tipo)

        return self._aplicar_vocabulario(respuesta, tipo)

    def _aplicar_vocabulario(self, texto: str, tipo: str) -> str:
        """
        Verifica que los términos del vocabulario controlado estén bien usados.
        Por ahora: pass-through — en versiones futuras puede hacer corrección terminológica.
        """
        return texto


# ---------------------------------------------------------------------------
# AgenteLenguaje — clase principal
# ---------------------------------------------------------------------------


class AgenteLenguaje:
    """
    Punto de entrada principal del Agente de Lenguaje.
    Instanciar una vez y reusar (carga archivos en __init__).
    """

    def __init__(self):
        log("AgenteLenguaje inicializando...")
        self.vocabulario = GestorVocabulario()
        self.registro = RegistroAgentes(self.vocabulario)
        self.ensamblador = EnsambladorResultados(self.vocabulario, self.registro)
        self._ultimo_ping = 0.0
        log("AgenteLenguaje listo")

    # ── API pública ──────────────────────────────────────────────────────────

    def ensamblar(
        self,
        resultados: list[dict],
        tarea: str = "",
        tipo: str = "ensamblado",
    ) -> str:
        """
        Punto de entrada para el orquestador.
        Ensambla los resultados de múltiples agentes.
        """
        return self.ensamblador.ensamblar(resultados, tarea, tipo)

    def vocabulario_para(self, nombre_agente: str) -> list[str]:
        """Devuelve el vocabulario asignado a un agente concreto."""
        return self.registro.vocabulario_de(nombre_agente)

    def prompt_con_vocabulario(self, tipo: str, system_base: str) -> str:
        """Enriquece un system prompt con el vocabulario controlado del tipo."""
        return system_base + self.vocabulario.construir_contexto_vocabulario(tipo)

    def actualizar_registro(self) -> dict[str, str]:
        """Actualiza el estado de todos los agentes y devuelve el mapa nombre→estado."""
        ahora = time.monotonic()
        if ahora - self._ultimo_ping > 60:  # no más de una vez por minuto
            estados = self.registro.actualizar_estados()
            self._ultimo_ping = ahora
            return estados
        return {a["nombre"]: a.get("estado", "?") for a in self.registro.listar()}

    def incorporar_aprendizaje(self) -> int:
        """Incorpora el vocabulario extraído del último ciclo semanal."""
        return self.vocabulario.incorporar_aprendizaje()

    def estado_json(self) -> dict:
        """Devuelve el estado completo en formato serializable."""
        self.actualizar_registro()
        return {
            "timestamp": datetime.now().isoformat(),
            "agentes_total": len(self.registro.listar()),
            "agentes_activos": len(self.registro.listar(solo_activos=True)),
            "vocabularios": {
                k: len(v)
                for k, v in {n: self.vocabulario.para_tipo(n) for n in VOCABULARIO_POR_TIPO}.items()
            },
            "agentes": self.registro.listar(),
        }

    def resumen_texto(self) -> str:
        """Texto legible del estado para logs y panel."""
        estado = self.estado_json()
        return (
            f"AgenteLenguaje — {estado['agentes_activos']}/{estado['agentes_total']} agentes activos\n"
            + self.registro.exportar_resumen()
        )


# ---------------------------------------------------------------------------
# Singleton para importación desde el orquestador
# ---------------------------------------------------------------------------

_instancia: AgenteLenguaje | None = None


def get_agente_lenguaje() -> AgenteLenguaje:
    """Devuelve la instancia singleton del AgenteLenguaje."""
    global _instancia
    if _instancia is None:
        _instancia = AgenteLenguaje()
    return _instancia


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Agente de Lenguaje URA")
    parser.add_argument("--estado", action="store_true", help="Mostrar estado del registro")
    parser.add_argument(
        "--incorporar", action="store_true", help="Incorporar vocabulario de aprendizaje"
    )
    parser.add_argument("--actualizar", action="store_true", help="Actualizar estados de agentes")
    parser.add_argument("--ensamblar", metavar="FILE", help="Ensamblar resultados desde JSON")
    args = parser.parse_args()

    al = AgenteLenguaje()

    if args.estado:
        print(al.resumen_texto())
        estado = al.estado_json()
        print("\nVocabularios:")
        for tipo, n in estado["vocabularios"].items():
            print(f"  {tipo:20s} {n} términos")

    elif args.incorporar:
        n = al.incorporar_aprendizaje()
        print(f"Incorporados {n} términos nuevos al vocabulario técnico.")

    elif args.actualizar:
        estados = al.actualizar_registro()
        activos = [k for k, v in estados.items() if v == "activo"]
        print(f"Activos ({len(activos)}): {', '.join(activos)}")

    elif args.ensamblar:
        ruta = Path(args.ensamblar)
        if not ruta.exists():
            print(f"ERROR: {ruta} no existe", file=sys.stderr)
            sys.exit(1)
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        resultados = datos.get("resultados", datos)
        tarea = datos.get("tarea", "")
        tipo = datos.get("tipo", "ensamblado")
        print(al.ensamblar(resultados, tarea, tipo))

    else:
        parser.print_help()

    def procesar(self, texto: str) -> str:
        """Procesar consulta para GestorVocabulario."""
        texto.lower()
        return "Puedo procesar lenguaje, traducir y hacer NLP. ¿Qué tarea de lenguaje necesitas?"

    def ejecutar(self, texto: str) -> str:
        """Ejecutar acción para GestorVocabulario."""
        return self.procesar(texto)

    def consultar(self, texto: str) -> str:
        """Consultar información para GestorVocabulario."""
        return self.procesar(texto)

    def responder(self, texto: str) -> str:
        """Responder pregunta para GestorVocabulario."""
        return self.procesar(texto)


if __name__ == "__main__":
    main()
