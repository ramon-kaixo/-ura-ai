# Limpieza URA_App — Ejecutar en Windsurf

> Abrir esta carpeta en Windsurf y ejecutar cada sección en orden.
> Total a liberar: ~5 GB

---

## PASO 1 — Backups redundantes en Desktop (fuera del proyecto)

Eliminar estas carpetas/archivos desde la terminal:

```bash
rm -rf ~/Desktop/URA_DNA
rm -rf ~/Desktop/URA_Backups
rm -rf ~/Desktop/URA_App_BACKUP
rm -rf ~/Desktop/URA_App_backup_20260426_181044
rm -rf ~/Desktop/URA_App_backup_20260426_181054
rm -rf ~/Desktop/URA_App_v2
rm -f  ~/Desktop/URA_Clean_Backup_20260426_062645.zip
rm -f  ~/Desktop/URA_App_backup_20260424_161524.tar.gz
```

**Libera ~4.9 GB**

---

## PASO 2 — Archivos backup dentro del proyecto

```bash
cd ~/Desktop/URA_App

rm -f main_final.py.backup
rm -f main_final.py.bak
rm -f main_final.py.bak3
rm -f main_final.py.clean_backup
rm -f mypy.ini.backup
rm -f connectors/ollama_connector.py.backup
rm -f core/react_engine.py.backup
rm -f core/right_panel.py.backup
```

---

## PASO 3 — Archivos corruptos (swap del editor)

```bash
cd ~/Desktop/URA_App

rm -f "core/.!83215!agente_policia_v2.py"
rm -f "core/__pycache__/.!83215!agente_policia_v2.cpython-313.pyc"
rm -f "core/__pycache__/.!83215!agente_policia_v2.cpython-312.pyc"
rm -f "core/__pycache__/.!83215!agente_policia_v2.cpython-314.pyc"
```

---

## PASO 4 — Scripts de prueba y archivos huérfanos en raíz

```bash
cd ~/Desktop/URA_App

rm -f chat_minimo.py
rm -f chat_test.py
rm -f prueba_ura.py
rm -f install_todo_auto.py
rm -f api_gateway.py
rm -f api_trazabilidad.py
```

> `api_gateway.py` está duplicado en `gateway/api_gateway.py` — se conserva esa versión.

---

## PASO 5 — Limpiar cache de Python

```bash
cd ~/Desktop/URA_App
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
find . -name "*.pyc" -delete 2>/dev/null
```

---

## VERIFICACIÓN FINAL

```bash
du -sh ~/Desktop/URA_App
ls ~/Desktop/URA_App/*.bak* ~/Desktop/URA_App/*.backup 2>/dev/null || echo "OK - sin backups"
ls ~/Desktop/URA_DNA ~/Desktop/URA_Backups 2>/dev/null || echo "OK - backups externos eliminados"
```

---

## LO QUE NO SE TOCA

| Directorio/Archivo | Razón |
|--------------------|-------|
| `dashboard/` | Tiene `app.py` + templates reales |
| `gateway/` | Tiene `api_gateway.py` real |
| `monitoring/` | Tiene configs de Grafana/Prometheus |
| `cloud_backup.py` | Es un módulo activo (no es un backup) |
| `URA_App` completo | El proyecto real |

---

## SIGUIENTE PASO (después de limpiar)

1. `git init` en `~/Desktop/URA_App`
2. Crear `.gitignore` con `__pycache__/`, `*.pyc`, `*.bak`, `*.backup`
3. Primer commit limpio
