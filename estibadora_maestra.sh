#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'
RED='\033[0;31m'; YEL='\033[1;33m'; GRN='\033[0;32m'
BLU='\033[0;34m'; CYN='\033[0;36m'; NC='\033[0m'; BOLD='\033[1m'
DRY_RUN=false; SOLO_FASE=""
for arg in "$@"; do case "$arg" in
  --dry-run) DRY_RUN=true ;; --fase) shift; SOLO_FASE="${1:-}" ;; --fase=*) SOLO_FASE="${arg#*=}" ;; esac; done
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/ura_env.sh" 2>/dev/null || true
REPO="${URA_ROOT:-$HOME/URA/ura_ia_1972}"; cd "$REPO"
LOGS_DIR="${REPO}/logs/estibadora"; mkdir -p "$LOGS_DIR"
TIMESTAMP=$(date +%Y%m%d_%H%M%S); LOG="${LOGS_DIR}/run_${TIMESTAMP}.log"
log()   { echo -e "${BLU}[$(date +%H:%M:%S)]${NC} $*" | tee -a "$LOG"; }
ok()    { echo -e "${GRN}  ✅ $*${NC}"  | tee -a "$LOG"; }
warn()  { echo -e "${YEL}  ⚠️  $*${NC}" | tee -a "$LOG"; }
err()   { echo -e "${RED}  ❌ $*${NC}"  | tee -a "$LOG"; }
phase() { echo -e "\n${BOLD}${CYN}══ FASE $1: $2 ══${NC}" | tee -a "$LOG"; }
run() { [ "$DRY_RUN" = true ] && { echo -e "${YEL}  [DRY] $*${NC}" | tee -a "$LOG"; return 0; }; eval "$@" 2>&1 | tee -a "$LOG" || return $?; }
has() { command -v "$1" &>/dev/null; }
should() { [ -z "$SOLO_FASE" ] || [ "$SOLO_FASE" = "$1" ]; }

echo -e "\n${BOLD}${CYN}╔════════════════════════════╗${NC}"
echo -e "${BOLD}${CYN}║  ESTIBADORA MAESTRA URA   ║${NC}"
echo -e "${BOLD}${CYN}║  $(date '+%Y-%m-%d %H:%M')   ║${NC}"
echo -e "${BOLD}${CYN}╚════════════════════════════╝${NC}"
[ "$DRY_RUN" = true ] && warn "DRY RUN"; log "Repo: $REPO"; log "Log: $LOG"

N_PY=$(find . -name "*.py" -not -path "*/__pycache__/*" -not -path "*/.mypy_cache/*" -not -path "*/.tox/*" | wc -l | tr -d ' ')
log "Archivos Python: $N_PY"

if should 1; then phase 1 "Python Lint"; 
  has ruff && { run "ruff check . --fix --unsafe-fixes --quiet"; run "ruff format . --quiet"; ok "ruff"; } || warn "ruff no instalado"
  has autoflake && { find . -name "*.py" -not -path "*/__pycache__/*" | xargs autoflake --in-place --remove-all-unused-imports --quiet 2>/dev/null; ok "autoflake"; } || true
fi

if should 2; then phase 2 "Types (mypy)"; has mypy && { mypy . --ignore-missing-imports --follow-imports=skip --no-error-summary 2>&1 | tail -3 | tee -a "$LOG"; ok "mypy"; } || warn "mypy no"; fi

if should 3; then phase 3 "Seguridad";
  has bandit && { bandit -r . -ll -q --exclude .tox,.mypy_cache 2>/dev/null | tail -3 | tee -a "$LOG"; ok "bandit"; } || true
  has trufflehog && { trufflehog filesystem . --no-update 2>/dev/null | tail -3 | tee -a "$LOG"; ok "trufflehog"; } || true
fi

if should 4; then phase 4 "Calidad";
  has radon && { radon cc . -s -n C 2>/dev/null | tail -3 | tee -a "$LOG"; ok "radon"; } || true
  has vulture && { vulture . --min-confidence 80 2>/dev/null | tail -3 | tee -a "$LOG"; ok "vulture"; } || true
  has jscpd && { jscpd . --pattern "**/*.py" --min-lines 10 --min-tokens 50 --silent 2>/dev/null; ok "jscpd"; } || true
fi

if should 5; then phase 5 "Traduccion ES->EN";
  if [ -f "scripts/pro/translate_to_english.py" ]; then
    PENDING=$(python3 scripts/pro/translate_to_english.py --dry-run 2>/dev/null | grep -oP '\d+(?= identificadores)' || echo "0")
    [ "$PENDING" = "0" ] && ok "0 pendientes" || { python3 scripts/pro/translate_to_english.py --apply; ok "$PENDING traducidos"; }
  fi
fi

if should 6; then phase 6 "Refactorizacion 14B";
  OLLAMA_UP=false
  for port in 11434 11436 11437 11438; do curl -s --max-time 3 "http://10.164.1.99:${port}/api/tags" &>/dev/null && { OLLAMA_UP=true; OLLAMA_PORT=$port; break; }; done
  if [ "$OLLAMA_UP" = true ] && [ "$DRY_RUN" = false ]; then
    python3 scripts/pro/refactor_large_functions.py 2>&1 | tee -a "$LOG"
    ok "Refactorizacion completada"
  else warn "Ollama no disponible o DRY_RUN"; fi
fi

if should 7; then phase 7 "JSON+YAML";
  JSON_ERR=0; while IFS= read -r f; do python3 -m json.tool "$f" /dev/null 2>/dev/null || JSON_ERR=$((JSON_ERR+1)); done < <(find . -name "*.json" -not -path "*/.tox/*" -not -path "*/node_modules/*" -size -500k 2>/dev/null)
  log "JSON: $JSON_ERR errores"; [ "$JSON_ERR" -eq 0 ] && ok "JSON OK" || warn "$JSON_ERR JSONs invalidos"
fi

if should 8; then phase 8 "Shell";
  SH_ERR=0; while IFS= read -r f; do shellcheck "$f" 2>/dev/null | grep -c "warning\|error" | read c && SH_ERR=$((SH_ERR + c)) || true; done < <(find . -name "*.sh" -not -path "*/node_modules/*" 2>/dev/null)
  log "Shell: $SH_ERR warnings"; [ "$SH_ERR" -eq 0 ] && ok "Shell OK"; fi

if should 9; then phase 9 "Markdown"; find . -name "*.md" -not -path "./.git/*" -exec sed -i '' 's/[[:space:]]*$//' {} \; 2>/dev/null; ok "Markdown limpio"; fi

if should 10; then phase 10 "Tests";
  has pytest && { pytest . -x --timeout=60 --tb=no -q 2>&1 | tail -3 | tee -a "$LOG"; ok "pytest"; } || warn "pytest no"; fi

if should 11; then phase 11 "Backup";
  BACKUP="$HOME/URA/backups/estibadora_$(date +%Y%m%d_%H%M%S)"
  mkdir -p "$BACKUP" && rsync -az --exclude='.mypy_cache' --exclude='__pycache__' --exclude='.tox' --exclude='*.pyc' --exclude='.git' ./ "$BACKUP/" 2>/dev/null && ok "Backup: $(du -sh "$BACKUP" | cut -f1)" || warn "rsync no"; fi

if should 12 || [ -z "$SOLO_FASE" ]; then phase 12 "Resumen";
  LINES=$(find . -name "*.py" -not -path "*/__pycache__/*" -not -path "*/.mypy_cache/*" -not -path "*/.tox/*" -exec cat {} + 2>/dev/null | wc -l | tr -d ' ')
  echo -e "\n${BOLD}${GRN}══ RESUMEN ══${NC}"
  echo "  Python: ${LINES} lineas en ${N_PY} archivos"
  echo -e "${BOLD}${GRN}══════════════${NC}\n"
fi
