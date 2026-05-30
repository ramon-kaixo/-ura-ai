#!/usr/bin/env python3
"""
Sistema de vocabularios técnicos por departamento + cristal limitador de tiempo.

8 departamentos con vocabularios precisos. Solo el Creativo permite sinónimos.
CrystalLimiter aplica timeouts por departamento.
"""

import functools
import json
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

VOCAB_DIR = Path.home() / ".ura" / "vocabulary"
VOCAB_DIR.mkdir(parents=True, exist_ok=True)
TIMEOUT_LOG_PATH = Path.home() / ".ura" / "crystal_timeouts.json"


# ═══════════════════════════════════════════════════════════
# 1. TechnicalVocabulary
# ═══════════════════════════════════════════════════════════


class TechnicalVocabulary:
    def __init__(
        self,
        department_name: str,
        terms: dict = None,
        sources: list = None,
        allow_synonyms: bool = False,
        max_response_time: int = 60,
    ):
        self.department_name = department_name
        self.terms = terms or {}
        self.sources = sources or []
        self.allow_synonyms = allow_synonyms
        self.max_response_time = max_response_time

    def to_dict(self) -> dict:
        return {
            "department_name": self.department_name,
            "terms": self.terms,
            "sources": self.sources,
            "allow_synonyms": self.allow_synonyms,
            "max_response_time": self.max_response_time,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TechnicalVocabulary":
        return cls(**data)

    def load_from_file(self, path: Path) -> bool:
        if not path.exists():
            return False
        try:
            with open(path) as f:
                data = json.load(f)
            self.terms = data.get("terms", self.terms)
            self.sources = data.get("sources", self.sources)
            self.allow_synonyms = data.get("allow_synonyms", self.allow_synonyms)
            self.max_response_time = data.get("max_response_time", self.max_response_time)
            return True
        except Exception as e:
            logger.warning(f"Error cargando vocabulario {path}: {e}")
            return False

    def save_to_file(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)

    def add_term(self, term: str, definition: str, source: str = ""):
        self.terms[term.lower()] = {
            "definition": definition,
            "source": source,
            "added": datetime.now().isoformat(),
        }
        if source and source not in self.sources:
            self.sources.append(source)

    def get_definition(self, term: str) -> str | None:
        entry = self.terms.get(term.lower())
        if entry is None:
            return None
        if isinstance(entry, dict):
            return entry.get("definition")
        return entry

    def search_terms(self, query: str) -> list[str]:
        q = query.lower()
        results = []
        for term, entry in self.terms.items():
            definition = entry.get("definition", "") if isinstance(entry, dict) else str(entry)
            if q in term or q in definition.lower():
                results.append(term)
        return results

    def update_from_research(self, topic: str, findings: dict):
        """Actualizar vocabulario con hallazgos del ResearchPipeline."""
        report = findings.get("full_report", "")
        if not report:
            return
        added = 0
        # Heurística simple: si el topic no está, lo añade como término
        if topic.lower() not in self.terms:
            summary = findings.get("executive_summary", "")[:500]
            self.add_term(topic, summary or report[:300], source="ResearchPipeline")
            added += 1
        if added:
            logger.info(f"{self.department_name}: {added} términos añadidos desde research")

    def get_context_for_prompt(self) -> str:
        if not self.terms:
            return ""
        parts = [f"VOCABULARIO TÉCNICO ({self.department_name}):"]
        if not self.allow_synonyms:
            parts.append("REGLA: Usar terminología precisa SIN sinónimos.")
        else:
            parts.append("REGLA: Departamento creativo — sinónimos y figuras permitidos.")
        for term, entry in list(self.terms.items())[:15]:
            definition = entry.get("definition", "") if isinstance(entry, dict) else str(entry)
            parts.append(f"  - {term}: {definition[:100]}")
        return "\n".join(parts) + "\n"


# ═══════════════════════════════════════════════════════════
# 2. CrystalLimiter
# ═══════════════════════════════════════════════════════════

DEFAULT_LIMITS = {
    "creativo": 120,
    "investigacion": 90,
    "software": 60,
    "contable": 45,
    "seguridad": 30,
    "mantenimiento": 30,
    "auditoria": 45,
    "memoria": 30,
}


class CrystalTimeout(Exception):
    pass


class CrystalLimiter:
    def __init__(self):
        self.time_limits = dict(DEFAULT_LIMITS)
        self.timeouts_log = self._load_log()

    def _load_log(self) -> list[dict]:
        if TIMEOUT_LOG_PATH.exists():
            try:
                with open(TIMEOUT_LOG_PATH) as f:
                    return json.load(f)
            except Exception:
                pass
        return []

    def _save_log(self):
        with open(TIMEOUT_LOG_PATH, "w") as f:
            json.dump(self.timeouts_log[-500:], f, indent=2)

    def get_limit(self, department: str) -> int:
        return self.time_limits.get(department.lower(), 60)

    def check_timeout(self, department: str, start_time: float) -> bool:
        elapsed = time.time() - start_time
        return elapsed > self.get_limit(department)

    def log_timeout(self, department: str, task: str = ""):
        self.timeouts_log.append(
            {
                "timestamp": datetime.now().isoformat(),
                "department": department.lower(),
                "task": task,
                "limit": self.get_limit(department),
            }
        )
        self._save_log()
        logger.warning(f"CrystalLimiter: timeout en {department} ({task})")

    def recent_timeouts(self, department: str, hours: int = 1) -> int:
        cutoff = datetime.now() - timedelta(hours=hours)
        count = 0
        for t in self.timeouts_log:
            if t.get("department") != department.lower():
                continue
            try:
                ts = datetime.fromisoformat(t.get("timestamp", ""))
                if ts >= cutoff:
                    count += 1
            except Exception:
                continue
        return count

    def decorate(self, department: str):
        """Decorador para aplicar timeout a una función."""
        limit = self.get_limit(department)

        def wrapper(func):
            @functools.wraps(func)
            def inner(*args, **kwargs):
                start = time.time()
                result = func(*args, **kwargs)
                if time.time() - start > limit:
                    self.log_timeout(department, func.__name__)
                    raise CrystalTimeout(f"{department}: excedió {limit}s en {func.__name__}")
                return result

            return inner

        return wrapper


_crystal_limiter: CrystalLimiter | None = None


def get_crystal_limiter() -> CrystalLimiter:
    global _crystal_limiter
    if _crystal_limiter is None:
        _crystal_limiter = CrystalLimiter()
    return _crystal_limiter


# ═══════════════════════════════════════════════════════════
# 3. Vocabularios predefinidos
# ═══════════════════════════════════════════════════════════

PREDEFINED_VOCABULARIES = {
    "contable": {
        "allow_synonyms": False,
        "max_response_time": 45,
        "terms": {
            "irpf": "Impuesto sobre la Renta de las Personas Físicas. Tributo directo y progresivo en España.",
            "iva": "Impuesto sobre el Valor Añadido. Tipos general (21%), reducido (10%), superreducido (4%).",
            "nomina": "Documento que detalla la retribución mensual de un trabajador y las deducciones aplicadas.",
            "convenio_colectivo": "Acuerdo entre empresarios y representantes de trabajadores que regula condiciones laborales.",
            "seguridad_social": "Sistema público de protección que cubre contingencias laborales y prestaciones.",
            "modelo_303": "Declaración trimestral del IVA en España.",
            "modelo_111": "Declaración trimestral de retenciones e ingresos a cuenta del IRPF.",
            "modelo_390": "Resumen anual del IVA.",
            "base_imponible": "Importe sobre el que se aplica el tipo impositivo para calcular la cuota tributaria.",
            "retencion": "Cantidad detraída del salario o factura para ingresar a Hacienda a cuenta del impuesto.",
            "autonomo": "Trabajador por cuenta propia inscrito en el RETA.",
            "epigrafe_iae": "Código de actividad económica usado en el Impuesto sobre Actividades Económicas.",
        },
    },
    "software": {
        "allow_synonyms": False,
        "max_response_time": 60,
        "terms": {
            "patron_singleton": "Patrón de diseño que garantiza una única instancia de una clase.",
            "antipatron": "Solución aparente que en la práctica genera más problemas que beneficios.",
            "pep8": "Guía de estilo oficial para código Python.",
            "tdd": "Test-Driven Development. Escribir tests antes que la implementación.",
            "pytest": "Framework de testing para Python.",
            "linter": "Herramienta de análisis estático que detecta errores y violaciones de estilo.",
            "cicd": "Continuous Integration / Continuous Deployment.",
            "git_rebase": "Reescribir el historial de commits aplicándolos sobre otra base.",
            "regresion": "Bug que reaparece tras haber sido corregido.",
            "race_condition": "Error por orden no determinista de operaciones concurrentes.",
            "deadlock": "Bloqueo mutuo entre procesos que esperan recursos del otro.",
            "n_plus_one": "Antipatrón ORM: ejecutar N+1 consultas cuando bastaría con una.",
        },
    },
    "seguridad": {
        "allow_synonyms": False,
        "max_response_time": 30,
        "terms": {
            "cve": "Common Vulnerabilities and Exposures. Identificador único de vulnerabilidad pública.",
            "cvss": "Common Vulnerability Scoring System. Puntuación de severidad de 0 a 10.",
            "tls": "Transport Layer Security. Protocolo criptográfico para comunicaciones seguras.",
            "aes": "Advanced Encryption Standard. Cifrado simétrico de bloque.",
            "rsa": "Algoritmo de cifrado asimétrico basado en factorización de primos grandes.",
            "mfa": "Multi-Factor Authentication. Autenticación con 2 o más factores.",
            "csrf": "Cross-Site Request Forgery. Ataque que fuerza acciones autenticadas en otro sitio.",
            "xss": "Cross-Site Scripting. Inyección de scripts en páginas web vistas por terceros.",
            "sqli": "SQL Injection. Inyección de código SQL malicioso.",
            "zero_day": "Vulnerabilidad explotada antes de que exista un parche público.",
            "fingerprint": "Huella digital criptográfica para identificar claves o certificados.",
            "salting": "Añadir datos aleatorios antes de hashear contraseñas.",
        },
    },
    "mantenimiento": {
        "allow_synonyms": False,
        "max_response_time": 30,
        "terms": {
            "snapshot": "Copia puntual del estado de un sistema o archivo.",
            "rollback": "Revertir cambios al estado anterior conocido como bueno.",
            "pruning": "Eliminar datos antiguos o irrelevantes para liberar espacio.",
            "health_check": "Verificación periódica del estado de un servicio.",
            "watchdog": "Proceso que vigila a otros y reinicia si fallan.",
            "log_rotation": "Mecanismo para archivar y eliminar logs antiguos automáticamente.",
            "cron": "Planificador de tareas en Unix/Linux/macOS.",
            "backup_incremental": "Backup que solo guarda los cambios desde el último.",
            "backup_completo": "Backup íntegro de todos los datos.",
            "checksum": "Suma de verificación que detecta corrupción de datos.",
            "uptime": "Tiempo continuo en funcionamiento sin reinicios.",
            "graceful_shutdown": "Apagado controlado que permite terminar tareas en curso.",
        },
    },
    "auditoria": {
        "allow_synonyms": False,
        "max_response_time": 45,
        "terms": {
            "evento": "Registro inmutable de una acción ocurrida en el sistema.",
            "correlacion": "Relación detectada entre dos o más eventos del historial.",
            "forense": "Análisis sistemático posterior a un incidente para determinar causa.",
            "trazabilidad": "Capacidad de seguir una acción desde el origen hasta el destino.",
            "detonante": "Evento previo que causa o precede a otro evento.",
            "cadena_de_custodia": "Secuencia documentada que prueba la integridad de la evidencia.",
            "auditoria_log": "Archivo append-only donde se registran acciones para revisión posterior.",
            "anomalia": "Desviación estadística respecto al comportamiento normal.",
            "siem": "Security Information and Event Management. Sistema de correlación de eventos.",
            "compliance": "Cumplimiento de normativa aplicable (RGPD, ISO27001, etc.).",
            "patron_sistemico": "Anomalía que se repite estructuralmente, indicando causa profunda.",
            "linea_base": "Comportamiento normal de referencia contra el que se comparan eventos.",
        },
    },
    "memoria": {
        "allow_synonyms": False,
        "max_response_time": 30,
        "terms": {
            "embedding": "Vector denso que representa semánticamente un texto o entidad.",
            "contexto": "Conjunto de información relevante disponible para una consulta.",
            "persistencia": "Capacidad de mantener datos entre ejecuciones.",
            "indexacion": "Estructura que acelera la recuperación de información.",
            "recuperacion": "Proceso de obtener datos previamente almacenados.",
            "rag": "Retrieval-Augmented Generation. Generación con recuperación de contexto.",
            "vectorstore": "Base de datos optimizada para búsqueda por similitud de vectores.",
            "ttl": "Time To Live. Tiempo de validez de una entrada en caché.",
            "cache_lru": "Least Recently Used. Estrategia de evicción por menor uso reciente.",
            "memoria_episodica": "Memoria de eventos concretos vividos.",
            "memoria_semantica": "Memoria de hechos generales y conceptos.",
            "checkpoint": "Punto de guardado del estado para reanudación posterior.",
        },
    },
    "vocabulario": {
        "allow_synonyms": False,
        "max_response_time": 30,
        "terms": {
            "sintaxis": "Reglas de combinación de palabras para formar oraciones válidas.",
            "semantica": "Estudio del significado de las expresiones lingüísticas.",
            "pragmatica": "Estudio del lenguaje en contexto y su uso comunicativo.",
            "morfologia": "Estudio de la estructura interna de las palabras.",
            "fonetica": "Estudio de los sonidos del habla.",
            "lexema": "Unidad léxica con significado independiente.",
            "morfema": "Unidad mínima con significado gramatical.",
            "protocolo": "Conjunto de reglas que rigen una comunicación.",
            "registro": "Variedad de lengua según el contexto comunicativo.",
            "ambiguedad": "Posibilidad de interpretar un enunciado de varios modos.",
            "deixis": "Referencia contextual (yo, aquí, ahora).",
            "anafora": "Referencia a un elemento mencionado previamente.",
        },
    },
    "investigacion": {
        "allow_synonyms": False,
        "max_response_time": 90,
        "terms": {
            "paper": "Artículo científico revisado por pares.",
            "preprint": "Versión preliminar de un paper antes de revisión.",
            "doi": "Digital Object Identifier. Identificador persistente de publicación.",
            "abstract": "Resumen estructurado al inicio de un paper.",
            "metaanalisis": "Síntesis estadística de múltiples estudios sobre un mismo tema.",
            "revision_sistematica": "Revisión exhaustiva con metodología explícita y reproducible.",
            "sesgo_publicacion": "Tendencia a publicar resultados positivos y omitir negativos.",
            "p_value": "Probabilidad de observar el resultado bajo la hipótesis nula.",
            "intervalo_confianza": "Rango que probablemente contiene el valor verdadero.",
            "hipotesis_nula": "Suposición de no efecto contra la que se contrasta.",
            "reproducibilidad": "Capacidad de obtener los mismos resultados con los mismos datos y métodos.",
            "fuente_primaria": "Documento original donde se reporta el hallazgo por primera vez.",
        },
    },
    "creativo": {
        "allow_synonyms": True,
        "max_response_time": 120,
        "terms": {
            "metafora": "Sustitución de un término por otro con el que guarda semejanza.",
            "metonimia": "Sustitución basada en relación de contigüidad (causa-efecto, parte-todo).",
            "sinonimia": "Relación entre palabras de significado similar.",
            "antonimia": "Relación entre palabras de significado opuesto.",
            "polisemia": "Capacidad de una palabra de tener varios significados relacionados.",
            "hiperbole": "Exageración intencionada con fines expresivos.",
            "ironia": "Decir lo contrario de lo que se quiere expresar, con intención evidente.",
            "anafora_retorica": "Repetición de una palabra al inicio de varias frases.",
            "aliteracion": "Repetición de sonidos similares en palabras cercanas.",
            "storytelling": "Técnica de comunicación basada en narrativa.",
            "copywriting": "Redacción persuasiva orientada a la acción del lector.",
            "call_to_action": "Llamada explícita a realizar una acción.",
            "aida": "Atención, Interés, Deseo, Acción. Modelo clásico de persuasión.",
            "pirámide_invertida": "Estructura informativa: lo más importante al inicio.",
            "tono_de_voz": "Personalidad expresiva consistente de una marca o autor.",
        },
    },
}


# ═══════════════════════════════════════════════════════════
# 4. VocabularyManager
# ═══════════════════════════════════════════════════════════


class VocabularyManager:
    def __init__(self):
        self.vocabularies: dict[str, TechnicalVocabulary] = {}
        self.initialize_all()

    def initialize_all(self):
        """Cargar 8 vocabularios desde disco; si no existen, crearlos."""
        for dept_name, default in PREDEFINED_VOCABULARIES.items():
            file_path = VOCAB_DIR / f"{dept_name}.json"
            vocab = TechnicalVocabulary(
                department_name=dept_name,
                allow_synonyms=default["allow_synonyms"],
                max_response_time=default["max_response_time"],
            )
            if file_path.exists():
                vocab.load_from_file(file_path)
            else:
                # Inicializar con términos predefinidos
                for term, definition in default["terms"].items():
                    vocab.add_term(term, definition, source="predefined")
                vocab.save_to_file(file_path)
            self.vocabularies[dept_name] = vocab

    def get_vocabulary(self, department: str) -> TechnicalVocabulary | None:
        return self.vocabularies.get(department.lower())

    def update_from_knowledge_base(self) -> dict:
        """Actualizar vocabularios desde la biblioteca local del Archivist."""
        try:
            from core.research_pipeline import get_knowledge_archivist

            arc = get_knowledge_archivist()
            stats = {}
            for dept, vocab in self.vocabularies.items():
                hits = arc.search_local(dept)
                if hits:
                    for h in hits:
                        url = h.get("url", "")
                        if url and url not in vocab.sources:
                            vocab.sources.append(url)
                    vocab.save_to_file(VOCAB_DIR / f"{dept}.json")
                    stats[dept] = len(hits)
            return stats
        except Exception as e:
            logger.debug(f"update_from_knowledge_base error: {e}")
            return {}

    def update_from_research(self, topic: str) -> str:
        """Determinar departamento por topic y actualizar su vocabulario."""
        try:
            from core.research_pipeline import get_research_pipeline

            pipe = get_research_pipeline()
            findings = pipe.execute(topic)

            # Heurística: detectar departamento por keywords
            topic_lower = topic.lower()
            keyword_map = {
                "contable": ["irpf", "iva", "fiscal", "nómina", "convenio", "tributo"],
                "software": ["código", "python", "bug", "test", "patrón", "git"],
                "seguridad": ["seguridad", "vulnerabilidad", "cifrado", "cve", "auth"],
                "mantenimiento": ["backup", "snapshot", "rollback", "log", "health"],
                "auditoria": ["auditoría", "forense", "evento", "correlación"],
                "memoria": ["memoria", "embedding", "cache", "índice", "rag"],
                "vocabulario": ["sintaxis", "semántica", "lengua", "gramática"],
                "creativo": ["metáfora", "narrativa", "marketing", "persuasión", "story"],
                "investigacion": ["paper", "estudio", "investigación", "ciencia"],
            }
            target_dept = "investigacion"
            for dept, kws in keyword_map.items():
                if any(kw in topic_lower for kw in kws):
                    target_dept = dept
                    break

            vocab = self.vocabularies.get(target_dept)
            if vocab:
                vocab.update_from_research(topic, findings)
                vocab.save_to_file(VOCAB_DIR / f"{target_dept}.json")
            return target_dept
        except Exception as e:
            logger.debug(f"update_from_research error: {e}")
            return ""

    def get_unified_context(self, department: str) -> str:
        vocab = self.get_vocabulary(department)
        if not vocab:
            return ""
        return vocab.get_context_for_prompt()


_vocabulary_manager: VocabularyManager | None = None


def get_vocabulary_manager() -> VocabularyManager:
    global _vocabulary_manager
    if _vocabulary_manager is None:
        _vocabulary_manager = VocabularyManager()
    return _vocabulary_manager
