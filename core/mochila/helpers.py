def _procesar_usage(respuesta: dict | None, provider_name: str, modelo: str, cost_tracker) -> None:
    if respuesta and isinstance(respuesta, dict):
        uso = respuesta.get("usage") or {}
        cost_tracker.registrar(
            provider_name,
            modelo,
            uso.get("prompt_tokens", 0) or 0,
            uso.get("completion_tokens", 0) or 0,
        )
