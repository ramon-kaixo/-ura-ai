# HALLAZGO: opencode CLI no ejecuta tools con Ollama (ai-sdk bug)

Fecha: 2026-08-25 · Autor: TERM

## Problema
opencode CLI (v0.0.55) con provider @ai-sdk/openai-compatible (Ollama /v1)
NO ejecuta tool calls: el modelo emite la tool call como JSON, pero opencode
la imprime como texto y no la ejecuta.

## Causa
Bug upstream conocido: el adapter @ai-sdk/openai-compatible no parsea
correctamente las tool calls de Ollama. Issues abiertos:
- #32756: [FEATURE] local ollama support (abierta, PR #33103 pendiente)
- #21396: native Ollama integration
- #12243: model discovery fails for Ollama

## Modelos afectados (verificado 2026-08-17)
- qwen3:32b-q8_0: emite tool call pero no ejecuta
- deepseek-r1:14b: alucina salida
- qwen2.5-coder:32b: bucle infinito repitiendo tool call como texto

## Workarounds posibles
1. **opencode-local-ollama** (npm, v0.1.0): plugin nativo de Ollama con model discovery
   - URL: https://www.npmjs.com/package/opencode-local-ollama
   - Instalar: npm install -g opencode-local-ollama
   - Configurar en opencode.json con npm: opencode-local-ollama
   - Riesgo: v0.1.0, poco mantenimiento (171 downloads/week)

2. **Esperar PR #33103**: soporte nativo Ollama en opencode upstream
   - Estado: open, sin merge estimado

3. **Usar OpenCode Web** (deepseek-v4-flash-free) para tareas con herramientas
   - Ya funciona actualmente como workaround

## Config actual (GX10)
- Provider: @ai-sdk/openai-compatible
- baseURL: http://localhost:11434/v1
- Modelos declarados con tools: true pero no ejecutan

## Recomendacion
No instalar opencode-local-ollama sin aprobacion de Ramon (riesgo v0.1.0).
Mejor esperar PR #33103 o usar OpenCode Web como fallback.
## Plugin instalado (2026-08-25)

opencode-local-ollama v0.1.0 instalado globalmente en GX10.

### Para activar, anadir a ~/.config/opencode/opencode.json:

    "plugin": {
      "opencode-local-ollama": {
        "host": "http://localhost:11434",
        "providerID": "ollama",
        "timeout": 5000,
        "context": 8192,
        "output": 4096
      }
    }

### Nota:
El provider ollama actual usa @ai-sdk/openai-compatible. El plugin podria
conflictuar. Probar en sesion de pruebas antes de aplicar a produccion.
Si hay conflicto, eliminar el bloque "plugin" del config.
