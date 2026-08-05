# Criterios de decisión — 2026-08-05

## Cuándo ACEPTAR un cambio

1. make validate pasa (0 fallos no-flaky)
2. 0 errores de collection
3. git status limpio después del commit
4. Tests nuevos acompañan a código nuevo
5. No se toca core/, motor/, knowledge/ sin necesidad
6. Documentado (docstring o ADR si es decisión)

## Cuándo RECHAZAR

1. make validate falla con algo no-flaky
2. Errores de collection
3. Código sin tests
4. Auto-commit activado sin aprobación humana
5. Cambios en runner.py sin test de regresión

## Cuándo PARAR y preguntar

1. Un módulo lleva más del doble del tiempo estimado
2. Se descubre un problema que requiere sudo (rootfs RO)
3. El otro agente sobrescribe el archivo en el que se trabaja (commit inmediato + pausa)
4. Un test falla en suite pero pasa aislado y no se entiende la causa
5. Se necesita modificar core/, motor/, knowledge/ para un fix

## Prioridades

1. Estabilidad de la suite (0 errores de collection)
2. Ciclo tuneladora → reporte → supervisor → alerta
3. Automatización sin romper lo manual
4. Documentación de decisiones (ADRs)
