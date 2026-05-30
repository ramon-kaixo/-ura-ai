# URA - Universal Reasoning Assistant

URA (Universal Reasoning Assistant) es un sistema de IA de nivel empresarial con arquitectura de 3 capas de seguridad, auto-recuperación y múltiples interfaces (PyQt5, Telegram, Terminal).

## **Características Principales**

### **Arquitectura de 3 Capas Cognitivas**
- **CAPA 1 - AGENTE POLICÍA**: Valida comandos peligrosos con 3 checkpoints (patrones → LLM → consenso)
- **CAPA 2 - TECHNICAL DIRECTOR**: Genera fichas técnicas basadas en operaciones permitidas
- **CAPA 3 - WORKFLOW ENGINE**: Ejecuta operaciones y limpia "basura humana" de respuestas

### **Sistema de Seguridad Robusto**
- 3 checkpoints de validación antes de ejecutar comandos
- Sistema de consenso tripartito (consulta a 3 fuentes externas)
- Privacy Scrubber automático (sanitiza datos sensibles)
- Anti-bypass de IA comercial (no responde como ChatGPT)

### **Auto-Recuperación**
- URA no muere si Ollama falla - se reinicia sola
- Monitorización continua de conexión con Ollama (cada 5 segundos)
- Registro en maintenance.log
- Notificación por Telegram

### **Gestión Dinámica de RAM**
- Cambia dinámicamente entre modelos según RAM disponible
- qwen2.5:7b-instruct (más inteligente) si RAM ≥ 7GB
- qwen2.5:3b-instruct (más rápido) si RAM < 7GB
- Optimizado para Mac mini M4

## **Instalación**

### **Requisitos Previos**
- Python 3.8 o superior
- Ollama instalado y corriendo
- PyQt5 (para interfaz gráfica)

### **Instalación de Dependencias**
```bash
# Clonar o descargar el proyecto
cd URA_App

# Instalar dependencias
pip install -r requirements.txt

# Configurar variables de entorno
cp .env.example .env
# Editar .env con tus valores reales
```

### **Configuración de Ollama**
```bash
# Instalar Ollama si no está instalado
curl -fsSL https://ollama.ai/install.sh | sh

# Iniciar Ollama
ollama serve

# Descargar modelos recomendados
ollama pull qwen2.5:7b-instruct
ollama pull qwen2.5:3b-instruct
```

## **Estructura del Proyecto**

```
URA_App/
├── core/                    # Módulos principales
│   ├── workflow_engine.py   # Motor de flujo de 3 fases
│   ├── technical_director.py # Director técnico
│   ├── agente_policia_v2.py # Agente policía (seguridad)
│   ├── consensus_system.py  # Sistema de consenso
│   ├── privacy_scrubber.py  # Sanitización de privacidad
│   ├── ram_manager.py       # Gestión de RAM
│   ├── self_healing_system.py # Auto-recuperación
│   └── agents/             # Agentes especializados
├── connectors/              # Conectores externos
│   └── ollama_connector.py  # Conexión con Ollama
├── config/                  # Configuración
│   ├── config.json         # Configuración unificada
│   ├── settings.json       # Configuración antigua (deprecated)
│   └── model_config.json   # Configuración de modelos (deprecated)
├── benchmarks/             # Tests de integración
├── tests/                  # Tests unitarios
├── logs/                   # Logs del sistema
├── .env                    # Variables de entorno
├── requirements.txt        # Dependencias
├── main_final.py          # Arranque principal
├── start_ura.sh           # Script de lanzamiento
└── README.md              # Este archivo
```

## **Configuración**

### **Archivo de Variables de Entorno (.env)**
```bash
# Telegram Configuration
TELEGRAM_TOKEN=your_token_here
TELEGRAM_CHAT_ID=your_chat_id_here

# Ollama Configuration
OLLAMA_HOST=localhost
OLLAMA_PORT=11434
OLLAMA_MODEL=qwen2.5:7b-instruct

# Database Configuration
DB_PATH=./core/data/ura_state.json

# Logging Configuration
LOG_LEVEL=INFO
LOG_PATH=./logs/

# Security Configuration
SECURITY_MODE=APPLE

# UI Configuration
VOICE_ENABLED=true
INTERACTION_MODE=with_cursor
```

### **Archivo de Configuración Unificado (config/config.json)**
La configuración se guarda en `config/config.json`:

```json
{
  "version": "2.0",
  "ollama": {
    "host": "localhost",
    "port": 11434,
    "auto_start": true,
    "active_model": "qwen2.5:7b-instruct",
    "fallback_model": "qwen2.5:3b-instruct"
  },
  "ui": {
    "voice_enabled": true,
    "interaction_mode": "with_cursor",
    "cursor_speed": 0.5
  },
  "system": {
    "project_path": "~",
    "check_interval": 5,
    "log_level": "INFO",
    "log_path": "./logs/",
    "security_mode": "APPLE"
  }
}
```

## **Uso**

### **1. Iniciar la Aplicación**
```bash
# Usar el script de lanzamiento
bash start_ura.sh

# O ejecutar directamente
python main_final.py
```

### **2. Ejecutar Tests**
```bash
# Tests unitarios
python -m pytest tests/

# Tests de integración
python benchmarks/master_test_suite.py
```

## **Seguridad**

### **Modos de Seguridad**
- **APPLE**: Solo biometría Apple (Face ID/Touch ID) - modo actual
- **TELEGRAM**: Solo autorización por Telegram (deprecated)
- **DUAL**: Ambos sistemas (deprecated)

### **Comandos Bloqueados**
- `rm -rf /` (destrucción total)
- Fork bombs (`:(){:|:};:`)
- `dd if=/dev/zero of=/dev/sda`
- Modificaciones a `/etc/passwd` o `/etc/shadow`

## **Documentación Adicional**

- **URA_CHANGELOG.md**: Historial de cambios
- **URA_DEPRECATED.md**: Elementos retirados y deprecated
- **ABSOLUTE_PATHS_TODO.md**: Lista de archivos con rutas absolutas (para migración SSD)

## **Desarrollo**

### **Tests Unitarios**
Los tests unitarios se encuentran en `tests/`:
- `test_privacy_scrubber.py`: Tests de sanitización de privacidad
- `test_ram_manager.py`: Tests de gestión de RAM
- `test_workflow_engine.py`: Tests del motor de flujo

### **Tests de Integración**
Los tests de integración se encuentran en `benchmarks/`:
- `master_test_suite.py`: Suite completa de tests
- `test_technical_director.py`: Tests del director técnico
- `test_personality_cleanup.py`: Tests de limpieza de personalidad
- `test_hybrid_routing.py`: Tests de enrutamiento híbrido

## **Docker**

### **Construir Imagen**
```bash
docker build -t ura:latest .
```

### **Ejecutar Contenedor**
```bash
docker run -it --rm \
  -v $(pwd)/config:/app/config \
  -v $(pwd)/logs:/app/logs \
  --network host \
  ura:latest
```

## **Contribución**

### **Reportar Issues**
Si encuentras algún problema:
1. Revisa los logs en `logs/`
2. Describe el problema detalladamente
3. Incluye tu configuración si es relevante

### **Sugerencias de Mejora**
- Nuevas funcionalidades
- Mejoras en la interfaz
- Optimización de rendimiento
- Mejor integración con Ollama

## **Licencia**

Este proyecto es software libre y open source.

## **Soporte**

Para soporte técnico:
1. Revisa esta documentación
2. Consulta los logs de la aplicación
3. Verifica la configuración de Ollama

---

**URA** - Universal Reasoning Assistant v2.0

