"""Jerarquía de excepciones canónica para motor/.

Política (Fase F del plan de saneamiento):
- Toda excepción nueva en motor/ debe heredar de una de estas clases.
- No reemplazar las 773 excepciones existentes en core/ — solo documentar.
- ruff E722 (bare except) ya activo vía select = ["ALL"].
"""


class MotorError(Exception):
    """Error base para todo el motor."""


class ConfigError(MotorError):
    """Error de configuración (secrets, parámetros, etc.)."""


class ProviderError(MotorError):
    """Error de proveedor LLM (timeout, auth, rate limit, etc.)."""

    def __init__(self, message: str, provider: str = "", status_code: int | None = None):
        self.provider = provider
        self.status_code = status_code
        super().__init__(message)


class ProtocolError(MotorError):
    """Error de protocolo (mensaje malformado, versión incompatible, etc.)."""


class MemoryStoreError(MotorError):
    """Error de memoria (episódica, semántica, etc.)."""


class PipelineError(MotorError):
    """Error en pipeline de procesamiento."""
