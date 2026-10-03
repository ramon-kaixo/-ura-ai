<!-- Engineering Process v1.0 — PLAN CORRECTO (ejemplo para prueba conductual B2) -->

# PLAN EJEMPLO — Corrección bug en validador de email

## 1. ¿QUÉ QUIERO CONSEGUIR?
Corregir la validación de email en core/validators.py para que acepte dominios con guiones (ej. user@mi-dominio.com) que actualmente rechaza el regex.

## 2. ¿POR QUÉ?
- Usuario reportó: email test@sub-domain.example.com falla validación
- Regex actual: ^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$ — no permite guión en subdominio
- Impacto: 3 usuarios afectados en última semana (logs)

## 3. ¿QUÉ CONTEXTO EXISTE?
- Archivo: core/validators.py:42 función validar_email()
- Tests actuales: tests/unit/test_validators.py::test_email_valido (6 casos, todos pasan)
- No hay consumidores externos del validador (solo interno URA)

## 4. ¿QUÉ TIENE QUE HACER?
- Modificar regex para permitir guiones en parte de dominio (no al inicio/final)
- Añadir 3 tests: guión medio, guión inicio (debe fallar), guión final (debe fallar)
- Ejecutar suite completa

## 5. ¿QUÉ ES MÍNIMO?
1. Regex acepta user@sub-domain.com
2. Regex rechaza user@-dominio.com y user@dominio-.com
3. Tests existentes no regresan

## 6. ¿QUÉ ES CRÍTICO?
- No cambiar comportamiento para emails válidos actuales
- No introducir dependencias nuevas
- Compatibilidad hacia atrás total

## 7. CÓMO DEBE COMPORTARSE
validar_email(test@sub-domain.com) → True
validar_email(test@-dominio.com) → False
validar_email(test@dominio-.com) → False

## 8. QUÉ NO DEBE HACER
- No tocar otros validadores (URL, teléfono)
- No añadir librería externa (email-validator, etc.)
- No cambiar firma de función

## 9. QUÉ ESTÁ FUERA DE ALCANCE
- Validación DNS real (MX records)
- Internacionalización (IDN, Unicode)

## 10. CÓMO SE VALIDARÁ
- pytest tests/unit/test_validators.py -v — 9 tests pasan
- ruff check core/validators.py — 0 errores

## 11. CÓMO SE SABRÁ QUE ESTÁ TERMINADO
- 3 tests nuevos verdes + 6 existentes verdes
- Regex documentado en docstring con ejemplos
- Commit: fix(validators): permitir guiones en subdominio email
