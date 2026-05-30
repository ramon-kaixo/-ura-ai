#!/usr/bin/env python3
"""
URA Tool Registry - Registro Centralizado de Herramientas
Sistema unificado para registrar, descubrir y gestionar todas las herramientas del sistema
"""

from collections.abc import Callable
from enum import Enum
from typing import TypedDict


# ============================================================
# CATEGORÍAS DE HERRAMIENTAS
# ============================================================
class ToolCategory(Enum):
    """Categorías de herramientas"""

    LLM = "llm"
    SEARCH = "search"
    MESSAGING = "messaging"
    STORAGE = "storage"
    DOCUMENT = "document"
    AUTOMATION = "automation"
    AUDIO = "audio"
    WEB = "web"


# ============================================================
# ESPECIFICACIÓN DE HERRAMIENTA
# ============================================================
class ToolSpec(TypedDict):
    """Especificación completa de una herramienta"""

    nombre: str
    categoria: ToolCategory
    descripcion: str
    funcion: Callable
    input_schema: dict
    output_schema: dict
    dependencias: list[str]
    uso_concurrente_max: int
    prioridad: int  # 1-10
    activo: bool
    version: str
    autor: str
    fecha_creacion: str
    fecha_actualizacion: str
    changelog: list[str]
    tags: list[str]
    vocabulario: dict[str, list[str]]
    test_function: Callable | None
    test_data: dict | None
    ejemplos_uso: list[str]
    notas: list[str]
    referencias: list[str]
    config_schema: dict
    config_default: dict
    metrics_enabled: bool
    metrics_to_track: list[str]
    cache_enabled: bool
    cache_ttl: int
    required_permissions: list[str]
    allowed_roles: list[str]


# ============================================================
# REGISTRO DE HERRAMIENTAS
# ============================================================
class ToolRegistry:
    """Registro centralizado de herramientas"""

    def __init__(self):
        self.tools: dict[str, ToolSpec] = {}
        self._init_default_tools()

    def _init_default_tools(self):
        """Inicializar herramientas por defecto"""
        # LLM Tools
        self._register_ollama()
        self._register_deepseek()
        self._register_claude()

        # Search Tools
        self._register_duckduckgo()
        self._register_google_search()

        # Messaging Tools
        self._register_telegram()
        self._register_slack()

        # Storage Tools
        self._register_postgresql()
        self._register_redis()

    def register(self, spec: ToolSpec) -> str:
        """Registrar herramienta"""
        tool_id = f"{spec['categoria'].value}_{spec['nombre']}"
        self.tools[tool_id] = spec
        return tool_id

    def get(self, tool_id: str) -> ToolSpec | None:
        """Obtener herramienta por ID"""
        return self.tools.get(tool_id)

    def list_by_category(self, categoria: ToolCategory) -> list[ToolSpec]:
        """Listar herramientas por categoría"""
        return [t for t in self.tools.values() if t["categoria"] == categoria]

    def get_available_tools(self) -> list[str]:
        """Obtener IDs de herramientas activas"""
        return [tid for tid, spec in self.tools.items() if spec["activo"]]

    def find_tools_by_tag(self, tag: str) -> list[ToolSpec]:
        """Encontrar herramientas por tag"""
        return [t for t in self.tools.values() if tag in t["tags"]]

    def deactivate(self, tool_id: str):
        """Desactivar herramienta"""
        if tool_id in self.tools:
            self.tools[tool_id]["activo"] = False

    def activate(self, tool_id: str):
        """Activar herramienta"""
        if tool_id in self.tools:
            self.tools[tool_id]["activo"] = True

    # ============================================================
    # REGISTRO DE HERRAMIENTAS POR DEFECTO
    # ============================================================
    def _register_ollama(self):
        """Registrar herramienta Ollama"""
        spec: ToolSpec = {
            "nombre": "ollama",
            "categoria": ToolCategory.LLM,
            "descripcion": "LLM local usando Ollama",
            "funcion": lambda: None,  # Placeholder
            "input_schema": {"prompt": {"type": "string", "required": True}},
            "output_schema": {"response": {"type": "string"}},
            "dependencias": ["ollama"],
            "uso_concurrente_max": 4,
            "prioridad": 10,
            "activo": True,
            "version": "1.0.0",
            "autor": "URA",
            "fecha_creacion": "2026-04-27",
            "fecha_actualizacion": "2026-04-27",
            "changelog": ["Inicial"],
            "tags": ["stable", "local"],
            "vocabulario": {
                "palabras_clave": ["consulta", "pregunta", "respuesta", "generar"],
                "terminos_tecnicos": ["inference", "prompt", "context window", "temperature"],
                "sinonimos": ["modelo", "ia", "llm", "chat"],
            },
            "test_function": None,
            "test_data": None,
            "ejemplos_uso": [
                "with TOOL_CONTEXT.open('llm_ollama') as ollama:",
                "    response = ollama.generate('Hola')",
                "    print(response)",
            ],
            "notas": [
                "Requiere Ollama corriendo en localhost:11434",
                "Modelo por defecto: gemma3:1b",
            ],
            "referencias": ["https://ollama.com/docs"],
            "config_schema": {
                "model": {"type": "string", "required": True},
                "temperature": {"type": "float", "min": 0.0, "max": 2.0, "default": 0.7},
                "max_tokens": {"type": "int", "min": 1, "max": 4096, "default": 512},
            },
            "config_default": {"model": "gemma3:1b", "temperature": 0.7, "max_tokens": 512},
            "metrics_enabled": True,
            "metrics_to_track": ["latency", "success_rate", "error_count", "tokens_used"],
            "cache_enabled": True,
            "cache_ttl": 300,
            "required_permissions": [],
            "allowed_roles": ["user", "admin"],
        }
        self.register(spec)

    def _register_deepseek(self):
        """Registrar herramienta DeepSeek"""
        spec: ToolSpec = {
            "nombre": "deepseek",
            "categoria": ToolCategory.LLM,
            "descripcion": "LLM cloud usando DeepSeek API",
            "funcion": lambda: None,
            "input_schema": {"prompt": {"type": "string", "required": True}},
            "output_schema": {"response": {"type": "string"}},
            "dependencias": ["deepseek_api"],
            "uso_concurrente_max": 2,
            "prioridad": 8,
            "activo": True,
            "version": "1.0.0",
            "autor": "URA",
            "fecha_creacion": "2026-04-27",
            "fecha_actualizacion": "2026-04-27",
            "changelog": ["Inicial"],
            "tags": ["cloud", "api"],
            "vocabulario": {
                "palabras_clave": ["consulta", "pregunta", "respuesta"],
                "terminos_tecnicos": ["api", "cloud", "inference"],
                "sinonimos": ["deepseek", "llm"],
            },
            "test_function": None,
            "test_data": None,
            "ejemplos_uso": [],
            "notas": ["Requiere API key de DeepSeek"],
            "referencias": ["https://platform.deepseek.com/docs"],
            "config_schema": {},
            "config_default": {},
            "metrics_enabled": True,
            "metrics_to_track": ["latency", "success_rate", "api_calls"],
            "cache_enabled": True,
            "cache_ttl": 600,
            "required_permissions": ["api_access"],
            "allowed_roles": ["admin"],
        }
        self.register(spec)

    def _register_claude(self):
        """Registrar herramienta Claude"""
        spec: ToolSpec = {
            "nombre": "claude",
            "categoria": ToolCategory.LLM,
            "descripcion": "LLM cloud usando Claude API",
            "funcion": lambda: None,
            "input_schema": {"prompt": {"type": "string", "required": True}},
            "output_schema": {"response": {"type": "string"}},
            "dependencias": ["anthropic"],
            "uso_concurrente_max": 2,
            "prioridad": 8,
            "activo": True,
            "version": "1.0.0",
            "autor": "URA",
            "fecha_creacion": "2026-04-27",
            "fecha_actualizacion": "2026-04-27",
            "changelog": ["Inicial"],
            "tags": ["cloud", "api"],
            "vocabulario": {
                "palabras_clave": ["consulta", "pregunta", "respuesta"],
                "terminos_tecnicos": ["api", "cloud", "anthropic"],
                "sinonimos": ["claude", "llm"],
            },
            "test_function": None,
            "test_data": None,
            "ejemplos_uso": [],
            "notas": ["Requiere API key de Anthropic"],
            "referencias": ["https://docs.anthropic.com"],
            "config_schema": {},
            "config_default": {},
            "metrics_enabled": True,
            "metrics_to_track": ["latency", "success_rate", "api_calls"],
            "cache_enabled": True,
            "cache_ttl": 600,
            "required_permissions": ["api_access"],
            "allowed_roles": ["admin"],
        }
        self.register(spec)

    def _register_duckduckgo(self):
        """Registrar herramienta DuckDuckGo Search"""
        spec: ToolSpec = {
            "nombre": "duckduckgo",
            "categoria": ToolCategory.SEARCH,
            "descripcion": "Búsqueda web usando DuckDuckGo",
            "funcion": lambda: None,
            "input_schema": {"query": {"type": "string", "required": True}},
            "output_schema": {"results": {"type": "array"}},
            "dependencias": ["duckduckgo-search"],
            "uso_concurrente_max": 2,
            "prioridad": 6,
            "activo": True,
            "version": "1.0.0",
            "autor": "URA",
            "fecha_creacion": "2026-04-27",
            "fecha_actualizacion": "2026-04-27",
            "changelog": ["Inicial"],
            "tags": ["search", "web"],
            "vocabulario": {
                "palabras_clave": ["buscar", "search", "encontrar"],
                "terminos_tecnicos": ["query", "results", "ddg"],
                "sinonimos": ["duckduckgo", "buscador"],
            },
            "test_function": None,
            "test_data": None,
            "ejemplos_uso": [],
            "notas": ["Búsqueda web gratuita"],
            "referencias": ["https://duckduckgo.com"],
            "config_schema": {},
            "config_default": {},
            "metrics_enabled": True,
            "metrics_to_track": ["latency", "search_count"],
            "cache_enabled": True,
            "cache_ttl": 300,
            "required_permissions": [],
            "allowed_roles": ["user", "admin"],
        }
        self.register(spec)

    def _register_google_search(self):
        """Registrar herramienta Google Custom Search"""
        spec: ToolSpec = {
            "nombre": "google_search",
            "categoria": ToolCategory.SEARCH,
            "descripcion": "Búsqueda web usando Google Custom Search API",
            "funcion": lambda: None,
            "input_schema": {"query": {"type": "string", "required": True}},
            "output_schema": {"results": {"type": "array"}},
            "dependencias": ["google-api-python-client"],
            "uso_concurrente_max": 2,
            "prioridad": 7,
            "activo": True,
            "version": "1.0.0",
            "autor": "URA",
            "fecha_creacion": "2026-04-27",
            "fecha_actualizacion": "2026-04-27",
            "changelog": ["Inicial"],
            "tags": ["search", "web", "api"],
            "vocabulario": {
                "palabras_clave": ["buscar", "search", "encontrar"],
                "terminos_tecnicos": ["api", "cx", "google"],
                "sinonimos": ["google", "buscador"],
            },
            "test_function": None,
            "test_data": None,
            "ejemplos_uso": [],
            "notas": ["Requiere API key y CX de Google"],
            "referencias": ["https://developers.google.com/custom-search"],
            "config_schema": {},
            "config_default": {},
            "metrics_enabled": True,
            "metrics_to_track": ["latency", "search_count", "api_calls"],
            "cache_enabled": True,
            "cache_ttl": 300,
            "required_permissions": ["api_access"],
            "allowed_roles": ["admin"],
        }
        self.register(spec)

    def _register_telegram(self):
        """Registrar herramienta Telegram"""
        spec: ToolSpec = {
            "nombre": "telegram",
            "categoria": ToolCategory.MESSAGING,
            "descripcion": "Bot de Telegram para mensajería",
            "funcion": lambda: None,
            "input_schema": {"message": {"type": "string", "required": True}},
            "output_schema": {"sent": {"type": "boolean"}},
            "dependencias": ["python-telegram-bot"],
            "uso_concurrente_max": 10,
            "prioridad": 9,
            "activo": True,
            "version": "1.0.0",
            "autor": "URA",
            "fecha_creacion": "2026-04-27",
            "fecha_actualizacion": "2026-04-27",
            "changelog": ["Inicial"],
            "tags": ["messaging", "bot"],
            "vocabulario": {
                "palabras_clave": ["mensaje", "enviar", "chat"],
                "terminos_tecnicos": ["bot", "token", "chat_id"],
                "sinonimos": ["telegram", "mensajero"],
            },
            "test_function": None,
            "test_data": None,
            "ejemplos_uso": [],
            "notas": ["Requiere bot token de Telegram"],
            "referencias": ["https://core.telegram.org/bots"],
            "config_schema": {},
            "config_default": {},
            "metrics_enabled": True,
            "metrics_to_track": ["messages_sent", "latency"],
            "cache_enabled": False,
            "cache_ttl": 0,
            "required_permissions": [],
            "allowed_roles": ["user", "admin"],
        }
        self.register(spec)

    def _register_slack(self):
        """Registrar herramienta Slack"""
        spec: ToolSpec = {
            "nombre": "slack",
            "categoria": ToolCategory.MESSAGING,
            "descripcion": "Bot de Slack para mensajería",
            "funcion": lambda: None,
            "input_schema": {"message": {"type": "string", "required": True}},
            "output_schema": {"sent": {"type": "boolean"}},
            "dependencias": ["slack-sdk"],
            "uso_concurrente_max": 10,
            "prioridad": 7,
            "activo": True,
            "version": "1.0.0",
            "autor": "URA",
            "fecha_creacion": "2026-04-27",
            "fecha_actualizacion": "2026-04-27",
            "changelog": ["Inicial"],
            "tags": ["messaging", "bot"],
            "vocabulario": {
                "palabras_clave": ["mensaje", "enviar", "channel"],
                "terminos_tecnicos": ["bot", "token", "workspace"],
                "sinonimos": ["slack", "mensajero"],
            },
            "test_function": None,
            "test_data": None,
            "ejemplos_uso": [],
            "notas": ["Requiere bot token de Slack"],
            "referencias": ["https://api.slack.com"],
            "config_schema": {},
            "config_default": {},
            "metrics_enabled": True,
            "metrics_to_track": ["messages_sent", "latency"],
            "cache_enabled": False,
            "cache_ttl": 0,
            "required_permissions": [],
            "allowed_roles": ["user", "admin"],
        }
        self.register(spec)

    def _register_postgresql(self):
        """Registrar herramienta PostgreSQL"""
        spec: ToolSpec = {
            "nombre": "postgresql",
            "categoria": ToolCategory.STORAGE,
            "descripcion": "Base de datos PostgreSQL",
            "funcion": lambda: None,
            "input_schema": {"query": {"type": "string", "required": True}},
            "output_schema": {"results": {"type": "array"}},
            "dependencias": ["psycopg2"],
            "uso_concurrente_max": 20,
            "prioridad": 10,
            "activo": True,
            "version": "1.0.0",
            "autor": "URA",
            "fecha_creacion": "2026-04-27",
            "fecha_actualizacion": "2026-04-27",
            "changelog": ["Inicial"],
            "tags": ["storage", "database"],
            "vocabulario": {
                "palabras_clave": ["guardar", "consultar", "base de datos"],
                "terminos_tecnicos": ["sql", "query", "psql"],
                "sinonimos": ["postgres", "bd", "database"],
            },
            "test_function": None,
            "test_data": None,
            "ejemplos_uso": [],
            "notas": ["Requiere PostgreSQL instalado"],
            "referencias": ["https://www.postgresql.org/docs"],
            "config_schema": {},
            "config_default": {},
            "metrics_enabled": True,
            "metrics_to_track": ["query_count", "latency", "connection_count"],
            "cache_enabled": False,
            "cache_ttl": 0,
            "required_permissions": ["db_access"],
            "allowed_roles": ["admin"],
        }
        self.register(spec)

    def _register_redis(self):
        """Registrar herramienta Redis"""
        spec: ToolSpec = {
            "nombre": "redis",
            "categoria": ToolCategory.STORAGE,
            "descripcion": "Caché y message queue usando Redis",
            "funcion": lambda: None,
            "input_schema": {"operation": {"type": "string", "required": True}},
            "output_schema": {"result": {"type": "any"}},
            "dependencias": ["redis"],
            "uso_concurrente_max": 100,
            "prioridad": 10,
            "activo": True,
            "version": "1.0.0",
            "autor": "URA",
            "fecha_creacion": "2026-04-27",
            "fecha_actualizacion": "2026-04-27",
            "changelog": ["Inicial"],
            "tags": ["storage", "cache", "queue"],
            "vocabulario": {
                "palabras_clave": ["cachear", "guardar", "recuperar"],
                "terminos_tecnicos": ["key", "value", "ttl"],
                "sinonimos": ["redis", "caché"],
            },
            "test_function": None,
            "test_data": None,
            "ejemplos_uso": [],
            "notas": ["Requiere Redis instalado"],
            "referencias": ["https://redis.io/docs"],
            "config_schema": {},
            "config_default": {},
            "metrics_enabled": True,
            "metrics_to_track": ["operation_count", "latency", "memory_usage"],
            "cache_enabled": False,
            "cache_ttl": 0,
            "required_permissions": [],
            "allowed_roles": ["user", "admin"],
        }
        self.register(spec)

    def get_stats(self) -> dict:
        """Obtener estadísticas del registro"""
        total = len(self.tools)
        activas = len(self.get_available_tools())
        por_categoria = {}

        for cat in ToolCategory:
            por_categoria[cat.value] = len(self.list_by_category(cat))

        return {
            "total": total,
            "activas": activas,
            "inactivas": total - activas,
            "por_categoria": por_categoria,
        }


# Instancia global
TOOL_REGISTRY = ToolRegistry()

# Test
if __name__ == "__main__":
    print("=" * 50)
    print("URA Tool Registry - Test")
    print("=" * 50)

    stats = TOOL_REGISTRY.get_stats()
    print("📊 Estadísticas:")
    print(f"   Total: {stats['total']}")
    print(f"   Activas: {stats['activas']}")
    print(f"   Inactivas: {stats['inactivas']}")
    print(f"   Por categoría: {stats['por_categoria']}")

    print("\n🔍 Herramientas activas:")
    for tool_id in TOOL_REGISTRY.get_available_tools():
        spec = TOOL_REGISTRY.get(tool_id)
        print(f"   - {tool_id}: {spec['descripcion']}")

    print("\n🔧 Herramientas LLM:")
    for spec in TOOL_REGISTRY.list_by_category(ToolCategory.LLM):
        print(f"   - {spec['nombre']}: {spec['descripcion']}")

    print("\n✅ Tool Registry OK")
