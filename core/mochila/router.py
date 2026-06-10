from dataclasses import dataclass
from typing import Protocol


@dataclass
class RouteResult:
    provider: str
    modelo: str
    route_reason: str


RUTAS_POR_DEFECTO: dict[str, list[dict]] = {
    "codigo": [
        {"provider": "ollama", "modelo": "deepseek-coder:6.7b"},
        {"provider": "ollama", "modelo": "qwen2.5-coder:32b"},
        {"provider": "openrouter", "modelo": "anthropic/claude-sonnet-4"},
        {"provider": "openrouter", "modelo": "deepseek/deepseek-v4-flash"},
    ],
    "razonamiento": [
        {"provider": "ollama", "modelo": "deepseek-r1:14b"},
        {"provider": "ollama", "modelo": "qwen3:32b-q8_0"},
        {"provider": "openrouter", "modelo": "google/gemini-2.5-flash"},
        {"provider": "openrouter", "modelo": "anthropic/claude-sonnet-4"},
    ],
    "rapido": [
        {"provider": "ollama", "modelo": "qwen2.5:7b"},
        {"provider": "ollama", "modelo": "deepseek-coder:6.7b"},
        {"provider": "openrouter", "modelo": "deepseek/deepseek-v4-flash"},
    ],
}

PATRONES_CLASIFICACION: dict[str, list[str]] = {
    "codigo": [
        "refactor", "funcion", "clase", "import", "def ", "bug", "fix",
        "test", "type", "codigo", "implementa", "bash", "script",
        "terminal", "git", "commit", "push", "pip",
    ],
    "razonamiento": [
        "analiza", "compara", "evalua", "planea", "arquitectura",
        "estrategia", "diseno", "sistema", "impacto", "pros y contras",
        "recomienda", "que es mejor",
    ],
}


class Clasificador(Protocol):
    def clasificar(self, mensajes: list, task_hint: str | None = None) -> str: ...


class ClasificadorKeyword:
    def __init__(self, patrones: dict[str, list[str]] | None = None):
        self.patrones = patrones or PATRONES_CLASIFICACION

    def clasificar(self, mensajes: list, task_hint: str | None = None) -> str:
        if task_hint and task_hint in ("codigo", "razonamiento", "rapido"):
            return task_hint

        texto = " ".join(m.get("content", "") for m in mensajes).lower()

        puntuaciones: dict[str, int] = {}
        for tipo, palabras in self.patrones.items():
            puntuaciones[tipo] = sum(1 for p in palabras if p in texto)

        if puntuaciones.get("codigo", 0) > puntuaciones.get("razonamiento", 0):
            return "codigo"
        elif puntuaciones.get("razonamiento", 0) > puntuaciones.get("codigo", 0):
            return "razonamiento"
        return "rapido"


class NoProviderAvailable(Exception):
    ...


class Router:
    def __init__(
        self,
        providers: dict,
        rutas: dict[str, list[dict]] | None = None,
        clasificador: Clasificador | None = None,
    ):
        self.providers = providers
        self.rutas = rutas or RUTAS_POR_DEFECTO
        self.clasificador = clasificador or ClasificadorKeyword()

    def elegir_provider(self, tipo: str, modelo_especifico: str | None) -> RouteResult:
        if modelo_especifico and modelo_especifico != "auto":
            if "/" in modelo_especifico:
                p, m = modelo_especifico.split("/", 1)
                if p in self.providers:
                    return RouteResult(provider=p, modelo=m, route_reason=f"explicit:{modelo_especifico}")
            return RouteResult(provider="ollama", modelo=modelo_especifico, route_reason=f"explicit:{modelo_especifico}")

        for entrada in self.rutas.get(tipo, self.rutas["rapido"]):
            p = entrada["provider"]
            if p in self.providers:
                return RouteResult(provider=p, modelo=entrada["modelo"], route_reason=f"keyword:{tipo}")

        raise NoProviderAvailable(f"Ningún provider disponible para tipo={tipo}")

    def route(
        self,
        mensajes: list,
        modelo_hint: str | None = None,
        task_hint: str | None = None,
    ) -> RouteResult:
        tipo = self.clasificador.clasificar(mensajes, task_hint)
        return self.elegir_provider(tipo, modelo_hint if modelo_hint and modelo_hint != "auto" else None)
