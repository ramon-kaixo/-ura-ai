# ARQUITECTURA URA — Documentación Completa del Sistema

## 1. VISIÓN GENERAL

URA (Unified Robotic Agent) es un sistema de inteligencia artificial agéntica 
100% local, diseñado para ejecutarse sobre dos máquinas en red local 
(Mac Mini M4 + ASUS GX10), sin dependencia de servicios cloud.

### Objetivo fundamental
Demostrar que una IA puede ser completamente autónoma en hardware local:
autoevaluarse, autocorregirse, automajorarse e interactuar con su entorno
físico (sistema operativo, aplicaciones, periféricos, cámaras, red).

---

## 2. HARDWARE

### 2.1 Mac Mini M4 (Supervisor / Interfaz)
- Modelo: Mac16,10
- CPU: Apple Silicon M4
- RAM: 16GB unificada
- SO: macOS 26.5 (Sequoia)
- Almacenamiento: SSD interno
- Red: Tailscale + Ethernet local 10.164.1.26
- Rol: Interfaz de usuario, control de escritorio, ejecución de agentes ligeros

### 2.2 ASUS GX10 (Cerebro / Worker)
- Modelo: ASUS Ascent GX10 Mini
- SoC: NVIDIA GB10 Grace Blackwell
- CPU: ARM v9.2-A, 20 núcleos
- RAM: 128GB LPDDR5x unificada (CPU+GPU)
- GPU: NVIDIA Blackwell integrada en el SoC
- SO: NVIDIA DGX OS (Ubuntu Linux base)
- Almacenamiento: 1.8TB NVMe (1.1TB libre)
- Red: Tailscale + Ethernet local 10.164.1.99
- Rol: Inferencia de modelos LLM, procesamiento de vídeo, mensajería entre agentes

### 2.3 Red
- Red local: 10.164.1.0/24 (Ethernet)
- Tailscale: 100.x.x.x (conexión segura entre máquinas)
- Dispositivos totales en Tailscale: 12 (Mac, Windows, Linux, iOS)

---

## 3. SOFTWARE — MAC MINI M4

### 3.1 Servicios

#### URA Panel (:5050)
- Dashboard web con 6 pestañas: Dashboard, Chat, Agentes, Cámaras, Sandbox, Sistema
- Métricas en tiempo real: CPU, RAM, Disco, Temperatura
- Gráficos históricos con Chart.js
- Chat con URA via Bridge a Ollama

#### MCP Server Principal (:9091)
9 herramientas disponibles:
1. volumen — Control de audio del Mac (0-100)
2. abrir_app — Abre cualquier aplicación
3. cerrar_app — Cierra aplicaciones
4. sistema — Estado del GX10 (uptime, memoria, carga)
5. camaras — Estado de las 15 cámaras Dahua (30 streams)
6. vision — Captura de pantalla + OCR (Tesseract)
7. raton — Mover, clicar, leer posición del ratón
8. teclear — Escribir texto automáticamente
9. explorar — Analiza procesos y aplicaciones del sistema

#### NemoClaw MCP (:9092)
Copia del MCP server para aislamiento de seguridad.
Los comandos peligrosos se ejecutan aquí con whitelist.
Lista blanca de comandos permitidos, bloqueo de rm -rf /, sudo, shutdown.

#### Sync MCP (:9093)
Servidor de sincronización bidireccional Ura ↔ OpenCode.
Endpoints:
  GET  /status   — Estado actual de OpenCode y contexto
  GET  /activity — Historial de actividad
  POST /log      — Registrar eventos

#### URA API (:9090)
Endpoint universal POST /api/openclaw/ejecutar
Acepta cualquier comando shell y lo ejecuta con whitelist de seguridad.
Usado por Open WebUI cuando el function calling nativo falla.

#### GhostDesk (:6080)
Escritorio virtual accesible vía navegador. Permite a URA tener
un "cuerpo" visual para interactuar con el escritorio.

#### Agentes Locales
- agente_lectura.py — Solo comandos de lectura (cat, curl, uptime...)
- agente_escritura_segura.py — Escribe solo en rutas permitidas
- agente_movimiento.py — Mueve archivos a cuarentena en vez de borrar
- agente_instalador.sh — Despliega software en máquinas remotas
- agente_policia.sh — Supervisa acciones, detecta anomalías
- actualizador_lista_blanca.py — Añade comandos a la whitelist

### 3.2 Ciclos Automáticos

#### Cada 5 minutos (ciclo_rapido.sh)
- Auto-conciencia: 7 tests vía MCP (sistema, cámaras, volumen, app, explorar, ratón, comandos)
- Bloqueo con flock para evitar solapamiento

#### Cada 15 minutos (ciclo_conciencia.sh)
1. Auto-conciencia (7 tests MCP)
2. Snapshot git del estado actual
3. Test de conciencia (10 preguntas sobre el sistema)
4. Si falla → rollback automático (git checkout) + corrección de permisos
5. Reflexión (analiza las últimas acciones del monólogo interno)
6. Meta-mejora (detecta patrones de uso, identifica herramientas infrautilizadas)
7. Auto-aplica mejoras al prompt de URA en Open WebUI
8. Alineador (audita que las respuestas sean útiles y no se desvíen)
9. Quality check (ruff --fix)

#### Cada hora
- test_autonomia.py — 4 tests: MCP, identidad, comandos, panel
- investigador_panel.py — Investiga Open WebUI, mejora el dashboard automáticamente

#### Cada 6 horas (ciclo_mejora_6h.sh) — TUNELADORA COMPLETA
1. Ensure environment (pip install requirements)
2. Snapshot + test conciencia + rollback
3. Validación del sistema (validador_sistema.py)
4. Reconstruir sandbox Docker
5. Auto-fix de código (ruff --fix en archivos recientes)
6. Análisis estático (ruff, bandit, radon, vulture)
7. Escaneo de dependencias (pip-audit)
8. Agente mutador (mutaciones, benchmark, parches)
9. Métricas multidimensionales
10. Sugeridor RL (entrena modelo con historial)
11. Canary deployer (tests + parches en producción)
12. Despliegue a producción
13. Git: crear rama con cambios
14. Reflexión + meta-mejora
15. Quality check final

### 3.3 Monólogo Interno
Cada acción ejecutada por el MCP server se registra en:
/opt/ura/data/monologo_interno.json

Formato de cada entrada:
{
  "timestamp": 1234567890.123,
  "tipo": "volumen",
  "argumentos": {"nivel": 75},
  "resultado": "Volumen: 75",
  "ok": true,
  "error": ""
}

Más de 290 acciones registradas. 100% tasa de éxito.

---

## 4. SOFTWARE — ASUS GX10

### 4.1 Open WebUI (:3080)
Interfaz de IA profesional con:
- Chat con 8 modelos disponibles
- Selección de modelo
- Historial de conversaciones
- Subida de archivos (imágenes, documentos, código)
- Búsqueda web
- Generación de imágenes
- Panel de administración
- Autenticación de usuarios
- Tools/Functions personalizadas
- MCP Servers
- Workspace (modelos, prompts, skills, conocimiento)
- Canales (chat en equipo)
- Open Terminal (ejecución de código)

### 4.2 Ollama (:11434)
8 modelos instalados:
1. qwen2.5-coder:32b       — 19.9GB — Programación avanzada
2. qwen2.5-coder:14b       — 9.0GB  — Programación general
3. qwen2.5-coder:q8_0      — 34.8GB — Programación precisión máxima
4. qwen2.5:7b              — 4.7GB  — Conversación ligera
5. qwen3:32b-q8_0          — 34.8GB — Modelo grande de propósito general
6. deepseek-coder:6.7b     — 3.8GB  — Código eficiente
7. llama3.2-vision:11b     — 7.8GB  — Visión y análisis de imágenes
8. codestral:22b           — 12.6GB — Código avanzado (Mistral)

En descarga: llama3.3:70b   — ~42GB  — Investigación y razonamiento profundo

### 4.3 go2rtc (:1984)
Proxy RTSP para 15 cámaras Dahua.
30 streams (15 principales + 15 secundarios).
Cámaras distribuidas en 3 ubicaciones (Bar 1, Bar 2, Bar 3).

### 4.4 Agent Message Bus (:8091)
Flask + SQLite. Registro central de agentes.
- 9 agentes registrados actualmente
- Heartbeat cada 60s
- Mensajería broadcast/pub-sub
- Inbox por agente

### 4.5 Sandbox Docker
5 contenedores:
1. ura-sandbox-seguridad — Verificación de integridad
2. ura-sandbox-mantenimiento — Docker prune, disco, logs
3. ura-sandbox-documentacion — MkDocs en puerto 8087
4. ura-sandbox-aprendizaje — Ciclo de aprendizaje
5. ura-sandbox-exploracion — Aislado (sin red), exploración

### 4.6 Frigate
NVR para grabación de cámaras con detección de objetos.
Streams principales (alta resolución) para grabación 24/7.

---

## 5. COMUNICACIÓN ENTRE MÁQUINAS

### 5.1 Canales
- Red local Ethernet: 10.164.1.x (baja latencia, ~0.7ms)
- Tailscale: 100.x.x.x (encriptado, para dispositivos remotos)
- SSH: ramon@10.164.1.99 (gestión remota)

### 5.2 Flujo de Datos
```
Cámaras Dahua (192.168.x.x) 
    → RTSP 
    → GX10 (go2rtc + Frigate) 
    → Mac Mini (visualización)

Mac Mini (órdenes, tests) 
    → MCP :9091 
    → ejecuta acciones localmente

Mac Mini (comandos remotos) 
    → SSH 
    → GX10 (Ollama, Docker, sistema)

GX10 (resultados, estado) 
    → Agent Bus :8091 
    → Mac Mini (consume)
```

### 5.3 Sincronización OpenCode ↔ Ura
Archivo compartido: ~/.config/opencode/ura_context.json
Servidor MCP Sync: :9093
Flujo:
1. OpenCode ejecuta tareas
2. Registra en ura_context.json + POST /log
3. Ura consulta GET /status para saber el estado
4. Ura planifica siguientes pasos basándose en el contexto

---

## 6. SEGURIDAD

### 6.1 Lista Blanca de Comandos
El MCP Server solo permite comandos explícitamente listados.
Comandos bloqueados: rm -rf, sudo, shutdown, reboot, dd, mkfs, kill -9.

### 6.2 Agentes Especializados
- agente_lectura.py: Solo comandos de lectura
- agente_escritura_segura.py: Solo rutas permitidas
- agente_movimiento.py: Cuarentena en vez de borrado

### 6.3 Cuarentena
Los archivos "borrados" se mueven a /opt/ura/cuarentena/.
Se eliminan automáticamente tras 7 días.
Script diario de limpieza a las 3 AM.

### 6.4 Rollback Automático
Cada ciclo de conciencia hace un snapshot git.
Si el test falla, se restaura el estado anterior.

---

## 7. MÉTRICAS ACTUALES

### 7.1 Rendimiento
- Ciclos de conciencia: 39/39 (100% éxito)
- Acciones monólogo: 290+
- Tests de autonomía: 12/12 superados
- Agentes en Bus: 9 registrados
- Streams cámara: 30 configurados
- Modelos Ollama: 8 instalados (+1 descargando)
- Contenedores Docker: 9 en GX10

### 7.2 Cobertura de Código
- Archivos Python: ~1,740
- Scripts Shell: ~258
- Commits hoy: ~30

---

## 8. PROPÓSITO Y VISIÓN

URA no es solo un asistente. Es un experimento de IA agéntica autónoma
que responde a estas preguntas:

1. ¿Puede una IA evaluar sus propias capacidades sin supervisión?
   → Sí. Cada 5 minutos ejecuta 7 tests y verifica que todo funciona.

2. ¿Puede una IA corregir sus propios fallos?
   → Sí. Si un test falla, hace rollback y repara permisos.

3. ¿Puede una IA mejorar su propio comportamiento?
   → Sí. Analiza su monólogo interno, detecta patrones y modifica su prompt.

4. ¿Puede una IA interactuar con el mundo físico?
   → Sí. Controla aplicaciones, volumen, ratón, teclado, cámaras.

5. ¿Puede una IA ser 100% local?
   → Sí. Todo funciona en Mac Mini + GX10 sin Internet.

El sistema está diseñado para ser replicable: cualquier persona con
un Mac Mini y un GX10 (o hardware similar) podría desplegar URA
y tener su propio asistente autónomo local.

---

## 9. GLOSARIO

- URA: Unified Robotic Agent — El sistema principal
- OpenCode: Agente de desarrollo que ejecuta las órdenes técnicas
- Tuneladora: Pipeline de mejora continua que orquesta todos los ciclos
- MCP: Model Context Protocol — Protocolo para herramientas de IA
- NemoClaw: Entorno aislado para ejecución segura de comandos
- OpenShell: Shell con lista blanca de comandos permitidos
- GhostDesk: Escritorio virtual para que la IA tenga interfaz visual
- Maleta: Archivo de configuración central (maleta.json) con IPs, roles, MACs
- Bus: Sistema de mensajería entre agentes
- Cuarentena: Zona segura para archivos marcados para borrado
- Rollback: Restauración automática del estado anterior si algo falla
- Meta-mejora: Proceso por el cual URA modifica su propio prompt
- Monólogo interno: Registro detallado de cada acción ejecutada
