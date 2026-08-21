## Descripción

El mapa de cobertura selecciona tests que **no cubren** la línea mutada, y con un único test async seleccionado, **todos los mutantes sobreviven** (0 zapped) aunque el test debería matarlos.

## Contexto

- pytest-gremlins 1.9.0, Python 3.12, Linux.
- Modo: `--gremlins --gremlin-executor=subprocess --gremlin-report=json`.
- Código objetivo (una sola línea problemática):

```python
async def ejecutar_tool(name: str, arguments: dict) -> dict:
    handler = TOOL_HANDLERS.get(name)
    if not handler:
        return {"error": f"Tool desconocida: {name}"}
    return await handler(**arguments)   # <-- mutante 'return value to None' en esta línea
```

Test que mata el mutante (verificado manualmente: con `return None` el assert falla):

```python
async def test_ejecutar_tool_devuelve_resultado_del_handler() -> None:
    async def _fake_handler(**kwargs):
        return {"ok": True, "kwargs": kwargs}
    TOOL_HANDLERS["_fake_test"] = _fake_handler
    try:
        res = await ejecutar_tool("_fake_test", {"a": 1})
        assert res == {"ok": True, "kwargs": {"a": 1}}
    finally:
        del TOOL_HANDLERS["_fake_test"]
```

## Reproducción

1. `pytest --gremlins --gremlin-executor=subprocess --gremlin-targets=core/mochila/tools.py --gremlin-report=json tests/unit/test_mochila_tools_cobertura.py` (suite completa del archivo) → 33 zapped, **1 survived**: el mutante de `return await handler(...)` (línea 175). En el reporte JSON, `selected_tests` para ese mutante es `["tests/unit/test_mochila_tools_cobertura.py::test_ejecutar_tool_desconocida"]` — un test que **no ejecuta esa línea** (hace `return` antes, porque `handler` es `None`).

2. `pytest --gremlins --gremlin-executor=subprocess --gremlin-targets=core/mochila/tools.py "tests/unit/test_mochila_tools_cobertura.py::test_ejecutar_tool_devuelve_resultado_del_handler"` (solo el test que SÍ cubre la línea) → **0 zapped, 34 survived**: con el mutante aplicado manualmente el test falla, pero bajo gremlins todos los mutantes "sobreviven".

## Causa probable

El mismo problema del #486: el **lightweight runner** llama directamente a la función del test; los tests `async def` no se ejecutan (o se ejecutan sin el archivo mutado), y el mapa de cobertura asigna líneas a tests que no las ejecutan (posible desalineación línea transformada vs. original para `return await`). Resultado: veredictos fabricados.

## Esperado

- El mutante de la línea con `return await handler(...)` debe ser ZAPPED por `test_ejecutar_tool_devuelve_resultado_del_handler`.
- Un test que no ejecuta una línea no debe aparecer en `selected_tests` de esa línea.

## Trabajo relacionado

- #486 (lightweight runner: async tests never execute)
