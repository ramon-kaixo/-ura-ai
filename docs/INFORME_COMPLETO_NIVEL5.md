# URA — Informe Completo del Sistema (Nivel 5)

**Fecha:** 2026-05-19
**Version:** Nivel 5 — Autonomia Colaborativa Total
**Arquitecto:** URA Development Team

---

## 1. Resumen Ejecutivo

URA (Urban Robotic Assistant) es un sistema multi-agente de inteligencia artificial diseñado para la gestion autonoma de bares y restaurantes. Opera en una arquitectura distribuida con dos nodos principales (Mac Mini como cerebro, GX10 como motor IA), 25 camaras Dahua conectadas a Frigate, integracion con TPV via API, y un enjambre de buzos especializados que operan de forma autonoma.

El sistema alcanza el **Nivel 5 de autonomia**: auto-organizacion, auto-reparacion, aprendizaje federado entre locales, y toma de decisiones con gestion de confianza y escalado etico.

---

## 2. Arquitectura de Hardware

```
┌─────────────────────────────────────────────────────────────────┐
│                        MAC MINI (Cerebro)                        │
│  ┌─────────────┐ ┌──────────────┐ ┌─────────────┐ ┌──────────┐ │
│  │ Laia Agent  │ │ Autonomia    │ │ Enjambre    │ │ Frigate  │ │
│  │ (Nivel 5)   │ │ Avanzada     │ │ (22+ buzos) │ │ (25 cams)│ │
│  └──────┬──────┘ └──────┬───────┘ └──────┬──────┘ └────┬─────┘ │
│         │               │                │              │        │
│  ┌──────▼───────────────▼────────────────▼──────────────▼─────┐ │
│  │              Message Bus (Redis Pub/Sub)                    │ │
│  └──────────────────────────┬─────────────────────────────────┘ │
│                             │ Tailscale                          │
└─────────────────────────────┼────────────────────────────────────┘
                              │
┌─────────────────────────────▼────────────────────────────────────┐
│                     GX10 - ASUS X10 (Motor IA)                    │
│  ┌─────────────┐ ┌──────────────┐ ┌─────────────┐ ┌──────────┐ │
│  │ Ollama      │ │ n8n          │ │ ChromaDB    │ │ Buzos    │ │
│  │ LLMs        │ │ Workflows    │ │ Vector DB   │ │ Python   │ │
│  └─────────────┘ └──────────────┘ └─────────────┘ └──────────┘ │
│  Modelos: qwen3:32b, llama3.2-vision:11b, faster-whisper        │
└─────────────────────────────┬────────────────────────────────────┘
                              │
┌─────────────────────────────▼────────────────────────────────────┐
│                    HETZNER VPS (Cloud)                           │
│  ┌─────────────┐ ┌──────────────┐                                │
│  │ SearXNG     │ │ Exit Node    │                                │
│  │ (busqueda)  │ │ Tailscale    │                                │
│  └─────────────┘ └──────────────┘                                │
└──────────────────────────────────────────────────────────────────┘

Perifericos:
- 25 camaras Dahua (RTSP) → Frigate (deteccion personas/objetos)
- TPV (API REST) → Ventas, stock, clientes
- ESP32 (MQTT) → Sensores IoT (puerta, temperatura)
- Disco 1TB → Backups locales
```

---

## 3. Los 10 Puntos Ciegos Resueltos

### Punto 1 — Indexacion Multimodal de Manuales
**Problema:** Los manuales solo se indexaban como texto plano.
**Solucion:** `core/indexing/multimodal_indexer.py` procesa PDFs, imagenes (OCR Tesseract) y videos (extraccion de frames cada N segundos + OCR).
**Archivos:**
- `core/indexing/multimodal_indexer.py`
- `scripts/indexar_manuales_multimodal.sh`
**Programacion:** Diario 02:00 via launchd.
**Uso:** Colocar archivos en `/opt/ura/docs/manuales/` y se indexan automaticamente en ChromaDB.

### Punto 2 — Autodescubrimiento de Interfaces (Fuzzing UI)
**Problema:** URA necesitaba conocer cada app manualmente.
**Solucion:** `core/discovery/fuzzer.py` explora aplicaciones de forma autonoma, construye un grafo de estados UI (nodos = pantallas, aristas = clics).
**Comando de voz:** "URA, explora [nombre app]"
**Salida:** `/opt/ura/data/ui_graph.json`
**Integracion:** Se registra cada transicion en la memoria semantica.

### Punto 3 — Aprendizaje Federado entre Bares
**Problema:** Cada bar aprendia de forma aislada.
**Solucion:** `core/federated/client.py` exporta experiencias anonimizadas (ultimas 24h) a un servidor central que agrega pesos globales.
**Archivos:**
- `core/federated/client.py` (cliente en cada bar)
- `scripts/federated_learn.py` (servidor central)
**Programacion:** Diario 03:00 via bucle autonomia.
**Privacidad:** Solo se comparten experiencias anonimizadas, nunca datos personales.

### Punto 4 — Gestion de Confianza e Incertidumbre
**Problema:** URA ejecutaba acciones sin evaluar su probabilidad de exito.
**Solucion:** `core/confidence/uncertainty.py` calcula confianza (0-1) basada en 3 señales:
1. Similitud con manuales indexados (ChromaDB)
2. Tasa de exito historico
3. Episodios pasados similares
**Umbral:** Si confianza < 0.7, pide confirmacion al gerente.
**Integracion:** Cada accion en `laia_agent.py` pasa por el estimador.

### Punto 5 — Auto Fine-Tune de Modelos de Vision
**Problema:** El modelo de deteccion de platos no mejoraba con el tiempo.
**Solucion:** `core/vision/auto_finetune.py` recopila snapshots de Frigate (eventos de cocina) y hace fine-tune de YOLOv8.
**Archivos:**
- `core/vision/auto_finetune.py`
- `scripts/auto_finetune_vision.sh`
**Programacion:** Semanal domingo 03:00 via launchd.
**Dataset:** `/opt/ura/data/vision_dataset/` (imagenes + labels)

### Punto 6 — Cache Meteorologico con Prediccion ARIMA
**Problema:** URA no tenia datos del clima para decisiones (terrazas, afluencia).
**Solucion:** `core/weather/cached_weather.py` consulta Open-Meteo API (gratuita), cachea resultados, y si la API falla, predice con ARIMA sobre historico.
**Comando de voz:** "URA, como esta el clima?"
**Integracion:** Regla 8 de autonomia (ajuste de terrazas segun lluvia).
**Cache:** `/opt/ura/data/weather_cache.json`

### Punto 7 — Orquestacion Emergente con Bus de Mensajes
**Problema:** Los buzos operaban de forma aislada sin colaboracion.
**Solucion:** `core/orchestrator/swarm_orchestrator.py` suscribe eventos en Redis y desencadena acciones coordinadas:
- `eventos/stock_bajo` → publica `tareas/reabastecer` + `consultas/precios`
- `eventos/cliente_enfadado` → publica `acciones/cortesia`
- `eventos/fallo_red` → ejecuta `network_autorepair.sh`
- `eventos/clima_extremo` → ajusta terrazas
**Bus:** `core/message_bus.py` (Redis Pub/Sub)
**Descomposicion de objetivos:** LLM descompone objetivos complejos en tareas atomicas.

### Punto 8 — Anonimizacion Automatica de Datos
**Problema:** Logs e imagenes contenian datos personales.
**Solucion:** `scripts/anonymize_data.py` recorre logs, episodios e imagenes:
- Texto: Reemplaza nombres de empleados y matriculas con placeholders
- Imagenes: Detecta rostros con `face_recognition` y los pixela
**Programacion:** Diario 04:00 via launchd.
**Paths:** `/opt/ura/logs/`, `/opt/ura/data/episodic_db/`, `/opt/ura/knowledge/`

### Punto 9 — Feedback Latente (Recompensa Retardada)
**Problema:** URA no podia medir el impacto a largo plazo de sus acciones.
**Solucion:** `core/feedback/latent_reward.py` registra acciones pendientes y las evalua despues (1 hora) con metricas reales:
- Tiempo de estadia del cliente (0.4 peso)
- Ventas generadas (0.4 peso)
- Repeticion de visita (0.2 peso)
**Integracion:** Cada accion en `laia_agent.py` registra un ID que se evalua diferidamente.
**Persistencia:** `/opt/ura/data/pending_actions.json`

### Punto 10 — Dialogo Contextual en Lenguaje Natural
**Problema:** URA no mantenia contexto entre conversaciones.
**Solucion:** `agents/dialogue_manager.py` gestiona conversaciones multi-turno:
- Historial en Redis (expira en 24h)
- LLM local via Ollama (qwen3:32b)
- Enriquecimiento con memoria episodica ("recuerdo que...")
**Comando de voz:** Cualquier pregunta natural, URA mantiene contexto.

---

## 4. Sistema de Auto-Reparacion del GX10

### Arquitectura
```
Mac Mini (cada 30 min)
    │
    ├── ping 100.127.206.86
    │   ├── OK → verifica health API :5103
    │   │   ├── OK → todo bien
    │   │   └── FAIL → lanza reparacion
    │   └── FAIL → lanza reparacion
    │
    └── ssh gx10 (alias SSH key-based)
        ├── Repara DNS (8.8.8.8 + 1.1.1.1)
        ├── Reinicia systemd-resolved
        ├── Reactiva Tailscale
        ├── Verifica Ollama
        └── Verifica conectividad Internet
```

### Archivos
- `scripts/fix_gx10_remote.sh` — Reparacion remota via SSH
- `scripts/fix_gx10.sh` — Reparacion local (ejecutar en GX10 con monitor)
- `scripts/setup_ssh_gx10.sh` — Configuracion inicial SSH (una sola vez)
- `config/gx10.json` — Config con IPs, usuario, puertos

### Configuracion SSH (una sola vez)
```bash
bash scripts/setup_ssh_gx10.sh
# Genera clave ed25519, copia al GX10, crea alias ~/.ssh/config
```

### Integracion en Autonomia
`agents/autonomia_avanzada.py`:
- Metodo `verificar_y_reparar_gx10()` ejecutado cada 30 minutos
- Metodo `_ejecutar_reparacion_remota()` lanza script en segundo plano
- Endpoint API `/sistema/gx10_reparado` para confirmacion

---

## 5. Integracion TPV por API

### Conector
`core/connectors/tpv_connector.py` — Clase `TPVApiConnector` que hereda de `APIConnector`:
- `ventas_hoy()` → ventas del dia
- `stock(producto)` → nivel de stock con umbral
- `registrar_venta(data)` → nueva venta
- `clientes_hoy()` → contador de clientes

### Mock Server
`scripts/mock_tpv_api.py` — Servidor Flask para desarrollo:
- Endpoint `/api/ventas/diarias`
- Endpoint `/api/stock/<producto>`
- Endpoint `/api/ventas/nueva` (POST)
- Endpoint `/api/clientes/hoy`
- Endpoint `/api/health`
- Puerto: 8080

### Configuracion
`config/tpv_endpoints.json`:
```json
{
  "base_url": "http://100.127.206.86:8080/api",
  "api_key": "ura_tpv_dev_key",
  "endpoints": { ... }
}
```

### Servicio Mock TPV
`config/mock_tpv.plist` — launchd KeepAlive para macOS.

---

## 6. Sistema de Camaras (Frigate)

### Configuracion
`config/frigate.yml` — Configuracion base con MQTT, detectores, retencion.
`config/frigate_camaras_ejemplo.yml` — Ejemplo completo con:
- go2rtc streams RTSP para 25 camaras Dahua
- Zonas configurables (entrada, barra, cocina)
- Mascara de movimiento (ignorar zonas falsas positivas)
- Deteccion de personas, botellas, vasos
- Retencion de eventos: 7-14 dias

### Docker Frigate
```bash
docker run -d --name frigate \
  -v /opt/ura/frigate/config.yml:/config/config.yml \
  -v /opt/ura/frigate/storage:/media/frigate \
  -p 5000:5000 -p 8554:8554 \
  ghcr.io/blakeblackshear/frigate:stable
```

---

## 7. Timers Launchd (7 programaciones)

| Timer | Frecuencia | Script | Log |
|-------|-----------|--------|-----|
| `com.ura.enjambre` | Cada 15 min | `orquestador/bibliotecario.sh` | `/tmp/ura_enjambre.log` |
| `com.ura.autonomia` | Cada 5 min | `agents/autonomia_avanzada.py` | `/tmp/ura_autonomia.log` |
| `com.ura.indexacion` | Diario 02:00 | `scripts/indexar_manuales_multimodal.sh` | `/tmp/ura_indexacion.log` |
| `com.ura.backup_config` | Diario 03:00 | `scripts/backup_config.sh` | `/tmp/ura_backup_config.log` |
| `com.ura.vision_finetune` | Domingo 03:00 | `scripts/auto_finetune_vision.sh` | `/tmp/ura_vision_finetune.log` |
| `com.ura.anonimizacion` | Diario 04:00 | `scripts/anonymize_data.py` | `/tmp/ura_anonimizacion.log` |
| `com.ura.mocktpv` | Siempre activo | `scripts/mock_tpv_api.py` | `/tmp/mock_tpv.log` |

---

## 8. Enjambre de Buzos (22+)

### Dominios
- **red** — Analisis de red, WiFi, IPs, DNS
- **vigilancia** — Camaras, deteccion de intrusos, eventos
- **marketing** — Analisis de redes sociales, reseñas
- **cocina** — Control de platos, inventario, recetas
- **flota** — Gestion de vehiculos, repartidores
- **sistema** — Salud del sistema, recursos, backups
- **orquestador** — Coordinacion, reflexion, meta-aprendizaje

### Calidad
`buzo_calidad.sh` — Verifica que todos los buzos funcionen correctamente.

### Meta-Aprendizaje
- `reflexion_ciclo.sh` — Analiza resultados y ajusta frecuencias
- `evaluar_impacto.sh` — Evalua impacto de cambios (cada 4 semanas)

---

## 9. Tuneladora (7 Rodillos de Calidad)

Pipeline de validacion antes de cada commit:
1. **Preflight** — Verificacion de estructura y dependencias
2. **Ruff fix** — Auto-correccion de estilo Python
3. **Autoflake** — Eliminacion de imports no usados
4. **Pytest** — Ejecucion de tests (44/44 pasando)
5. **Bandit** — Analisis de seguridad
6. **Debug guard** — Verificacion de prints/debug残留
7. **Cleanup** — Limpieza de cache y temporales

### Auto-Cleanup
`scripts/auto_cleanup.sh` — Ejecucion diaria 00:00 via launchd.
### Quarantine
Fallos van a `quarantine/` con timestamp. Limpieza automatica tras 7 dias.

---

## 10. Seguridad

### SSH
- Clave ed25519 sin passphrase para acceso Mac → GX10
- Alias `gx10` en `~/.ssh/config` con timeout y StrictHostKeyChecking
- Credenciales opcionales en macOS Keychain (`core/security/ssh_credentials.py`)

### Anonimizacion
- Nombres de empleados → `[EMPLEADO]`
- Matriculas → `[MATRICULA]`
- Rostros en imagenes → pixelados

### Sandbox
- Todos los cambios autonomos pasan por sandbox + rollback
- Allowlist de red para contenedores
- No `shell=True` en subprocess

### Tuneladora
- 7 rodillos de validacion antes de commit
- Fallos aislados en quarantine

---

## 11. Comandos de Voz Disponibles

| Comando | Accion |
|---------|--------|
| "URA, repara la red" | Restaurar conectividad |
| "URA, monta el disco de backup" | Montar unidad externa |
| "URA, lanza buzo buzo_red" | Analisis de red |
| "URA, clic en [texto]" | Clic por vision |
| "URA, escribe [texto]" | Teclear texto |
| "URA, informe de consumo" | Consumos empleados |
| "URA, analiza la limpieza" | Eficiencia limpieza |
| "URA, reporta comportamientos" | Actitudes no catalogadas |
| "URA, como exporto las ventas?" | Consulta manual + ejecuta |
| "URA, +1 punto" / "-1 punto" | Feedback RLHF |
| "URA, explora [app]" | Fuzzing UI |
| "URA, como esta el clima?" | Prediccion meteorologica |
| "URA, planifica [objetivo]" | Descomponer objetivo |

---

## 12. Informes Automaticos

Generados mensualmente en `/opt/ura/informes/`:

| Informe | Contenido |
|---------|-----------|
| `informe_eficiencia_empleados.csv` | Tiempos atencion, pausas, productividad |
| `informe_consumo_barra.csv` | Bebidas por empleado |
| `informe_rotaciones.csv` | Platos rotos por persona |
| `informe_almacen.csv` | Accesos repartidores, intentos robo |
| `informe_mejora_continua.pdf` | Sugerencias optimizacion |

---

## 13. Backup y Recuperacion

### Backup Config
`scripts/backup_config.sh` — Diario 03:00:
- Config legal, TPV, GX10, Frigate, maleta
- ChromaDB, episodic DB, macros
- Sync automatico al GX10 via SCP
- Purge automatico de backups > 30 dias

### Backup Discos Locales
`scripts/backup_discos_locales.sh` — Cron GX10 diario 02:00:
- Knowledge, scripts, config
- Modelos Ollama

### Plan de Supervivencia
`docs/PLAN_SUPERVIVENCIA.md`:
- **Escenario A:** Cae el Mac → GX10 sigue operando autonomamente
- **Escenario B:** Cae el GX10 → Mac ejecuta Tuneladora local, notifica watchdog
- **Escenario C:** Cae Tailscale → Cada maquina opera autonomamente

---

## 14. Despliegue Completo

### Paso 1: Instalacion base
```bash
unzip ~/URA/ura_ia_1972/ura_paquete_nivel5.zip -d /opt/ura
cd /opt/ura && bash scripts/final_install.sh
sudo bash scripts/instalar_autonomia.sh
```

### Paso 2: Conexion GX10
```bash
bash scripts/setup_ssh_gx10.sh
bash scripts/deploy_gx10.sh
```

### Paso 3: Verificacion
```bash
curl http://localhost:5105/health && echo " - Mac OK"
curl http://100.127.206.86:5103/health && echo " - GX10 OK"
```

### Paso 4: Camaras (opcional)
```bash
nano /opt/ura/config/frigate_camaras_ejemplo.yml  # Editar IPs RTSP
cp /opt/ura/config/frigate_camaras_ejemplo.yml /opt/frigate/config/config.yml
docker restart frigate
```

### Paso 5: TPV Real (opcional)
```bash
nano /opt/ura/config/tpv_endpoints.json  # URL y API key real
nano /opt/ura/.env  # TPV_API_KEY=clave_real
```

---

## 15. Guia para Gerentes

Documento completo en `docs/GUIA_GERENTES.md`.

### Mantenimiento Minimo
- Revisar informes mensuales
- Editar `config/legal_rules.json` para ajustar politicas
- Añadir manuales en `docs/manuales/` (se indexan automaticamente)
- El sistema se actualiza solo (`auto_update.sh` diario)

### Escalamiento de Decisiones
- Notificacion por Telegram o pantalla
- Responder por voz: "Si, aprobar" o "No, denegar"
- Timeout 5 minutos → denegacion por defecto

---

## 16. Stack Tecnologico

| Componente | Tecnologia | Funcion |
|------------|-----------|---------|
| LLM | Ollama (qwen3:32b, llama3.2-vision) | Razonamiento, planificacion |
| STT | faster-whisper (base) | Transcripcion voz |
| TTS | macOS `say` | Sintesis voz |
| Vector DB | ChromaDB | Memoria semantica |
| Message Bus | Redis Pub/Sub | Coordinacion enjambre |
| IoT | Mosquitto MQTT | Sensores ESP32 |
| Vision | Frigate + YOLOv8 | Deteccion camaras |
| Busqueda | SearXNG (Hetzner) | Busqueda web |
| Orchestrator | n8n (GX10) | Workflows visuales |
| Monitoring | Prometheus + Grafana | Metricas |
| Tunel | Tailscale | Red segura |
| Tests | pytest (44/44) | Validacion |
| Lint | Ruff (ALL rules) | Calidad codigo |

---

## 17. Estado Actual

| Modulo | Estado | Tests |
|--------|--------|-------|
| Laia Agent (Nivel 5) | ✅ Integrado | — |
| 10 Puntos Ciegos | ✅ Implementados | Ruff clean |
| Auto-reparacion GX10 | ✅ SSH key-based | — |
| TPV API + Mock | ✅ Conector + servidor | — |
| Frigate 25 camaras | ✅ Config ejemplo | — |
| 7 Timers Launchd | ✅ Instalables | — |
| Enjambre 22+ buzos | ✅ Operativo | — |
| Tuneladora 7 rodillos | ✅ Activa | 44/44 pass |
| Backup + Sync GX10 | ✅ Configurado | — |
| Anonimizacion | ✅ Diaria | — |
| Guia Gerentes | ✅ Documentada | — |

---

## 18. Proximos Pasos (Roadmap)

1. **Desplegar en produccion** → Ejecutar los 3 comandos de despliegue
2. **Configurar 25 camaras** → Editar IPs RTSP en frigate config
3. **Conectar TPV real** → Reemplazar mock con API real
4. **Sensores IoT** → Configurar ESP32 + MQTT para puerta/temperatura
5. **Aprendizaje federado** → Conectar segundo bar al servidor central
6. **Fine-tune YOLO** → Etiquetar primeras imagenes de cocina manualmente
7. **Monitor Grafana** → Dashboard en tiempo real de todos los agentes

---

*Informe generado automaticamente por URA Development Team — 2026-05-19*
