# CHANGELOG URA — 2026-05-24

## Resumen del dia
Sistema URA alcanzo autonomia operacional completa.

## Cambios realizados

### 00:00 - Diagnostico
- Detectado bug de function calling en Open WebUI (#23927)
- Modelos personalizados no reenvian function_calling a Ollama

### 01:15 - Tool universal
- Creado endpoint /api/openclaw/ejecutar en ura_api.py
- Tool "Ejecutar" en Open WebUI que evita el bug
- URA ya puede ejecutar comandos desde el chat

### 02:30 - Autoevaluacion
- auto_conciencia.py: 5 tests de capacidades via MCP
- ciclo_rapido.sh con flock cada 5 min
- ciclo_conciencia.sh cada 15 min (completo)
- 5/5 tests superados desde el primer momento

### 03:00 - Seguridad
- Lista blanca de comandos en MCP server
- agente_lectura.py: solo comandos lectura
- agente_escritura_segura.py: rutas permitidas
- agente_movimiento.py: cuarentena en vez de borrar
- rm -rf / bloqueado, uptime permitido

### 04:00 - Panel e investigacion
- investigador_panel.py: mejora el panel cada hora
- MCP server con 6 tools operativas
- endpoint /api/openclaw/ejecutar funcional

### 05:00 - Autonomia
- test_autonomia.py: 4 tests (MCP, identidad, comandos, panel)
- RESULTADO: 4/4 - URA ES AUTONOMA

### Arquitectura final

Cada 5 min:  ciclo_rapido.sh (auto-conciencia MCP)
Cada 15 min: ciclo_conciencia.sh (snapshot + test + rollback + reflexion + calidad)
Cada 60 min: test_autonomia.py + investigador_panel.py
Cada 6h:     ciclo_mejora_6h.sh (tuneladora completa)

Seguridad:
- MCP con lista blanca de comandos
- Agentes especializados (lectura, escritura segura, cuarentena)
- rm sustituido por movimiento a cuarentena
- Rollback automatico si test falla

### Componentes activos
- Open WebUI v0.9.5 en GX10 :3080
- MCP Server en Mac :9091 (6 tools)
- API universal en Mac :9090
- Bus de mensajes en GX10 :8091
- go2rtc camaras en GX10 :1984 (30 streams)
- GhostDesk en Mac :6080
- 8 modelos Ollama en GX10
- 5 contenedores sandbox en GX10
- 15 camaras Dahua configuradas
- 9 agentes registrados en el Bus
