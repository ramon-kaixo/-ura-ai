# Mejoras de Integración OpenCode-OpenClaw

## Problema Principal: Scope Upgrade Pending Approval

OpenClaw Gateway está bloqueado por una aprobación de scope pendiente:
- **Request ID**: 7e625bae-69b2-44db-a84a-1f8b5d0baf2f
- **Causa**: Intento de upgrade de permisos de operator.pairing a operator.read
- **Estado**: Gateway funcionando pero rechazando conexiones

### Solución Inmediata

1. **Acceder al Dashboard de OpenClaw**:
   ```bash
   # Desde tu Mac:
   ssh -N -L 18789:127.0.0.1:18789 ramon@10.164.1.99
   # Luego abrir en navegador: http://localhost:18789/
   ```

2. **Aprobar el scope upgrade** en el dashboard (sección Security/Approvals)

3. **Verificar conexión**:
   ```bash
   openclaw gateway status
   ```

## Configuración Mejorada para OpenCode

### Problema Actual
- Modelo único: qwen3:32b-q8_0 para todo
- Sin routing inteligente por tipo de tarea
- MCP no funcional debido al scope upgrade

### Solución Propuesta

Usar el Model Router existente en GX10 (puerto 11435) para routing inteligente:

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "model": "auto",
  "agent": {
    "default": "ura_router"
  },
  "mcp": {
    "openclaw": {
      "type": "local",
      "command": ["openclaw", "mcp", "serve"],
      "enabled": true,
      "timeout": 30000,
      "retry": 3
    }
  }
}
```

### Routing de Modelos

El Model Router de GX10 ya está configurado para:
- **Razonamiento complejo**: qwen3:32b-q8_0
- **Código**: qwen2.5-coder:32b
- **Respuestas rápidas**: qwen2.5:7b
- **Tareas complejas**: llama3.3:70b

## Habilitar Skills Clave en OpenClaw

### Skills Recomendados

```bash
# GitHub integration
openclaw skills enable github

# Coding agent
openclaw skills enable coding-agent

# Summarization
openclaw skills enable summarize

# Model usage tracking
openclaw skills enable model-usage
```

### Lista de Skills Disponibles

- **coding-agent**: Agentes de código especializados
- **github**: Integración con GitHub (issues, PRs)
- **summarize**: Resumen automático de conversaciones
- **model-usage**: Seguimiento de uso de modelos
- **session-logs**: Logs de sesiones para debugging

## Configurar Canales en OpenClaw

### Canales Recomendados

```bash
# Agregar canal si es necesario
openclaw channels add
```

## Pasos de Implementación

### 1. Resolver Scope Upgrade (CRÍTICO)
```bash
# Desde Mac:
ssh -N -L 18789:127.0.0.1:18789 ramon@10.164.1.99 &
# Abrir http://localhost:18789/ en navegador
# Aprobar el scope upgrade en Security/Approvals
```

### 2. Actualizar Configuración OpenCode
```bash
# Copiar configuración mejorada
scp opencode_config_improved.jsonc ramon@10.164.1.99:/home/ramon/.config/opencode/opencode.jsonc
```

### 3. Habilitar Skills
```bash
ssh ramon@10.164.1.99
openclaw skills enable github
openclaw skills enable coding-agent
openclaw skills enable summarize
openclaw skills enable model-usage
```

### 4. Verificar Conexión MCP
```bash
# En GX10
opencode mcp list
# Debería mostrar openclaw con 9 herramientas disponibles
```

### 5. Probar Integración
```bash
# Probar MCP
opencode mcp debug openclaw
```

## Optimizaciones Adicionales

### 1. Configurar Model Router como Endpoint Primario

OpenCode puede usar directamente el Model Router en lugar de Ollama:

```jsonc
{
  "model": "http://localhost:11435/api/chat",
  "provider": "openai-compatible"
}
```

### 2. Habilitar Caching de Contexto

```jsonc
{
  "features": {
    "context_cache": true,
    "cache_ttl": 3600
  }
}
```

### 3. Configurar Timeout para MCP

```jsonc
{
  "mcp": {
    "openclaw": {
      "timeout": 60000,
      "retry": 5
    }
  }
}
```

## Monitoreo y Debugging

### Verificar Estado
```bash
# OpenCode
opencode mcp list
opencode mcp debug openclaw

# OpenClaw
openclaw gateway status
openclaw status
openclaw models status
```

### Logs
```bash
# OpenCode logs
tail -f ~/.local/share/opencode/log/*.log

# OpenClaw logs
tail -f /tmp/openclaw/openclaw-*.log
```

## Resumen de Mejoras

1. **Resolver scope upgrade** - Acceso manual al dashboard
2. **Routing inteligente** - Usar Model Router existente
3. **Habilitar skills** - GitHub, coding-agent, summarize
4. **Configurar canales** - Si es necesario
5. **Optimizar timeouts** - Mejorar estabilidad MCP
6. **Monitoreo activo** - Logs y status checks

## Próximos Pasos

1. Acceder al dashboard y aprobar scope upgrade
2. Aplicar configuración mejorada de OpenCode
3. Habilitar skills clave
4. Verificar conexión MCP
5. Probar integración completa
