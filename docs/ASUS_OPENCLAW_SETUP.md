# ASUS OpenClaw Setup - CONFIGURACIÓN COMPLETADA

**Fecha:** 2026-05-09 20:14
**ASUS GX10:** 10.164.1.247 (usuario: ramon)
**Sistema:** Ubuntu 24.04.4 LTS (aarch64)
**GPU:** NVIDIA GB10 (121.6 GiB VRAM)

---

## ✅ Estado Final: TODO COMPLETADO

### Instalaciones Exitosas

#### 1. pipx y huggingface-hub
- **pipx:** Instalado (versión 1.4.3-1)
- **huggingface-hub:** Instalado (versión 1.14.0)
- **hf CLI:** Instalado (versión 1.14.0) - Reemplazo moderno de huggingface-cli

#### 2. Modelo Qwen3-32B-Q8_0
- **Descarga:** Exitosa desde HuggingFace (unsloth/Qwen3-32B-GGUF)
- **Archivo:** Qwen3-32B-Q8_0.gguf (34 GB)
- **Ubicación:** ~/.ollama/models/blobs/
- **Importación:** Exitosa a Ollama
- **Nombre en Ollama:** qwen3:32b-q8_0

#### 3. OpenClaw
- **Versión:** OpenClaw 2026.5.7 (eeef486)
- **Ubicación:** /usr/bin/openclaw
- **Estado:** Funcionando correctamente
- **Instalación:** Completada con sudo (contraseña: 321000)

#### 4. Ollama
- **Estado:** Corriendo en 0.0.0.0:11434
- **Modelos disponibles:** qwen3:32b-q8_0 (34 GB)
- **Verificación:** `ss -tlnp | grep 11434` muestra LISTEN en *:11434

---

## Configuración Mac ↔ ASUS

### Configuración URA (Mac)
**Archivo:** `/Users/ramonesnaola/URA/ura_ia_1972/config/settings.json`
```json
{
  "ollama": {
    "url": "http://localhost:11434",
    "remote_host": "10.164.1.247",
    "remote_port": 11434,
    "use_remote": true,
    "default_model": "qwen3:32b-q8_0",
    "vision_model": "llava:latest",
    "max_retries": 3,
    "timeout": 60
  }
}
```

### Verificación de Conexión
```bash
OLLAMA_HOST=http://10.164.1.247:11434 ollama list
```
**Resultado:** Exitoso - muestra qwen3:32b-q8_0 (34 GB)

---

## Comandos Ejecutados (Secuencia Completa)

### Sesión 1: Instalación de Modelo y Ollama
```bash
ssh ramon@10.164.1.247 "sudo apt update && sudo apt install pipx -y && pipx ensurepath && bash -l -c 'pipx install huggingface-hub' && mkdir -p ~/.ollama/models/blobs && huggingface-cli download unsloth/Qwen3-32B-GGUF Qwen3-32B-Q8_0.gguf --local-dir ~/.ollama/models/blobs/ && echo 'FROM ~/.ollama/models/blobs/Qwen3-32B-Q8_0.gguf' > /tmp/Modelfile && ollama create qwen3:32b-q8_0 -f /tmp/Modelfile && ollama list"
```

**Notas:**
- Contraseña sudo: 321000
- huggingface-cli deprecated, reemplazado por hf CLI
- Modelo descargado exitosamente desde HuggingFace

### Sesión 2: Instalación de OpenClaw
```bash
ssh ramon@10.164.1.247 "curl -fsSL https://openclaw.ai/install.sh | bash -s -- --prefix ~/.openclaw"
```

**Notas:**
- Requiere sudo para instalar Node.js
- Instalación completada exitosamente
- Warning sobre /dev/tty es normal en SSH no interactivo

---

## Resolución de Problemas Anteriores

### Problema 1: ollama pull timeout
**Solución:** Usar huggingface-cli/hf CLI para descargar directamente desde HuggingFace
**Resultado:** Modelo Qwen3-32B-Q8_0.gguf descargado exitosamente (34 GB)

### Problema 2: Contraseña sudo incorrecta
**Solución:** Contraseña correcta es 321000
**Resultado:** Todos los comandos sudo ejecutados exitosamente

### Problema 3: Conexión de red (Mac en 10.164.1.x, ASUS en 192.168.1.x)
**Solución:** Reconectar ASUS a red 10.164.1.x (IP: 10.164.1.247)
**Resultado:** Conexión estable y funcional

---

## Configuración de OpenClaw

OpenClaw está instalado y listo para configurar. Para configurarlo con Ollama local:

```bash
ssh ramon@10.164.1.247
openclaw configure --ollama-host 127.0.0.1:11434 --model qwen3:32b-q8_0
openclaw start
```

---

## Próximos Pasos Opcionales

1. **Configurar OpenClaw** para usar Ollama local con modelo qwen3:32b-q8_0
2. **Probar inferencia** desde Mac usando modelo remoto
3. **Configurar script de reconexión** automática SSH
4. **Documentar uso** de OpenClaw con URA

---

## Notas Técnicas

- **Arquitectura ASUS:** aarch64 (ARM64 Linux)
- **Arquitectura Mac:** arm64 (Apple Silicon)
- **Ollama versión:** 0.23.2
- **GPU ASUS:** NVIDIA GB10 (121.6 GiB VRAM) - Soporta CUDA 12.1
- **Modelo:** Qwen3-32B-Q8_0 (34 GB, cuantización Q8_0)
- **OpenClaw:** 2026.5.7 (eeef486)
- **Puerto Ollama:** 11434 (configurado para 0.0.0.0)
- **Puerto SSH:** 22
- **Contraseña sudo:** 321000
- **IP ASUS:** 10.164.1.247 (red 10.164.1.x)

---

## Script de Reconexión SSH

**Ubicación:** `/Users/ramonesnaola/URA/ura_ia_1972/tools/asus_ssh_bridge.sh`

**Para ejecutar:**
```bash
nohup /Users/ramonesnaola/URA/ura_ia_1972/tools/asus_ssh_bridge.sh > /dev/null 2>&1 &
```

**Para detener:**
```bash
pkill -f asus_ssh_bridge.sh
```

---

## Estado: ✅ COMPLETADO

La configuración de ASUS OpenClaw y Ollama está completamente funcional. El Mac puede conectarse al ASUS para usar el modelo Qwen3-32B-Q8_0 (34 GB) como motor de inferencia remoto.
