#!/usr/bin/env bash
# estibadora_auditor.sh — Auditor e instalador automático de SOFTWARE DETERMINISTA
# Compatible con bash 3.x (macOS)
set -euo pipefail

REPO="${REPO:-$PWD}"; AUTO_YES=0; DRY_RUN=0; RECOMMEND_ALL=0
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo) REPO="$2"; shift 2 ;; --yes|-y) AUTO_YES=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;; --all) RECOMMEND_ALL=1; shift ;;
    -h|--help) head -20 "$0"; exit 0 ;; *) echo "? $1"; exit 1 ;;
  esac
done

LOGS_DIR="${REPO}/.auditor_logs"; mkdir -p "$LOGS_DIR"
C_B=''; C_G=''; C_Y=''; C_R=''; C_C=''; C_RESET=''
[[ -t 1 ]] && { C_B=$'\033[1m'; C_G=$'\033[32m'; C_Y=$'\033[33m'; C_R=$'\033[31m'; C_C=$'\033[36m'; C_RESET=$'\033[0m'; }
hdr()  { echo -e "\n${C_B}${C_C}== $* ==${C_RESET}"; }
ok()   { echo -e "  ${C_G}✓${C_RESET} $*"; }
miss() { echo -e "  ${C_Y}•${C_RESET} $*"; }
warn() { echo -e "  ${C_R}!${C_RESET} $*"; }
info() { echo -e "  $*"; }
have() { command -v "$1" >/dev/null 2>&1; }

HAS_PIPX=0; HAS_PIP=0; HAS_NPM=0; HAS_APT=0; HAS_CARGO=0; HAS_SUDO=0
have pipx  && HAS_PIPX=1; have pip3 && HAS_PIP=1; have pip && HAS_PIP=1
have npm   && HAS_NPM=1; have apt-get && HAS_APT=1; have cargo && HAS_CARGO=1
{ [[ $EUID -eq 0 ]] || have sudo; } && HAS_SUDO=1

# Catalogo: key|bin|install_method:pkg|lang|ram|desc
# Indices: 0=key 1=bin 2=install 3=lang 4=ram 5=desc
CATALOG=(
  "ruff|ruff|pipx:ruff|python|ligera|Linter+formateador Rust"
  "autoflake|autoflake|pipx:autoflake|python|ligera|Elimina imports no usados"
  "vulture|vulture|pipx:vulture|python|ligera|Detecta codigo muerto"
  "mypy|mypy|pipx:mypy|python|media|Type checker"
  "bandit|bandit|pipx:bandit|python|ligera|Seguridad Python"
  "radon|radon|pipx:radon|python|ligera|Complejidad ciclomatica"
  "xenon|xenon|pipx:xenon|python|ligera|Umbral CI radon"
  "semgrep|semgrep|pipx:semgrep|multi|media|SAST multi-lenguaje"
  "jscpd|jscpd|npm:jscpd|multi|ligera|Clones de codigo"
  "tokei|tokei|cargo:tokei|multi|ligera|Contador lineas Rust"
  "ripgrep|rg|apt:ripgrep|multi|ligera|Busqueda rapida"
  "shellcheck|shellcheck|apt:shellcheck|shell|ligera|Check scripts Bash"
  "shfmt|shfmt|apt:shfmt|shell|ligera|Formato Bash"
  "jq|jq|apt:jq|data|ligera|Validador JSON"
  "yq|yq|pipx:yq|data|ligera|Validador YAML"
  "pre-commit|pre-commit|pipx:pre-commit|multi|ligera|Hooks git"
  "pip-audit|pip-audit|pipx:pip-audit|python|ligera|CVEs dependencias"
  "codespell|codespell|pipx:codespell|multi|ligera|Ortografia codigo"
)

# Funcion auxiliar: get_field N "linea"
get_field() { echo "$2" | cut -d'|' -f"$1"; }

# Analisis repo
count_ext() { find "$REPO" -type f -name "*.$1" -not -path '*/.git/*' -not -path '*/node_modules/*' -not -path '*/.venv/*' 2>/dev/null | wc -l | tr -d ' '; }
PY=$(count_ext py); SH=$(count_ext sh); JSON=$(count_ext json)
YML=$(( $(count_ext yml) + $(count_ext yaml) ))
AGENTS=$(find "$REPO" -type f -iname '*agent*' -not -path '*/.git/*' 2>/dev/null | wc -l | tr -d ' ')

# Lenguajes en el repo
lang_has() {
  case "$1" in
    python) [[ $PY -gt 0 ]] ;; shell) [[ $SH -gt 0 ]] ;;
    data) [[ $JSON -gt 0 || $YML -gt 0 ]] ;; multi) return 0 ;; *) return 1 ;;
  esac
}

hdr "REPOSITORIO"
info "Ruta: $REPO"
echo -e "  Python:${PY}  Shell:${SH}  JSON:${JSON}  YAML:${YML}  ${C_B}Agentes:${AGENTS}${C_RESET}"

hdr "YA INSTALADO"
FOUND=0
for line in "${CATALOG[@]}"; do
  key=$(get_field 1 "$line"); bin=$(get_field 2 "$line"); ram=$(get_field 4 "$line")
  if have "$bin"; then FOUND=1; ok "$key ($ram)"; fi
done
[[ $FOUND -eq 0 ]] && info "Ninguna detectada"

hdr "RECOMENDADO INSTALAR"
PLAN_KEYS=(); PLAN_CMDS=(); PLAN_COUNT=0
for line in "${CATALOG[@]}"; do
  key=$(get_field 1 "$line"); bin=$(get_field 2 "$line")
  inst=$(get_field 3 "$line"); lang=$(get_field 4 "$line"); ram=$(get_field 5 "$line"); desc=$(get_field 6 "$line")
  have "$bin" && continue
  [[ $RECOMMEND_ALL -eq 1 ]] || lang_has "$lang" || continue

  method="${inst%%:*}"; pkg="${inst##*:}"
  case "$method" in
    pipx) [[ $HAS_PIPX -eq 1 ]] && cmd="pipx install $pkg" || { [[ $HAS_PIP -eq 1 ]] && cmd="pip install -q $pkg"; } || { warn "$key: sin pip"; continue; } ;;
    pip) [[ $HAS_PIP -eq 1 ]] && cmd="pip install -q $pkg" || { warn "$key: sin pip"; continue; } ;;
    npm) [[ $HAS_NPM -eq 1 ]] && cmd="npm install -g $pkg" || { warn "$key: sin npm"; continue; } ;;
    apt) [[ $HAS_APT -eq 1 ]] && cmd="${HAS_SUDO:+sudo }apt-get install -y -qq $pkg" || { warn "$key: sin apt"; continue; } ;;
    cargo) [[ $HAS_CARGO -eq 1 ]] && cmd="cargo install $pkg" || { warn "$key: sin cargo"; continue; } ;;
    *) warn "$key: metodo desconocido $method"; continue ;;
  esac
  PLAN_KEYS[$PLAN_COUNT]="$key"; PLAN_CMDS[$PLAN_COUNT]="$cmd"; ((PLAN_COUNT++))
  echo -e "  ${C_Y}+${C_RESET} ${C_B}${key}${C_RESET} ($ram) — ${desc}"
  info "    → $cmd"
done
[[ $PLAN_COUNT -eq 0 ]] && ok "Nada pendiente"

if [[ $PLAN_COUNT -gt 0 ]]; then
  if [[ $DRY_RUN -eq 1 ]]; then hdr "DRY-RUN — no se instala nada"
  elif [[ $AUTO_YES -eq 1 ]]; then
    hdr "INSTALANDO $PLAN_COUNT herramientas"
    INSTALLED=0; FAILED=0
    for ((i=0; i<PLAN_COUNT; i++)); do
      echo -n "  ${PLAN_KEYS[$i]}... "
      if eval "${PLAN_CMDS[$i]}" >>"$LOGS_DIR/install.log" 2>&1; then echo "✓"; ((INSTALLED++)); else echo "✗"; ((FAILED++)); fi
    done
    ok "Instaladas: $INSTALLED"; [[ $FAILED -gt 0 ]] && warn "Fallidas: $FAILED → $LOGS_DIR/install.log"
  fi
fi

hdr "ORDEN OPTIMO"
echo "  1. ruff check --fix  →  ruff format  →  autoflake"
echo "  2. vulture (muerto)  →  jscpd (clones)"
echo "  3. mypy  →  bandit  →  semgrep"
echo "  4. radon  →  xenon (gate)"
echo "  5. SOBREVIVIENTES → qwen2.5-coder:14b (4 workers)"