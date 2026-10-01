---
name: alarma-coverage
description: Analiza alertas de cobertura y propone parches quirúrgicos a tests
---

# Alarma Coverage Pipeline

Analiza alertas del pipeline de cobertura determinista de URA.

## Uso
- Lee `.nervioso/llm_proposal.json` y `.nervioso/flaky_tests.json`
- Para cada módulo en alerta: analiza trazabilidad, identifica causa raíz (mutante superviviente, rama sin cubrir, flaky)
- Propón parche QUIRÚRGICO SOLO sobre archivo de test existente
- Guarda propuesta en `.nervioso/llm_proposal.json` con: modulo, timestamp, propuesta, veredicto, intento_numero
