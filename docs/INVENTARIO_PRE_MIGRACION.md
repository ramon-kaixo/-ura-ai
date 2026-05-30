# Inventario Pre-Migración - Mac

**Fecha:** 2026-05-11  
**Objetivo:** Documentar estado actual del Mac antes de migración a GX10

## 1. Servicios Docker Activos

**Estado:** Docker daemon no está corriendo

```
Cannot connect to the Docker daemon at unix:///Users/ramonesnaola/.docker/run/docker.sock
```

## 2. Puertos en Uso

| Servicio | Puerto | Estado |
|----------|--------|--------|
| Redis | 6379 | LISTEN (127.0.0.1, [::1]) |
| PostgreSQL | 5432 | LISTEN (127.0.0.1, [::1]) |
| Ollama | 11434 | LISTEN (127.0.0.1) |
| nginx | 8080, 8090, 8091, 8888 | LISTEN |
| ControlCenter | 5000, 7000 | LISTEN |
| Node | 18789, 18791 | LISTEN (127.0.0.1) |
| Windsurf | 64116 | LISTEN (127.0.0.1) |
| Language Server | 64126, 64133 | LISTEN (127.0.0.1) |
| IPNExtension | 42849, 34731 | LISTEN |
| Python | 5051 | LISTEN (127.0.0.1) |
| OpenCode | 60749, 60696 | LISTEN (127.0.0.1) |

## 3. Modelos Ollama Instalados

| Modelo | ID | Tamaño | Modificado |
|--------|-----|--------|-----------|
| mxbai-embed-large:latest | 468836162de7 | 669 MB | hace 3 semanas |

## 4. Agentes en /agents

**Total:** 82 archivos .py

Lista completa:
- agente_administrativo_contable.py
- agente_archivist.py
- agente_arquitectura.py
- agente_asesor.py
- agente_backup.py
- agente_banco.py
- agente_biblioteca.py
- agente_camaras.py
- agente_cocina_espanola.py
- agente_cocina_italiana.py
- agente_cocina_mexicana.py
- agente_cocina_navarra_temporada.py
- agente_cocina_peruana.py
- agente_conciencia.py
- agente_conectividad.py
- agente_contabilidad.py
- agente_conversacion.py
- agente_email.py
- agente_facturas.py
- agente_gastronomo_musica.py
- agente_gobierno.py
- agente_gui.py
- agente_instalador.py
- agente_investigador_ia.py
- agente_juridico.py
- agente_laboral.py
- agente_lenguaje.py
- agente_lenguaje_escribiente.py
- agente_lenguaje_tecnico.py
- agente_librarian.py
- agente_logger.py
- agente_marketing.py
- agente_marketing_temporada_navarra.py
- agente_media_recetas.py
- agente_memoria.py
- agente_modelos.py
- agente_notificaciones.py
- agente_opencode.py
- agente_operativo_hardware.py
- agente_orquestador_documentacion.py
- agente_orquestador_recetas.py
- agente_policia_v2.py
- agente_programador.py
- agente_red.py
- agente_red_telefonia.py
- agente_rendimiento.py
- agente_reparador.py
- agente_revisor.py
- agente_rrhh.py
- agente_scheduler.py
- agente_seguridad.py
- agente_sistemas.py
- agente_supervisor.py
- agente_tailscale.py
- agente_telegram_dam.py
- agente_tendencias_pamplona.py
- agente_verificador.py
- agente_video.py
- agente_vision.py
- agente_vocabulario.py
- agente_vocabulario_bar.py
- agente_vocabulario_codigo.py
- agente_vocabulario_financiero.py
- agente_vocabulario_gastronomico.py
- agente_vocabulario_legal.py
- agente_vocabulario_tecnico.py
- agentes_busqueda.py
- bibliotecario_pasillo.py
- clasificador.py
- cocina_agent.py
- cocina_internacional_agent.py
- contabilidad_agent.py
- doble_verificacion.py
- guardian_residente.py
- leyes_agent.py
- marketing_agent.py
- motor_autorizacion_dual.py
- notificador_dam.py
- recetas_con_media.py
- registry.py
- rrhh_camaras_agent.py
- servidor_validacion.py

## 5. Bases de Datos y Tamaños

| Archivo | Tamaño |
|---------|--------|
| benchmark_questions.json | 4.0K |
| calendario_navarra.json | 4.0K |
| email_session | 0B |
| error_knowledge.json | 4.0K |
| gastronomia/ | 16K |
| instagram_session | 0B |
| musica/ | 16K |
| n8n_workflow_template.json | 4.0K |
| payment_audit.jsonl | 4.0K |
| telegram_session | 0B |
| whatsapp_session | 348K |

## 6. Archivos .env Presentes

- `/Users/ramonesnaola/URA/ura_ia_1972/.env` (valores sensibles no mostrados)
- `/Users/ramonesnaola/URA/ura_ia_1972/.env.example`
- `/Users/ramonesnaola/Desktop/URA_App/.env` (valores sensibles no mostrados)

## 7. Tamaño Total del Proyecto

- **URA_App:** 32K (solo contiene .env, centro_mando.html y docs/)
- **ura_ia_1972:** 3.3G (proyecto principal)

## 8. Versión Python

**Versión:** Python 3.12.0  
**Ubicación:** /Users/ramonesnaola/URA/ura_ia_1972/.venv/bin/python

## Resumen

- **Docker:** No está corriendo
- **Ollama:** 1 modelo instalado (669 MB)
- **Agentes:** 82 archivos Python
- **Bases de datos:** PostgreSQL en puerto 5432, Redis en 6379
- **Python:** 3.12.0
- **Puertos críticos:** 5432 (PostgreSQL), 6379 (Redis), 11434 (Ollama)
