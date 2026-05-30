# SYSTEM_READY.md - Manual de Instrucciones para Diseño de Pantalla

**URA v1.0 - Sistema Ready**
**Fecha:** 24 de abril de 2026
**Estado:** ✅ Sistema operativo y listo para integración GUI

---

## 1. HERRAMIENTAS INSTALADAS

### Python y Entorno Virtual
- **Python:** 3.12
- **Entorno Virtual:** `.venv` (aislado)
- **Ubicación:** `/Users/ramonesnaola/URA/ura_ia_1972/.venv`

### Dependencias Principales (requirements.txt)

**GUI e Interfaz:**
- `PyQt5` - Interfaz gráfica de usuario
- `pyautogui` - Automatización de GUI

**Red y API:**
- `Flask` - Web API
- `FastAPI` - API REST moderna
- `uvicorn` - Servidor ASGI
- `pydantic` - Validación de datos
- `requests` - Cliente HTTP

**Seguridad y Cifrado:**
- `cryptography` - Cifrado Fernet
- `keyring` - Gestión de claves en macOS Keychain
- `bandit` - Análisis de seguridad

**Base de Datos y Memoria:**
- `redis` - Base de datos en memoria
- `chromadb` - Base de datos vectorial

**Monitoreo y Métricas:**
- `psutil` - Monitoreo de sistema
- `prometheus-client` - Métricas
- `loguru` - Logging avanzado

**Testing y Calidad:**
- `pytest` - Testing framework
- `pytest-cov` - Cobertura de tests
- `hypothesis` - Testing property-based
- `mypy` - Type checking

**Voz y Audio:**
- `SpeechRecognition` - Reconocimiento de voz
- `PyAudio` - Audio processing
- `pyttsx3` - Text-to-speech
- `gTTS` - Google Text-to-Speech
- `playsound3` - Reproducción de audio

**Otras Utilidades:**
- `watchdog` - File system monitoring
- `jsonschema` - Validación JSON
- `schedule` - Tareas programadas

---

## 2. RUTAS DE ARCHIVOS CLAVE

### Directorio Principal
```
/Users/ramonesnaola/URA/ura_ia_1972/
```

### Archivos de Configuración
```
/Users/ramonesnaola/URA/ura_ia_1972/config/
├── config.json              # Configuración principal (CIFRADO)
├── model_config.json        # Configuración de modelos (CIFRADO)
├── security_policy.json     # Política de seguridad (umbral 0.01€)
└── .ura.key                 # Clave maestra (en macOS Keychain)
```

### Archivos Core (52 archivos esenciales)
```
/Users/ramonesnaola/URA/ura_ia_1972/core/
├── main_final.py            # Punto de entrada principal
├── memory_persistence.py    # Memoria persistente
├── semantic_memory.py      # Memoria semántica
├── react_engine.py         # Motor de razonamiento ReAct
├── autonomous_strategy.py  # Estrategia autónoma
├── traffic_controller.py   # Control de tráfico (Carretera 1/2)
├── rapid_classifier.py     # Clasificador rápido
├── security_policy.py      # Política de seguridad
├── security/               # Módulos de seguridad
│   ├── encryptor.py        # Cifrado con Fernet + keyring
│   ├── display_manager.py  # Ventanas emergentes macOS
│   └── hermetic_states.py  # Estados globales de bloqueo
└── ... (otros 43 archivos)
```

### Archivos de Seguridad
```
/Users/ramonesnaola/URA/ura_ia_1972/core/security/
├── encryptor.py            # Cifrado/Descifrado con Fernet
├── security_policy.py      # Autorización (Telegram/Apple)
├── display_manager.py      # Ventanas emergentes nativas
└── hermetic_states.py      # BLOCK_PAYMENTS, BLOCK_CREDENTIALS, BLOCK_INTERNET
```

### Logs
```
/Users/ramonesnaola/URA/ura_ia_1972/logs/
└── ura_app.log             # Logs del sistema
```

### Backup y Versiones
```
/Users/ramonesnaola/URA/ura_ia_1972/versions/
└── ura_v1.0_20260424_174150/  # Versión estable 1.0
```

---

## 3. PUERTOS DE CONEXIÓN (API)

### Ollama (Modelos de IA)
- **Host:** `localhost`
- **Puerto:** `11434`
- **Modelo Activo:** `qwen2.5:7b-instruct`
- **Modelo Fallback:** `qwen2.5:3b-instruct`

### Flask (Web API)
- **Puerto:** Por defecto 5000 (configurable)
- **Estado:** Disponible para integración

### FastAPI (API REST)
- **Puerto:** Por defecto 8000 (configurable)
- **Estado:** Disponible para integración

### Redis (Base de Datos en Memoria)
- **Puerto:** Por defecto 6379
- **Estado:** Instalado y funcionando

---

## 4. SISTEMA DE SEGURIDAD

### Cifrado
- **Algoritmo:** Fernet (AES-128 en CBC mode)
- **Clave Maestra:** Almacenada en macOS Keychain
- **Servicio:** `ura_encryption`
- **Usuario:** `master_key`
- **Verificación:** Biológica (Face ID / Touch ID)

### Política de Gastos
- **Umbral de Aprobación:** 0.01€
- **Modo:** `always_ask: true` (siempre pregunta)
- **Autorización:** Telegram + Apple Biometrics
- **Config:** `config/security_policy.json`

### Estados Herméticos
- **BLOCK_PAYMENTS:** Bloquea pagos
- **BLOCK_CREDENTIALS:** Bloquea credenciales
- **BLOCK_INTERNET:** Bloquea internet
- **HERMETIC:** Bloquea todo

### Ventanas Emergentes
- **OS:** macOS nativo (osascript)
- **Función:** `display_manager.py`
- **Timeout:** 30 segundos

---

## 5. ARQUITECTURA DE TRÁFICO

### Carretera 1 (Local)
- **Tipo:** Operaciones locales sin internet
- **Velocidad:** Ultra-rápida
- **Componente:** `rapid_classifier.py`
- **Uso:** Consultas de memoria, configuración local

### Carretera 2 (Externa)
- **Tipo:** Operaciones con internet
- **Timeout:** Configurable (default 30s)
- **Componente:** `traffic_controller.py`
- **Uso:** Búsqueda web, API externas

---

## 6. MODELOS DE IA (Ollama)

### Modelos Disponibles
- `qwen2.5:7b-instruct` - Principal
- `qwen2.5:3b-instruct` - Fallback
- `llava:latest` - Visión
- `deepseek-r1:7b` - Análisis profundo
- `policia:latest` - Seguridad

### Mapeo de Modelos
- `gestion:latest` → Departamento de gestión
- `seguridad:latest` → Departamento de seguridad
- `sistema:latest` → Departamento de sistema
- ... (ver config/model_mapping)

---

## 7. AGENTES URA (57 Agentes)

### Categorías
- **Gestión:** 8 agentes
- **Sistema:** 12 agentes
- **Documentos:** 6 agentes
- **Cocina:** 7 agentes
- **Seguridad:** 2 agentes
- **Comunicación:** 3 agentes
- **Lenguaje:** 4 agentes
- **Vocabulario:** 5 agentes
- **Técnica:** 2 agentes
- **Auditoría:** 2 agentes
- **Verificación:** 2 agentes
- **Instalación:** 1 agente

### Archivo de Referencia
- `AGENTS.md` - Inventario completo de agentes

---

## 8. MEMORIA DEL SISTEMA

### Memoria Semántica
- **Tecnología:** ChromaDB (Vector DB)
- **Checkpointing:** Automático
- **Carga:** Automática al arranque
- **Archivo:** `core/semantic_memory.py`

### Memoria Persistente
- **Backend:** Redis / File
- **Archivo:** `core/memory_persistence.py`
- **Estado:** Operativo

### Memoria de Contexto
- **Componente:** `core/dynamic_context.py`
- **Función:** Gestión de contexto dinámico

---

## 9. INSTRUCCIONES PARA DISEÑO DE PANTALLA

### 9.1. Punto de Entrada
- **Archivo:** `main_final.py`
- **Ubicación:** `/Users/ramonesnaola/URA/ura_ia_1972/main_final.py`
- **Función:** `main()`

### 9.2. Integración con PyQt5
```python
from PyQt5.QtWidgets import QApplication, QMainWindow
import sys

# Inicializar URA
from core.react_engine import ReActEngine
from core.security_policy import require_authorization

# Crear ventana principal
app = QApplication(sys.argv)
window = QMainWindow()
```

### 9.3. API Endpoints Disponibles

**POST /api/chat**
- Envía mensaje a URA
- Recibe respuesta del modelo

**GET /api/status**
- Estado del sistema
- CPU, RAM, Modelos activos

**POST /api/authorize**
- Solicita autorización para acciones sensibles
- Retorna True/False

**GET /api/memory**
- Recupera recuerdos de memoria persistente
- Parámetros: limit, offset

### 9.4. Seguridad en GUI
- **Verificar estados herméticos antes de acciones sensibles**
- **Usar decoradores:** `@check_payments_allowed`, `@check_credentials_allowed`, `@check_internet_allowed`
- **Autenticación:** Integrar con Face ID / Touch ID vía `security_policy.py`

### 9.5. Componentes de UI Recomendados
- **Chat Window:** Para conversación con URA
- **Status Panel:** CPU, RAM, Estado de modelos
- **Memory Viewer:** Visualizador de recuerdos
- **Security Panel:** Control de estados herméticos
- **Agent Selector:** Selector de agente activo
- **Log Viewer:** Visualizador de logs en tiempo real

### 9.6. Flujo de Usuario Típico
1. **Usuario inicia app** → URA carga configuración
2. **Usuario escribe mensaje** → RapidClassifier clasifica (Carretera 1/2)
3. **URA procesa** → ReAct Engine razona
4. **URA responde** → GUI muestra respuesta
5. **Si acción sensible** → Ventana emergente + Face ID
6. **Si gasto > 0.01€** → Autorización requerida

---

## 10. COMANDOS DE REFERENCIA

### Arrancar URA
```bash
cd ~/Desktop/URA_App
./start_ura.sh
```

### Ver Logs
```bash
tail -f ~/Desktop/URA_App/logs/ura_app.log
```

### Verificar Ollama
```bash
ollama list
```

### Probar Compilación
```bash
cd ~/Desktop/URA_App
source .venv/bin/activate
python3 -m py_compile main_final.py
```

### Backup Rápido
```bash
cd ~/Desktop/URA_App
cp -r . versions/ura_backup_$(date +%Y%m%d_%H%M%S)/
```

---

## 11. ESTADO ACTUAL DEL SISTEMA

### ✅ Operativo
- Cifrado con Fernet + keyring
- Memoria persistente funcional
- Redis instalado
- Ollama funcionando
- Sistema hermético implementado
- Política de gastos activa
- Ventanas emergentes macOS listas
- TrafficController operativo
- ReAct Engine funcional

### ⏸️ Pendientes
- Integración GUI (PyQt5)
- Configuración de puertos Flask/FastAPI
- Diseño de interfaz de usuario

---

## 12. CONTACTO Y SOPORTE

**Documentación Técnica:** Ver archivos en `core/`
**Logs:** `/Users/ramonesnaola/URA/ura_ia_1972/logs/ura_app.log`
**Configuración:** `/Users/ramonesnaola/URA/ura_ia_1972/config/`

---

**SISTEMA READY PARA DISEÑO DE PANTALLA** ✅
