# n8n Manual for URA

## 1. Configuración de n8n en URA

**Estado actual:**
- n8n corre nativamente en el host (no en Docker)
- Puerto: 5678
- URL: http://localhost:5678
- Configuración: ~/.n8n/config
- Base de datos: ~/.n8n/database.sqlite

**Configuración Docker (futuro):**
```yaml
# docker-compose.yml
n8n:
  image: n8nio/n8n:latest
  container_name: ura-n8n
  ports:
    - "5678:5678"
  environment:
    - N8N_HOST=localhost
    - N8N_PORT=5678
    - N8N_PROTOCOL=http
    - N8N_API_DISABLED=false
    - N8N_API_KEY=ura_n8n_api_key_2026
    - N8N_ENCRYPTION_KEY=ura_encryption_key_2026
    - WEBHOOK_URL=http://localhost:5678/
    - NODE_FUNCTION_ALLOW_BUILTIN=curl
    - NODE_FUNCTION_ALLOW_EXTERNAL=*
  volumes:
    - n8n-data:/home/node/.n8n
  restart: unless-stopped
  networks:
    - ura-network
```

## 2. Activar API Key desde la UI

1. Abre http://localhost:5678 en el navegador
2. Inicia sesión si es necesario
3. Ve a Settings (icono de engranaje) → API
4. Activa "API" (toggle switch)
5. Genera o establece un API key
6. Copia el API key para usar en comandos curl

**Nota:** El API key se guarda en ~/.n8n/config:
```json
{
  "encryptionKey": "...",
  "api": {
    "key": "ura_n8n_api_key_2026",
    "disabled": false
  }
}
```

## 3. Importar Workflows via API con curl

**Formato básico:**
```bash
curl -X POST http://localhost:5678/api/v1/workflows \
  -H "X-N8N-API-KEY: {API_KEY}" \
  -H "Content-Type: application/json" \
  -d @config/n8n_workflow_name.json
```

**Importar todos los workflows de URA:**
```bash
cd ~/Desktop/URA_App
for f in config/n8n_*.json; do
  curl -X POST http://localhost:5678/api/v1/workflows \
    -H "X-N8N-API-KEY: ura_n8n_api_key_2026" \
    -H "Content-Type: application/json" \
    -d @"$f"
done
```

**Respuesta esperada:**
```json
{
  "id": "workflow_id",
  "name": "workflow_name",
  "active": false,
  "nodes": [...],
  "connections": {...},
  "settings": {...}
}
```

## 4. Activar/Desactivar Workflows via API

**Activar workflow:**
```bash
curl -X PATCH http://localhost:5678/api/v1/workflows/{WORKFLOW_ID} \
  -H "X-N8N-API-KEY: {API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"active": true}'
```

**Desactivar workflow:**
```bash
curl -X PATCH http://localhost:5678/api/v1/workflows/{WORKFLOW_ID} \
  -H "X-N8N-API-KEY: {API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"active": false}'
```

## 5. Ejecutar Workflow Manualmente via API

**Obtener workflow ID primero:**
```bash
curl -X GET http://localhost:5678/api/v1/workflows \
  -H "X-N8N-API-KEY: {API_KEY}"
```

**Ejecutar workflow:**
```bash
curl -X POST http://localhost:5678/api/v1/workflows/{WORKFLOW_ID}/execute \
  -H "X-N8N-API-KEY: {API_KEY}"
```

**Respuesta esperada:**
```json
{
  "data": {
    "resultData": {
      "runData": {...}
    },
    "executionData": {
      "executionId": "execution_id"
    }
  }
}
```

## 6. Endpoints de la API de n8n

**Workflows:**
- `GET /api/v1/workflows` - Listar todos los workflows
- `GET /api/v1/workflows/{id}` - Obtener workflow específico
- `POST /api/v1/workflows` - Crear/importar workflow
- `PATCH /api/v1/workflows/{id}` - Actualizar workflow
- `DELETE /api/v1/workflows/{id}` - Eliminar workflow
- `POST /api/v1/workflows/{id}/execute` - Ejecutar workflow manualmente
- `POST /api/v1/workflows/{id}/activate` - Activar workflow
- `POST /api/v1/workflows/{id}/deactivate` - Desactivar workflow

**Executions:**
- `GET /api/v1/executions` - Listar ejecuciones
- `GET /api/v1/executions/{id}` - Obtener ejecución específica
- `DELETE /api/v1/executions/{id}` - Eliminar ejecución

**Health:**
- `GET /healthz` - Health check (no requiere autenticación)

## 7. Qué hacer cuando la API devuelve 401

**Causas comunes:**
1. API key incorrecta o no configurada
2. API deshabilitada en settings
3. Header X-N8N-API-KEY mal formateado

**Soluciones:**
1. Verificar que la API key sea correcta en ~/.n8n/config
2. Ir a Settings → API en la UI y activar la API
3. Regenerar el API key desde la UI
4. Asegurar que el header sea `X-N8N-API-KEY: {key}` (no Bearer)
5. Reiniciar n8n si se modificó ~/.n8n/config manualmente

**Comando para verificar config:**
```bash
cat ~/.n8n/config
```

## 8. Workflows de URA

| Workflow | Puerto | Frecuencia | Trigger | Endpoint |
|----------|--------|------------|---------|----------|
| n8n_disk_check_workflow.json | 8101 | 15 min | Schedule | http://localhost:8101/health |
| n8n_ollama_health_workflow.json | 8102 | 5 min | Schedule | http://localhost:8102/health |
| n8n_disk_clean_workflow.json | 8103 | Manual | Reactive | http://localhost:8103/health |
| n8n_thread_cleaner_workflow.json | 8104 | 30 min | Schedule | http://localhost:8104/health |
| n8n_network_audit_workflow.json | 8105 | 60 min | Schedule | http://localhost:8105/health |
| n8n_ram_check_workflow.json | 8106 | Manual | Reactive | http://localhost:8106/health |
| n8n_cloud_backup_workflow.json | 8107 | Manual | Reactive | http://localhost:8107/health |
| n8n_health_report_workflow.json | 8108 | Manual | Reactive | http://localhost:8108/health |

**Lógica de alertas:**
- Los workflows solo alertan cuando `estado == "error"` o `estado == "warning"`
- Estado `"pendiente"` (sin ejecuciones previas) NO activa alertas
- Estado `"ok"` NO activa alertas

**Estructura de los workflows:**
1. **Schedule/Trigger** - Ejecución periódica o manual
2. **HTTP Request** - Llama al endpoint `/health` del nodo
3. **If condition** - Verifica `estado == "error"` OR `estado == "warning"`
4. **Log Alert** - Escribe a `/logs/n8n/alertas.jsonl` si hay error

**Importación masiva:**
```bash
cd ~/Desktop/URA_App
API_KEY="ura_n8n_api_key_2026"
for f in config/n8n_*.json; do
  echo "Importando $f..."
  curl -X POST http://localhost:5678/api/v1/workflows \
    -H "X-N8N-API-KEY: $API_KEY" \
    -H "Content-Type: application/json" \
    -d @"$f"
  echo ""
done
```
