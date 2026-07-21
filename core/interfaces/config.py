"""Interfaz de proveedor de configuración."""

from __future__ import annotations

from typing import Protocol


class IConfigProvider(Protocol):
    """Contrato que cualquier configuración URA debe cumplir.

    UraConfig (motor/core/config.py) cumple este protocolo estructuralmente
    sin necesidad de herencia explícita.
    """

    qdrant_host: str
    qdrant_port: int
    deploy_dir: str
    data_dir: str
    log_level: str
    ollama_host: str
    ollama_port: int
    ollama_model: str
    ollama_embedding_model: str
    ollama_timeout: int
    ollama_temperature: float
    ollama_max_tokens: int
    llm_provider: str
    is_vm: bool
    asus_host: str
    asus_port: int
    tailscale_iface: str
    timer_interval_min: int
    failure_knowledge_path: str
    baseline_path: str
    auto_verify: bool
    schema_version: int
