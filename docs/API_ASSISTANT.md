# URA Assistant API — Documentación

## Endpoint base
```
POST http://10.164.1.99:8003/api/v1/chat
```

## Autenticación
Si `URA_API_KEY` está configurada, todas las peticiones requieren:
```
Authorization: Bearer <API_KEY>
```
Sin autenticación: el endpoint está abierto.

---

## Chat

### Request
```json
{
  "user_id": "test",
  "conversation_id": "mi-chat-1",
  "message": "dime el estado del repo",
  "mode": "conversacion",
  "stream": false
}
```

| Campo | Tipo | Defecto | Descripción |
|-------|------|---------|-------------|
| `user_id` | string | `""` | Identificador de usuario (aisla conversaciones) |
| `conversation_id` | string | `""` | ID de conversación (vacío = nueva) |
| `message` | string | — | Mensaje del usuario (máx 100K chars) |
| `mode` | string | `"conversacion"` | `conversacion`, `trabajo`, `explicacion` |
| `stream` | bool | `false` | `true` = respuesta vía SSE streaming |

### Response (stream=false)
```json
{
  "conversation_id": "mi-chat-1",
  "reply": "El repositorio tiene un archivo modificado...",
  "intent": "command",
  "turn_count": 2
}
```

### Response (stream=true)
Eventos SSE:
```
data: {"type":"token","data":{"text":"El"}}
data: {"type":"token","data":{"text":" repositorio"}}
data: {"type":"token","data":{"text":" tiene"}}
...
data: {"type":"complete","data":{"reply":"El repositorio tiene...","conversation_id":"mi-chat-1","intent":"command","mode":"conversacion"}}
```

---

## Health
```
GET http://10.164.1.99:8003/health
```
```json
{"status":"ok","version":"0.29.0","auth":false}
```

---

## Comandos disponibles
El asistente ejecuta comandos reales cuando detecta intención de comando:

| Keywords en el mensaje | Comando ejecutado |
|------------------------|-------------------|
| "status", "estado" | `git status --short` |
| "log" | `git log --oneline` |
| "diff" | `git diff --stat` |
| "docker", "contenedor" | `docker ps` |
| "busca", "buscar", "search" | DuckDuckGo web search |

---

## Modos conversacionales

| Modo | Comportamiento |
|------|---------------|
| `conversacion` | Respuestas naturales, cortas, lenguaje coloquial |
| `trabajo` | Preciso, bullet points, estructura profesional |
| `explicacion` | Profundo, ejemplos, paso a paso, didáctico |

---

## Idiomas
Detección automática español/inglés. Responde en el mismo idioma del mensaje.

---

## Despliegue local
```bash
URA_API_KEY=mi-clave-secreta python -m motor.assistant.main
```

O con Docker:
```bash
cd deploy
URA_API_KEY=mi-clave docker compose up -d
```
