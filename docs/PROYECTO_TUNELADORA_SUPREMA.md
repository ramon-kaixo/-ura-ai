# 🏗️ PROYECTO: TUNELADORA SUPREMA — Fusión Definitiva

**Versión:** 2.0  
**Fecha:** 2026-06-03  
**Estado:** Propuesta Formal  
**Consultores Expertos Solicitados:** Sistemas de Revisión de Código, Ingeniería de Refactorización Automática

---

## 📋 Resumen Ejecutivo

Se fusionan **todas las tuneladoras existentes** (10 scripts) en un **único orquestador** con procesos jerarquizados por frecuencia temporal. El sistema gestiona de forma autónoma la salud, refactorización, mejora y backup del ecosistema URA en GX10.

---

## 🔍 Inventario de Tuneladoras Existentes (10 scripts)

| # | Script | Propósito | Frecuencia actual |
|---|--------|-----------|-------------------|
| 1 | `tuneladora.sh` (root) | 6 fases unificadas | Cada 6h (timer) |
| 2 | `tuneladora_mantenimiento.sh` | Mantenimiento sistema | Manual / timer |
| 3 | `tuneladora_pro.sh` | Pro en paralelo | Manual |
| 4 | `tuneladora_mejora.sh` | Mejora continua (sandbox) | Manual |
| 5 | `tuneladora_v3.sh` | 14 fases (versión anterior) | Obsoleto |
| 6 | `tuneladora_master.py` | Orquestador Python AEA | Manual |
| 7 | `tuneladora_repair.sh` | Auto-reparación de incidencias | Bajo demanda |
| 8 | `scripts/pro/tuneladora.sh` | Sub-fase de mantenimiento | Parte de #1 |
| 9 | `scripts/pro/tuneladora_mantenimiento.sh` | Sub-fase mantenimiento | Parte de #1 |
| 10 | `scripts/pro/tuneladora_mejora.sh` | Sub-fase mejora sandbox | Parte de #1 |

---

## 🏛️ Arquitectura — Jerarquía Temporal

### Cada 1 Hora — Health Check

```
1. RAM, CPU, zombies, procesos clave
2. Model Router heartbeat (puerto 11435)
3. Log rotación si >100MB
```

### Cada 6 Horas (00:00, 06:00, 12:00, 18:00) — 5 Rodillos

```
RODILLO 1: DIAGNÓSTICO
├── Ruff fix completo (F841, F401, F811)
├── Poda Mecánica → mapa cromático 🔴🟢
├── Test unitarios (127) + OpenClaw (12)
└── F821 count vs baseline

RODILLO 2: REFACTORIZACIÓN
├── deepseek-coder:6.7b (4 workers, ~25s/función)
├── Fallback qwen2.5-coder:14b (solo errores)
├── Compactadora Cromática
├── Auto-Reglas (reparación determinista)
└── 10 Inspectores (120 checks)

RODILLO 3: AUDITORÍA MODELOS
├── Verificar Ollama + modelos disponibles
├── Test inferencia rápida
└── Model Router health + métricas

RODILLO 4: MEJORA CONTINUA
├── Sandbox Docker (ruff + pytest + bandit)
├── Watermark Aggregator
├── Generar reglas auto desde patrones
└── Detectar patrones sistémicos (≥3 ciclos)

RODILLO 5: BACKUP + REPORTE
├── Snapshot .nervioso/ + configs
├── Backup a /tmp/backups/
├── Reporte JSON a docs/pro/reports/
└── Delta snapshot para próximo ciclo
```

### Cada 24 Horas (03:00) — 4 Rodillos

```
RODILLO 6: MANTENIMIENTO PROFUNDO
├── Docker system prune -f --volumes
├── Pip cache purge
├── Logs rotación + compresión
├── __pycache__ + .mypy_cache cleanup
└── Paquetes APT desactualizados

RODILLO 7: BACKUP COMPLETO
├── Backup a Mac (rsync)
├── Backup a /tmp/ura_backups/
├── Tar.gz del repo (excluyendo .venv, .git)
├── Backup de configs systemd
└── Backup de watermarks + reglas auto

RODILLO 8: MÉTRICAS + REPORTE DIARIO
├── F821 vs baseline (314)
├── Funciones grandes restantes (>80 líneas)
├── Tiempo total vs estimado
├── Errores vs éxito rate
└── Reporte markdown a docs/pro/reports/

RODILLO 9: AUTO-LIMPIEZA DE APRENDIZAJE
├── Watermarks reparados >7 días → eliminar
├── Reglas con confianza <0.3 → eliminar
├── Patrones sistémicos resueltos → archivar
└── Recalcular baseline F821
```

### Bajo Demanda — 3 Rodillos

```
RODILLO 10: REPARACIÓN DE EMERGENCIA
├── tuneladora_repair.sh (zombies, RAM, servicios)
├── Model Router restart si caído
├── Rollback a último snapshot si crítico
└── Alerta vía SNC si no se puede reparar

RODILLO 11: REFACTORIZACIÓN EXPLÍCITA
└── Lanzar refactor con parámetros específicos

RODILLO 12: DASHBOARD (siempre activo)
├── Métricas en http://10.164.1.99:11435/metrics
├── Estado en .nervioso/estado.json
└── Logs en /opt/ura/logs/tuneladora_suprema/
```

---

## 🧠 Consultoría de Expertos Solicitada

### Perfiles

| Perfil | Experiencia | Evaluará |
|--------|-------------|----------|
| **Ingeniero de Refactorización Automática** | Google Kythe, Uber Piranha, Meta codemod | Pipeline cascada 6.7B→14B, tasa éxito, tiempos |
| **Arquitecto de Mantenimiento Predictivo** | SonarQube, CodeClimate, Grafana | Alertas tempranas, detección degradación |
| **Experto en Orquestación Temporal** | systemd timers, Airflow, Prefect | Jerarquía temporal, priorización |
| **Especialista en Auto-Aprendizaje** | Snorkel, Stanford PLSE, active learning | Bucle watermarks→reglas, confianza, olvido |

### Preguntas para los Expertos

```
1. ¿La jerarquía temporal (1h/6h/24h/bajo demanda) es óptima?
2. ¿El pipeline cascada (6.7B → fallback 14B → auto_reglas) es óptimo?
3. ¿El sistema de confianza (0.5+ activas, -0.2 por fallo) es adecuado?
4. ¿Sistema de versionado de reglas con rollback?
5. ¿Métricas adicionales para detectar degradación temprana?
6. ¿Umbral de 3 ciclos para patrones sistémicos es correcto?
```

---

## ⚙️ Configuración

```json
{
  "frecuencias": {
    "health_check_minutos": 60,
    "ciclo_completo_horas": 6,
    "mantenimiento_profundo_horas": 24,
    "hora_mantenimiento": "03:00"
  },
  "rodillos": {
    "1_diagnostico": { "timeout": 300 },
    "2_refactor": { "timeout": 3600 },
    "3_auditoria_modelos": { "timeout": 120 },
    "4_mejora_continua": { "timeout": 600 },
    "5_backup_reporte": { "timeout": 300 },
    "6_mantenimiento": { "timeout": 600 },
    "7_backup_completo": { "timeout": 900 },
    "8_metricas_diarias": { "timeout": 120 },
    "9_auto_limpieza": { "timeout": 60 },
    "10_reparacion_emergencia": { "timeout": 300 },
    "11_refactor_explicito": { "timeout": 7200 },
    "12_dashboard": { "timeout": 0 }
  },
  "modelos": {
    "refactor_principal": "deepseek-coder:6.7b",
    "refactor_fallback": "qwen2.5-coder:14b",
    "workers": 4,
    "monster_threshold": 80
  }
}
```

---

## 📊 Métricas de Éxito

| Métrica | Objetivo | Estado hoy |
|---------|----------|-----------|
| F821 total | <200 | 314 |
| Funciones >80 líneas | <50 | 107 |
| Tiempo ciclo completo | <30 min | ~25 min |
| Tasa éxito refactor | >60% | 62.5% (deepseek) |
| RAM estable | <90GB | 73GB |
| Zombies | 0 | 0 ✅ |
| Reglas auto aprendidas | >5 activas | 9 built-in |

---

## ✅ Plan de Implementación

| Fase | Duración | Acciones |
|------|----------|---------|
| 1. Fusión | Día 1 | Crear tuneladora_suprema.py, migrar 10 scripts, timers |
| 2. Validación | Días 2-3 | Ciclo manual, verificar métricas, ajustar, consultar expertos |
| 3. Producción | Día 4+ | Timers automáticos, monitoreo 1 semana, ajustes finales |

---

*Documento permanente. No eliminar. Actualizar solo con consentimiento del Comité de los Cuatro Expertos.*
