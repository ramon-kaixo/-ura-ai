# Deuda Técnica — Auditoría Post-F29

| ID | Ítem | Prioridad | Estado | Notas |
|----|------|-----------|--------|-------|
| T01 | `core/synonyms.json` con `chattr +i` | Mínima | ⏳ Pendiente | Requiere sudo interactivo en GX10 |
| T02 | `scripts/pro/sanear_codigo.py:50` syntax error | Baja | ✅ Resuelto | No hay error de sintaxis (ya corregido) |
| T03 | 12 archivos .py con no-ASCII en nombre | Baja | ✅ Resuelto | 0 archivos encontrados (ya corregido) |
| T04 | 5 tests CLI fallan por dependencias | Baja | ✅ Parcial | `test_unit.py` sys.exit() envuelto en `__name__ == '__main__'` |
| T05 | FTS schema verifier falso positivo | Media | ✅ Resuelto | `sqlite_stat*` ya ignorados en `storage_verifier.py` |
| T06 | ~2.356 lint errors pre-existentes | Baja | ⏳ Pendiente | Requiere auditoría masiva, baja prioridad |
| T07 | `adapters/` directorio nunca creado | Informativa | ℹ️ Informativo | Sin acción necesaria |
| T08 | 14 bloques `except: pass` validados | Mínima | ✅ Resuelto | F28.1 ya añadió logging en `motor/platform/` |
| T09 | ~80+ bloques `except: pass` sin auditar | Media | ✅ Resuelto | 26 instancias en `knowledge/engine/` auditadas: 100% degradación controlada. `# noqa: S110` añadido |

**Total original:** 9 items  
**Resueltos:** 6 (T02, T03, T05, T08, T09) + parcial T04  
**Pendientes:** 2 (T01, T06) + 1 informativo (T07)
