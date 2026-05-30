# Sistema de Entrenamiento N3 con OpenClaw VM

**Estado**: Implementación completa (5 etapas)
**Fecha**: 2026-05-05

## Descripción

Sistema completo de entrenamiento masivo N3 utilizando OpenClaw corriendo en una máquina virtual UTM, con almacenamiento en disco externo Toshiba para generacion de búsquedas sintéticas.

## Arquitectura

```
Mac (16 GB RAM)
├── Ollama local (puerto 11434) - para URA N2
├── Ollama separado (puerto 11435) - para query_decomposer
├── Disco Toshiba (/Volumes/TOSHIBA_NUEVO/)
│   └── URA_entrenamiento/
│       ├── seeds.txt
│       ├── respuestas/
│       ├── decompose_cache.db
│       └── reports/
└── UTM VM Ubuntu Server 24.04 LTS
    ├── 8 GB RAM, 4 CPUs
    ├── OpenClaw + Ollama qwen2.5:7b
    └── API HTTP en puerto 5000
```

## Componentes Implementados

### STAGE 1: Script de configuración VM
- **Archivo**: `scripts/setup_openclaw_vm.sh`
- **Función**: Prepara entorno, genera cloud-init, crea archivos de configuración
- **Uso**: `bash scripts/setup_openclaw_vm.sh`

### STAGE 2: Conector URA ↔ OpenClaw
- **Archivo**: `core/openclaw_connector.py`
- **Función**: Cliente async para comunicar con OpenClaw VM
- **Métodos**:
  - `search(query, max_tokens)` - Búsqueda individual
  - `batch_search(queries, concurrency)` - Búsqueda en paralelo
  - `health_check()` - Verifica estado VM

### STAGE 3: Descomponedor de queries
- **Archivo**: `core/query_decomposer.py`
- **Función**: Descompone temas complejos en 15-20 subpreguntas atómicas
- **Métodos**:
  - `decompose(topic, n)` - Genera subpreguntas
  - `is_complex(topic)` - Determina si requiere descomposición
- **Cache**: SQLite en Toshiba

### STAGE 4: Pipeline de entrenamiento masivo
- **Archivo**: `core/training_orchestrator.py`
- **Función**: Orquesta generación de búsquedas sintéticas
- **Métodos**:
  - `night_training(max_queries)` - Ejecuta entrenamiento nocturno
  - `process_batch(queries)` - Procesa lotes en paralelo
- **Features**:
  - Control de saturación CPU
  - Validación de respuestas
  - Informes automáticos

### STAGE 5: Integración semilla manual
- **Archivos**: 
  - `config/seeds_manuales.txt` - Semillas prioritarias
  - `scripts/start_training.sh` - Script lanzador
- **Función**: Inicia entrenamiento completo

## Instalación

### 1. Conectar disco Toshiba
```bash
# Verificar que está montado
ls -la /Volumes/TOSHIBA_NUEVO/
```

### 2. Instalar dependencias
```bash
pip3 install -r requirements_n3.txt
```

### 3. Configurar VM en UTM
```bash
bash scripts/setup_openclaw_vm.sh
```

Seguir las instrucciones que muestra el script para:
- Crear VM Ubuntu Server 24.04 LTS en UTM
- Configurar red Host-Only (IP 192.168.64.100)
- Importar cloud-init.yaml
- Configurar carpeta compartida

### 4. Copiar servidor API a VM
```bash
scp vm_files/server.py root@192.168.64.100:/opt/openclaw_api/
```

### 5. Verificar VM
```bash
curl http://192.168.64.100:5000/health
```

## Uso

### Iniciar entrenamiento
```bash
bash scripts/start_training.sh
```

Este script:
1. Verifica Toshiba conectado
2. Verifica conexión VM
3. Instala dependencias
4. Carga semillas manuales
5. Ejecuta entrenamiento
6. Muestra resultados

### Uso programático
```python
from core.training_orchestrator import TrainingOrchestrator
import asyncio

async def train():
    orchestrator = TrainingOrchestrator(max_queries=500, concurrency=8)
    await orchestrator.night_training()

asyncio.run(train())
```

### Uso del conector directamente
```python
from core.openclaw_connector import OpenClawConnector
import asyncio

async def search():
    async with OpenClawConnector() as connector:
        result = await connector.search("test query")
        print(result)

asyncio.run(search())
```

## Archivos generados

### En Toshiba:
- `URA_entrenamiento/seeds.txt` - Semillas a procesar
- `URA_entrenamiento/respuestas/*.json` - Respuestas OpenClaw
- `URA_entrenamiento/decompose_cache.db` - Cache de descomposiciones
- `URA_entrenamiento/reports/*.json` - Informes de entrenamiento

### En proyecto:
- `.env` - Variables de entorno (VM URL, rutas Toshiba)
- `cloud-init.yaml` - Configuración inicial VM
- `vm_files/server.py` - Servidor API para VM

## Configuración

### Variables de entorno (.env):
```bash
VLLM_URL=http://192.168.64.100:5000
OPENCLAW_VM_IP=192.168.64.100
OPENCLAW_VM_PORT=5000
TOSHIBA_PATH=/Volumes/TOSHIBA_NUEVO
TRAINING_DIR=/Volumes/TOSHIBA_NUEVO/URA_entrenamiento
```

### Parámetros CLI:
```bash
python3 -m core.training_orchestrator --max 500 --concurrency 8 --cpu-threshold 80.0
```

## Monitoreo

### Estado de entrenamiento:
```python
from core.ura_openclaw_client import get_openclaw_status
status = get_openclaw_status()
print(status)
```

### Ver resultados:
```bash
# Contar respuestas generadas
ls /Volumes/TOSHIBA_NUEVO/URA_entrenamiento/respuestas/ | wc -l

# Ver último informe
cat /Volumes/TOSHIBA_NUEVO/URA_entrenamiento/reports/*.json | tail -1
```

## Troubleshooting

### VM no responde:
```bash
# Verificar VM está corriendo
# En UTM: verificar VM iniciada

# Verificar IP correcta
ping 192.168.64.100

# Verificar puerto
nc -zv 192.168.64.100 5000
```

### Toshiba no montado:
```bash
# Verificar disco conectado
diskutil list

# Montar manualmente si es necesario
diskutil mountDisk /dev/diskX
```

### Ollama separado no iniciado:
```bash
# Iniciar Ollama en puerto separado
bash scripts/start_ollama_openclaw.sh
```

## Semillas manuales

Las semillas en `config/seeds_manuales.txt` incluyen temas prioritarios:
- Leyes municipales Pamplona/Navarra
- Errores RRHH
- Cámaras de seguridad
- IA seguridad
- Herramientas OpenClaw
- Contabilidad española
- Cocina regional
- Marketing digital

## Seguridad

- Sin servicios de pago (solo Ollama local)
- Respaldo automático Toshiba antes de borrar
- Verificación de volumen antes de escribir
- Sin API keys externas configuradas

## Rendimiento

- Concurrency: 8 queries paralelas (configurable)
- Lotes: 50 queries por lote
- Control CPU: Pausa si > 80%
- Tiempo estimado: ~500 queries en 2-4 horas (dependiendo de VM)

## Próximos pasos

1. Crear VM en UTM siguiendo instrucciones de setup_openclaw_vm.sh
2. Verificar VM responde correctamente
3. Ejecutar start_training.sh antes de dormir
4. Revisar resultados por la mañana en Toshiba
5. Analizar informes en reports/
