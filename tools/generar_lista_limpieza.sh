#!/usr/bin/env bash
# Genera lista_limpieza.txt con los "restos de obra" SIN BORRAR nada.
# Requiere validación Face ID antes de eliminar (ver main_final.py -> handle_clean_safe).

set -u
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROOT="$SCRIPT_DIR"
OUT="$ROOT/lista_limpieza.txt"

{
  echo "# ============================================================"
  echo "# URA · LISTA DE LIMPIEZA (restos de obra)"
  echo "# Generada: $(date '+%Y-%m-%d %H:%M:%S')"
  echo "# ATENCIÓN: nada se ha borrado todavía."
  echo "# La eliminación requiere validación por Face ID."
  echo "# ============================================================"
  echo ""

  echo "## 1) Directorios __pycache__"
  find "$ROOT" -type d -name "__pycache__" 2>/dev/null
  echo ""

  echo "## 2) Archivos .pyc"
  find "$ROOT" -type f -name "*.pyc" 2>/dev/null
  echo ""

  echo "## 3) Archivos .DS_Store"
  find "$ROOT" -type f -name ".DS_Store" 2>/dev/null
  echo ""

  echo "## 4) Logs antiguos (>30 dias)"
  find "$ROOT" -type f \( -name "*.log" -o -name "*.log.*" \) -mtime +30 2>/dev/null
  echo ""

  echo "## 5) Backups comprimidos (>30 dias)"
  find "$ROOT" -type f \( -name "*.gz" -o -name "*.zip" -o -name "*.tar" \) -mtime +30 2>/dev/null
  echo ""

  echo "## 6) Temporales, swap y .bak"
  find "$ROOT" -type f \( -name "*.tmp" -o -name "*.temp" -o -name "*.swp" -o -name "*.bak" -o -name "*~" \) 2>/dev/null
  echo ""

  echo "## 7) Cachés de build / test"
  find "$ROOT" -type d \( -name "build" -o -name "dist" -o -name ".pytest_cache" -o -name ".mypy_cache" -o -name ".ruff_cache" \) 2>/dev/null
  echo ""

  echo "## 8) node_modules (si existieran)"
  find "$ROOT" -maxdepth 4 -type d -name "node_modules" 2>/dev/null
  echo ""

  echo "## 9) Archivos .orig / .rej / core dumps"
  find "$ROOT" -type f \( -name "*.orig" -o -name "*.rej" -o -name "core.*" \) 2>/dev/null
  echo ""

  echo "## 10) Programas/ejecutables desconocidos (revisar manualmente)"
  find "$ROOT" -maxdepth 2 -type f -perm +111 ! -name "*.sh" ! -name "*.py" ! -path "*/.*" 2>/dev/null | head -50
  echo ""

  echo "# ============================================================"
  echo "# RESUMEN"
  echo "# ============================================================"
  TOTAL=$(find "$ROOT" \( -name "__pycache__" -o -name "*.pyc" -o -name ".DS_Store" -o -name "*.tmp" -o -name "*.bak" -o -name "*~" \) 2>/dev/null | wc -l | tr -d ' ')
  SIZE=$(find "$ROOT" \( -name "__pycache__" -o -name "*.pyc" -o -name ".DS_Store" -o -name "*.tmp" -o -name "*.bak" -o -name "*~" \) -exec du -sk {} + 2>/dev/null | awk '{s+=$1} END {printf "%.1f MB", s/1024}')
  echo "# Candidatos totales (restos obvios): $TOTAL"
  echo "# Espacio liberable estimado: $SIZE"
} > "$OUT"

echo "Archivo generado: $OUT"
wc -l "$OUT"
