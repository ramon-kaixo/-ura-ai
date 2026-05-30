# Manual Test Scripts

**Fecha:** 2026-05-11  
**Propósito:** Scripts de prueba manuales para verificar funcionalidades específicas

## Descripción

Esta carpeta contiene scripts de prueba manuales que **no están integrados en pytest** ni en el sistema de tests automatizados. Son scripts de uso manual para verificar funcionalidades específicas del sistema URA.

## Scripts Disponibles

### 1. test_ollama_integration.py
**Tipo:** Test manual de integración  
**Propósito:** Test de Integración Ollama Directo en URA OpenClaw client  
**Ejecución:**
```bash
python3 scripts/manual_tests/test_ollama_integration.py
```
**Descripción:** Detecta disponibilidad de OpenClaw, crea cliente y prueba integración directa con Ollama.

---

### 2. test_training_fix.py
**Tipo:** Test manual de entrenamiento  
**Propósito:** Prueba de TrainingOrchestrator después de las correcciones  
**Ejecución:**
```bash
python3 scripts/manual_tests/test_training_fix.py
```
**Descripción:** Instancia TrainingOrchestrator(max_queries=10, concurrency=2), carga semillas del seed_pipeline, corre night_training(max_queries=10) y muestra self.stats.

---

### 3. bench_models.py
**Tipo:** Benchmark  
**Propósito:** Benchmark completo de modelos para URA  
**Ejecución:**
```bash
python3 scripts/manual_tests/bench_models.py
```
**Descripción:** Ejecuta benchmark de modelos y guarda resultado en `/tmp/ura_bench.log`.

---

### 4. test_redis_idempotency.py
**Tipo:** Test manual  
**Propósito:** Test Redis Idempotency - Prueba de idempotencia con Redis  
**Ejecución:**
```bash
python3 scripts/manual_tests/test_redis_idempotency.py
```
**Descripción:** Prueba idempotencia con Redis - crea y recupera claves, verifica funcionamiento del sistema de idempotencia.

---

### 5. test_slack_idempotency.py
**Tipo:** Smoke test manual  
**Propósito:** Smoke Test: Redis + Slack Idempotency  
**Ejecución:**
```bash
python3 scripts/manual_tests/test_slack_idempotency.py
```
**Descripción:** Verifica que la idempotencia está funcionando correctamente con Slack - smoke test integrado.

---

## Notas Importantes

- Estos scripts **no son tests automatizados** de pytest/unittest
- No están integrados en CI/CD ni en qa_check.sh
- Se ejecutan manualmente según necesidad
- Pueden requerir configuración previa (Redis, Ollama, Slack tokens)
- Se movieron desde la raíz del proyecto el 2026-05-11 para organizar mejor el códigobase

## Requisitos Previos

- Python 3.12+
- Redis (para test_redis_idempotency.py y test_slack_idempotency.py)
- Ollama (para test_ollama_integration.py)
- Configuración de Slack tokens (para test_slack_idempotency.py)
- Entorno virtual activo: `source .venv/bin/activate`
