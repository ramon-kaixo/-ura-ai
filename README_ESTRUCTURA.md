# URA - Universal Reasoning Agent - Estructura del Sistema

## Resumen Ejecutivo

Universal Reasoning Agent (URA) es un framework de inteligencia artificial sofisticado diseñado para tareas complejas de razonamiento con mantenimiento automatizado y garantía de calidad del código. El sistema está compuesto por componentes principales que trabajan en conjunto para proporcionar capacidades avanzadas de procesamiento, memoria, monitoreo y mantenimiento automático.

## Componentes Principales

### 1. Memory Engine (`motor/core/memory_engine.py`)
- Implementa RAG (Retrieval-Augmented Generation)
- Indexa documentos en base de datos vectorial Qdrant
- Maneja fragmentación y embeddings usando Ollama
- Proporciona capacidades deterministas de consulta y generación de respuestas

### 2. Configuration Manager (`motor/core/config_manager.py`)
- Gestiona configuraciones del sistema con perfiles específicos por OS  
- Soporta diferentes configuraciones para Linux (Asus GX10) vs Darwin (Mac)
- Maneja expansión y validación de rutas
- Incluye validación mediante esquema de archivos de configuración

### 3. Cleanup Plugin (`scripts/pro/tuneladora/plugins/cleanup.py`)
- Funcionalidad de mantenimiento y limpieza del sistema  
- Gestiona rotación de logs, limpieza de embeddings, vacuado de bases de datos
- Implementa monitoreo de espacio en disco
- Maneja limpieza de aislamiento de procesos

### 4. AST Sentinel (`core/guardians/ast_sentinel.py`)
- Herramienta de análisis de calidad del código  
- Realiza análisis de complejidad ciclomática
- Detecta números mágicos y marcadores de deuda técnica (TODO/FIXME)
- Aplica estándares y mejores prácticas de codificación

## Arquitectura de Componentes

```
┌─────────────────┐    ┌───────────────────┐    ┌──────────────────┐
│   Memory Engine │────▶  Configuration  │────▶  Cleanup Plugin│
│                 │    │     Manager       │    │                  │
└─────────────────┘    └───────────────────┘    └──────────────────┘
        ▲                       ▲                        ▲
        │                       │                        │
        │                       │                        │
┌─────────────────┐    ┌───────────────────┐    ┌──────────────────┐  
│   AST Sentinel  │────▶  Core Components│────▶  RAG Pipeline  │
└─────────────────┘    └───────────────────┘    └──────────────────┘

```

## Tecnologías Utilizadas

- **Python 3.8+** como lenguaje principal
- **Ollama** para generación de embeddings (modelo nomic-embed-text)
- **Qdrant** como base de datos vectorial  
- **JSON** para gestión de configuraciones
- **Path expansion** y validación de rutas
- **SHA-256 hashes** para indexación determinista

## Procedimientos de Mantenimiento

### 1. Limpiador Automático (Cleanup Plugin)
- Rotación de archivos de log (retención de 30 días por defecto)  
- Limpieza de embeddings para archivos huérfanos
- Optimización de bases de datos SQLite
- Monitoreo del espacio en disco con advertencias

### 2. Seguridad y Calidad
- Análisis AST basado en complejidad ciclomática (máx 10)
- Límites en cantidad de líneas por función (máx 50)  
- Detección de operaciones prohibidas (os.system, eval, exec)
- Seguimiento de marcadores TODO/FIXME

## Métodos de Calidad y Seguridad

### Control de Calidad
- Análisis AST completo para métricas de calidad:
  - Complejidad ciclomática limitada
  - Conteo de líneas por función
  - Detección de importaciones prohibidas
  - Identificación de números mágicos

### Seguridad Implementada  
- Sistema de verificación y auditoría automática (AST Sentinel)
- Procedimientos de limpieza seguros para datos sensibles
- Monitoreo continuo del estado del sistema 
- Implementación de circuit breakers

## Instalación y Configuración

### Prerrequisitos
- Python 3.8+
- Ollama instalado y ejecutándose  
- Servidor Qdrant en funcionamiento

### Instalación
```bash
pip install -e .
```

### Configuración Inicial
1. Configurar el sistema en `config/system_config.json`
2. Ejecutar motor de memoria para indexar documentos  
3. Consultar el sistema RAG con preguntas en lenguaje natural

## Características Clave

### Determinismo Operativo
- Todos los componentes están diseñados para ser deterministas
- Sin variables globales afectando estado
- Comportamiento predecible y reproducible

### Soporte Multiplataforma  
- Sistema de configuración detecta automáticamente el sistema operativo
- Aplicación de perfiles específicos según hostname

## Mantenimiento Automático
El framework incluye funcionalidades automáticas para:
- Monitoreo del espacio en disco
- Limpieza automática de archivos temporales y logs
- Optimización de bases de datos  
- Detección y reporte de deuda técnica