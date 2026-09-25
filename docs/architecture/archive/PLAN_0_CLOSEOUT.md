# Closeout PLAN 0 — Infraestructura de Ingeniería para Agentes (v1.0)

**Fecha**: 2026-08-08
**Tarea**: TASK-20260808-016
**Plan**: `docs/architecture/PLAN_0_REVISADO.md` (v1.1, aprobado por Ramón)
**Tag**: v0.31.0-plan0
**Árbol final**: limpio

---

## 1. Resumen ejecutivo

Plan 0 implementado según §5 del plan revisado. La metodología universal de ingeniería ("un plan nunca se ejecuta sin análisis previo") está documentada, versionada, verificable y se entrega a todo agente OpenCode vía mecanismos nativos (AGENTS.md proyecto + AGENTS.md global + script de comprobación). Se reutilizó UDO para la maquinaria (reservas, gate F2.2, AUTO-REVISIÓN) — sin duplicar, sin máquina de estados nueva (lección F3).

## 2. Entregables

| Entregable | Ubicación | Estado |
|------------|-----------|--------|
| README | `docs/engineering/README.md` | ✅ |
| ENGINEERING_PROCESS v1.0 (10 obligaciones, clasificación, roles, trazabilidad, versionado) | `docs/engineering/ENGINEERING_PROCESS.md` | ✅ |
| PLAN_TEMPLATE (11 preguntas §50) | `docs/engineering/PLAN_TEMPLATE.md` | ✅ |
| PLAN_REVIEW_TEMPLATE (ANÁLISIS + veredicto GO/GO CON CAMBIOS/NO-GO + 9 preguntas) | `docs/engineering/PLAN_REVIEW_TEMPLATE.md` | ✅ |
| ROLE_MODEL | fusionado en ENGINEERING_PROCESS §9 | ✅ (cambio #2) |
| AGENTS.md puntero (§38) | `AGENTS.md` sección "Metodología Universal de Ingeniería" | ✅ |
| Copia de instalación (origen) | `deploy/engineering/AGENTS.md.global` | ✅ |
| Copia global instalada | `~/.config/opencode/AGENTS.md` | ⚠️ PENDIENTE (rootfs ro — ver §6) |
| Script de comprobación | `scripts/pro/ura-engineering-check` (--install/--fix/check) | ✅ |
| Tests casos 1-6 (§44) | `tests/engineering/test_engineering.sh` — 13/13 OK | ✅ |
| Casos 7-10 (§44) | reutilizan `tests/udo/test_udo.sh` — 30/30 OK | ✅ |
| Referencias CI colgantes | `.github/tests-ci-exclude.txt` + `.github/CI_POLICY.md` creados | ✅ |
| Auditoría previa | `docs/architecture/PLAN_0_AUDITORIA.md` (GO CON CAMBIOS) | ✅ |
| Plan revisado aprobado | `docs/architecture/PLAN_0_REVISADO.md` (v1.1) | ✅ |
| Referencia maestra | `docs/architecture/PLAN_0.md` (v1.0 original) | ✅ |

## 3. Cumplimiento del §48 (criterio de cierre)

| Criterio | Evidencia |
|----------|-----------|
| docs/engineering/ existe (4 archivos) con versión en cabecera | `ENGINEERING_PROCESS.md` → `<!-- Engineering Process v1.0 -->` ✅ |
| AGENTS.md global instalado + checksum | ⚠️ PENDIENTE rootfs ro (comando §6; tras instalación, `ura-engineering-check` verifica) |
| AGENTS.md del repo referencia metodología (puntero) | ✅ sección "Metodología Universal de Ingeniería" |
| ura-engineering-check existe, ejecutable, devuelve OK | ✅ (depende del punto anterior para OK completo) |
| 10 casos de prueba documentados y ejecutados | ✅ 1-6: test_engineering.sh 13/13; 7-10: test_udo.sh 30/30 |
| Evidencia en expedientes UDO (análisis, clasificación, veredicto) | ✅ TASK-015 (auditoría: GO CON CAMBIOS + clasificaciones) y TASK-016 (implementación) |
| Auditoría final adversa + closeout + tag | ✅ este documento + tag `v0.31.0-plan0` |

## 4. Auditoría final (autoaplicación §45)

Se aplicó la metodología al propio Plan 0 (TASK-015): análisis previo, clasificación de descubrimientos (OBLIGATORIO/NECESARIO/MEJORA/DESCUBRIMIENTO/PENDIENTE/FUERA DE ALCANCE), veredicto GO CON CAMBIOS, plan corregido v1.1, y tras aprobación humana, implementación (TASK-016). Trazabilidad completa en los expedientes.

### Hallazgos durante la implementación

| Hallazgo | Clase | Resolución |
|----------|-------|------------|
| Rootfs `/` montado ro (F14-F01) impide instalar AGENTS.md global | PENDIENTE | Comando §6 para Ramón (sudo) |
| `mcp.openclaw` en config global de opencode | NECESARIO (limpieza) | PENDIENTE — requiere rootfs rw + editar `~/.config/opencode/opencode.json` |
| `ReadWritePaths=.openclaw` en hardening.conf del servicio | NECESARIO (limpieza) | PENDIENTE — requiere sudo Ramón |
| Residuos `~/.opencode/opencode.json` + package.json (1.15.12) | MEJORA | PENDIENTE — verificar antes de borrar |
| Secretos en `.bashrc` (TAILSCALE_AUTH_KEY, HCLOUD_TOKEN) | DESCUBRIMIENTO | FUERA DE ALCANCE — tarea de seguridad aparte (§53) |
| Watchdog stub (`exit 0`) | DESCUBRIMIENTO | Documentado: desactivación deliberada; solo lo usa plist macOS |

## 5. Validación

| Suite | Resultado |
|-------|-----------|
| `tests/engineering/test_engineering.sh` | 13 OK, 0 FAIL |
| `tests/udo/test_udo.sh` | 30 OK, 0 FAIL |
| `make validate` | 5251 passed, 0 regresiones (baseline sin cambios de código) |
| Ruff | sin cambios de código Python — sin impacto |

## 6. Pendientes (no bloqueantes, requieren sudo/rootfs rw)

```bash
# 1. Instalar la metodología global (Web + Terminal la reciben)
sudo mount -o remount,rw / && cp /home/ramon/URA/ura_ia_1972/deploy/engineering/AGENTS.md.global /home/ramon/.config/opencode/AGENTS.md && sudo mount -o remount,ro /
# 2. Verificar instalación
scripts/pro/ura-engineering-check
# 3. Limpieza restos (opcional, mismo remount)
#    - eliminar bloque "openclaw" de ~/.config/opencode/opencode.json
#    - eliminar ReadWritePaths=.../.openclaw de /etc/systemd/system/opencode.service.d/hardening.conf
# 4. (Tarea aparte) migrar TAILSCALE_AUTH_KEY/HCLOUD_TOKEN de ~/.bashrc a /etc/ura/secrets.env + rotar
```

## 7. Cierre formal

- **Plan 0 implementado y validado** (salvo instalación global pendiente de rootfs rw — reversible, no bloqueante).
- **Reversible**: `rm -rf docs/engineering/ deploy/engineering/ tests/engineering/ scripts/pro/ura-engineering-check` + revertir sección de AGENTS.md + `rm ~/.config/opencode/AGENTS.md` deja URA intacta.
- **Regla de no regresión**: 0 regresiones funcionales (5251 tests baseline).
- **Tag**: `v0.31.0-plan0` creado.
- **Secuencia**: Plan 0 cierra → F4 y F5 podrán abrirse con la nueva metodología (análisis previo obligatorio).

---

*Closeout elaborado por TERM (TASK-20260808-016). Auditoría previa: TASK-20260808-015. Veredicto previo: GO CON CAMBIOS → aprobado por Ramón → implementado.*
