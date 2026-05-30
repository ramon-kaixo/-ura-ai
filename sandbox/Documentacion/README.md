# Sandbox 4 — Documentación

**Función:** Manuales e informes del ecosistema
**Ubicación:** Mac (local)
**Horario:** 12:00 y 00:00

## Herramientas
- `scripts/generar_manuales.py` — Generación de manuales de uso
- `scripts/informe_estado.py` — Informe de estado del sistema
- `scripts/registrar_cambios.py` — Documentación automática de cambios
- `scripts/actualizar_readme.py` — Actualización del README principal
- `scripts/generar_metricas.py` — Métricas de uso y rendimiento

## Flujo de ejecución
1. Recopilar métricas de observability y health_monitor
2. Generar informe de estado (CPU, RAM, disco, agentes activos)
3. Registrar cambios detectados en el código (git diff)
4. Actualizar documentación automáticamente
5. Archivar informe en `informes/informe_YYYYMMDD.md`

## Dependencias
- Git para detección de cambios
- Acceso a logs de observability
- Python venv del proyecto
