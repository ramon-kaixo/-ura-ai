# Sandbox 2 — Seguridad

**Función:** Validación y auditoría de seguridad
**Ubicación:** GX10 (Docker)
**Horario:** 06:00 y 00:00

## Herramientas
- `bandit` — Escaneo de vulnerabilidades en código Python
- `pip-audit` — Auditoría de dependencias Python
- `safety` — Verificación de CVEs en paquetes
- `scripts/verificar_permisos.sh` — Validación de permisos de archivos
- `scripts/validar_firmas.sh` — Verificación de firmas GPG

## Flujo de ejecución
1. Ejecutar bandit sobre todo el código URA
2. Ejecutar pip-audit sobre requirements.txt
3. Verificar permisos de archivos críticos (.env, claves SSH)
4. Registrar hallazgos en `auditoria/`
5. Si hay vulnerabilidades críticas → alerta Pushover

## Dependencias
- Docker con Python 3.12
- bandit, pip-audit, safety instalados
- Acceso al código URA (montado como volumen)
