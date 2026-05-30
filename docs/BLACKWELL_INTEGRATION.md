# Integración Blackwell-Core Híbrida Distribuida (Mac M4 ↔ ASUS GX10)

Este documento describe cómo configurar URA en el Mac Mini M4 para usar el ASUS GX10 (128 GB, Blackwell) como músculo de inferencia remoto.

## Arquitectura

**MAC MINI M4 (16 GB) — Mando táctico + Interfaz:**
- URA (voz/texto)
- Panel web (ura_panel.py)
- Conectores de mensajería (Telegram, Gmail, WhatsApp)
- Guardrails (agente_policia_v2, jailbreak_guard)
- Browser agent (Playwright)
- Memoria conversacional a corto plazo
- n8n (workflows, triggers)

**ASUS GX10 (128 GB, Blackwell) — Músculo de inferencia:**
- Ollama con modelos grandes (DeepSeek R1 70B, Llama 3.1 70B, Qwen 72B)
- OpenClaw (langosta) corriendo aquí
- 83 agentes especializados con mochilas
- ReAct engine + razonamiento complejo
- Sandbox de VirtualBox (32 GB RAM)
- Embeddings reales (sentence-transformers)

## Configuración

### Método 1: Variable de Entorno (Recomendado)

```bash
# En el Mac M4
export OLLAMA_HOST=100.x.x.x:11434
```

Donde `100.x.x.x` es la IP Tailscale del ASUS GX10.

### Método 2: Archivo de Configuración

Editar `config/settings.json`:

```json
{
  "ollama_use_remote": true,
  "ollama_remote_host": "100.x.x.x",
  "ollama_remote_port": 11434,
  "ollama_host": "localhost",
  "ollama_port": 11434
}
```

### Método 3: Configuración Centralizada (core/config_manager.py)

El `ConfigManager` ahora soporta configuración remota en `OllamaConfig`:

```python
from core.config_manager import ConfigManager

cm = ConfigManager()
cm.config.ollama.use_remote = True
cm.config.ollama.remote_host = "100.x.x.x"
cm.config.ollama.remote_port = 11434

url = cm.config.ollama.get_ollama_url()  # Retorna http://100.x.x.x:11434
```

## Verificación de Conectividad

Usar el script de verificación:

```bash
# Configurar IP del ASUS
export ASUS_TAILSCALE_IP=100.x.x.x

# Ejecutar verificación
./tools/check_asus_connectivity.sh
```

El script verifica:
1. Ping a IP Tailscale del ASUS
2. Puerto 11434 abierto
3. API de Ollama responde (/api/tags)
4. Latencia de generación

## Archivos Modificados

1. **core/model_config.py**
   - Añadido soporte para variable de entorno `OLLAMA_HOST`
   - Parseo de host:port si está incluido en la variable

2. **core/config_manager.py**
   - Añadidos campos `remote_host`, `remote_port`, `use_remote` a `OllamaConfig`
   - Método `get_ollama_url()` para obtener URL correcta (remoto o local)

3. **services/init_utils.py**
   - Modificado `_init_connectors()` para leer configuración remota
   - Usa `ollama_use_remote`, `ollama_remote_host`, `ollama_remote_port`

4. **tools/check_asus_connectivity.sh** (nuevo)
   - Script de verificación de conectividad Mac ↔ ASUS

## Comportamiento de Fallback

Si el Ollama remoto no está disponible:
- La configuración usa `localhost` por defecto
- Los conectores aceptan host y port como parámetros
- No hay fallback automático en tiempo de ejecución (para evitar confusión)

## Troubleshooting

**Problema: No se puede hacer ping al ASUS**
- Verifica que Tailscale está corriendo en ambas máquinas
- Verifica que ambas máquinas están en la misma red Tailscale
- Verifica que el firewall no está bloqueando el tráfico

**Problema: Puerto 11434 no accesible**
- Verifica que Ollama está corriendo: `ollama serve` en el ASUS
- Verifica que Ollama escucha en 0.0.0.0:11434 (no solo localhost)
- Verifica que el firewall del ASUS permite conexiones entrantes

**Problema: API de Ollama no responde**
- Verifica que Ollama está corriendo en el ASUS
- Verifica que no hay firewall bloqueando
- Prueba con curl: `curl http://100.x.x.x:11434/api/tags`

## Próximos Pasos

1. Configurar Tailscale en ambas máquinas
2. Instalar Ollama en el ASUS GX10
3. Descargar modelos grandes en el ASUS (DeepSeek R1 70B, Llama 3.1 70B, Qwen 72B)
4. Ejecutar script de verificación
5. Configurar variable de entorno OLLAMA_HOST
6. Iniciar URA en el Mac
7. Verificar que usa Ollama remoto
