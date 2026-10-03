<!-- Engineering Process v1.0 — PLAN INCOMPLETO (ejemplo para prueba conductual B2) -->

# PLAN EJEMPLO — Refactor módulo de autenticación

## 1. ¿QUÉ QUIERO CONSEGUIR?
Refactorizar el módulo de autenticación para que sea más limpio.

## 2. ¿POR QUÉ?
El código actual es difícil de mantener.

## 3. ¿QUÉ CONTEXTO EXISTE?
- Archivo: core/auth.py (500 líneas)
- Usa JWT para tokens

## 4. ¿QUÉ TIENE QUE HACER?
- Dividir en varios archivos
- Mejorar nombres de funciones

## 5. ¿QUÉ ES MÍNIMO?
- Código más limpio

## 6. QUÉ ES CRÍTICO?
- No romper login

## 7. CÓMO DEBE COMPORTARSE
Login sigue funcionando.

## 8. QUÉ NO DEBE HACER
- No cambiar API pública

## 9. QUÉ ESTÁ FUERA DE ALCANCE
- OAuth2

## 10. CÓMO SE VALIDARÁ
- Tests pasan

## 11. CÓMO SE SABRÁ QUE ESTÁ TERMINADO
- Código refactorizado

# FALTAN SECCIONES: QUÉ ES CRÍTICO incompleto, sin PUNTOS CRÍTICOS/INVARIANTES detallados,
# sin COMPORTAMIENTO ESPERADO específico, sin QUÉ NO DEBE HACER exhaustivo,
# sin criterios de validación medibles, sin criterios de cierre objetivos.
