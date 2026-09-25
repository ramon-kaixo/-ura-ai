#!/usr/bin/env bash
# phase-close.sh - Microdato automático al cerrar fase UDO
# Uso: phase-close.sh <TASK-ID>
# Lee expediente UDO + git diff → escribe .opencode/microdata/phase-<N>.jsonl (append)

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $*"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*" >&2; }

# Helper: array to JSON array (handles empty arrays)
# Usage: array_to_json "elem1" "elem2" ...
array_to_json() {
	if [[ $# -eq 0 ]]; then
		echo "[]"
	else
		printf '%s\n' "$@" | jq -R . | jq -s .
	fi
}

# Helper: escape string for JSON
json_escape() {
	printf '%s' "$1" | jq -Rs .
}

# Safe grep for YAML frontmatter fields: returns value after "key: "
get_field() {
	local field="$1"
	local file="$2"
	# Match "key: value" at start of line, return value part
	grep -m1 "^${field}:" "$file" 2>/dev/null | sed "s/^${field}: *//" || true
}

if [[ $# -ne 1 ]]; then
	log_error "Uso: $0 <TASK-ID>"
	log_error "Ejemplo: $0 TASK-20260925-001"
	exit 1
fi

TASK_ID="$1"

if [[ ! "$TASK_ID" =~ ^TASK-[0-9]{8}-[0-9]{3}$ ]]; then
	log_error "Formato TASK-ID inválido: $TASK_ID"
	exit 1
fi

URA_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TASK_FILE="${URA_ROOT}/docs/udo/tasks/${TASK_ID}.md"
MICRODATA_DIR="${URA_ROOT}/.opencode/microdata"

if [[ ! -f "$TASK_FILE" ]]; then
	log_error "Tarea no encontrada: $TASK_FILE"
	exit 1
fi

mkdir -p "$MICRODATA_DIR"

PHASE_NUM=$(echo "$TASK_ID" | sed 's/.*-0*\([0-9]*\)$/\1/')
MICRODATA_FILE="${MICRODATA_DIR}/phase-${PHASE_NUM}.jsonl"

# Extraer campos del expediente UDO con valores por defecto
OBJETIVO=$(get_field 'descripcion' "$TASK_FILE" | head -c 500)
OBJETIVO=${OBJETIVO:-"Sin objetivo documentado"}

ESTADO=$(get_field 'estado' "$TASK_FILE" | tr -d ' ')
ESTADO=${ESTADO:-"DESCONOCIDO"}

VEREDICTO=$(get_field 'resultado' "$TASK_FILE" | head -c 200)
VEREDICTO=${VEREDICTO:-"Sin veredicto"}

NOTA=$(get_field 'nota' "$TASK_FILE" | head -c 500)
NOTA=${NOTA:-""}

EJECUTOR=$(get_field 'agente_terminal' "$TASK_FILE" | tr -d ' ')
EJECUTOR=${EJECUTOR:-"DESCONOCIDO"}

REVISOR=$(get_field 'agente_web' "$TASK_FILE" | tr -d ' ')
REVISOR=${REVISOR:-"DESCONOCIDO"}

COMMIT_BASE=$(get_field 'commit_base' "$TASK_FILE" | tr -d ' ')

# Obtener reserva (archivos declarados)
RESERVA=$(grep -A 10 '^reserva:' "$TASK_FILE" 2>/dev/null | sed '1d' | sed 's/^  - //' | tr '\n' ',' | sed 's/,$//' | head -c 500) || true
RESERVA=${RESERVA:-""}

# Git diff desde commit_base - usar while loop en lugar de mapfile (bash 3.2 compatible)
EVIDENCIA_COMMITS=()
EVIDENCIA_DIFF=""
if [[ -n "$COMMIT_BASE" && "$COMMIT_BASE" != "null" ]]; then
	while IFS= read -r line; do
		[[ -n "$line" ]] && EVIDENCIA_COMMITS+=("$line")
	done < <(git -C "$URA_ROOT" log --oneline "${COMMIT_BASE}..HEAD" --format="%h %s" 2>/dev/null || true)
	EVIDENCIA_DIFF=$(git -C "$URA_ROOT" diff --stat "${COMMIT_BASE}..HEAD" 2>/dev/null | tail -1 | sed 's/^ *//' || echo "")
else
	while IFS= read -r line; do
		[[ -n "$line" ]] && EVIDENCIA_COMMITS+=("$line")
	done < <(git -C "$URA_ROOT" log --oneline -5 --format="%h %s" 2>/dev/null || true)
	EVIDENCIA_DIFF=$(git -C "$URA_ROOT" diff --stat HEAD~5..HEAD 2>/dev/null | tail -1 | sed 's/^ *//' || echo "")
fi

# Extraer problemas conocidos de la nota
PROBLEMAS=()
while IFS= read -r line; do
	[[ "$line" =~ (problema|issue|bug|fallo|pendiente|falta|TODO|FIXME) ]] && PROBLEMAS+=("$line")
done <<<"$NOTA"

TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# Helper: array to JSON array (handles empty arrays) - outputs compact JSON
array_to_json() {
	if [[ $# -eq 0 ]]; then
		echo "[]"
	else
		printf '%s\n' "$@" | jq -R . | jq -cs .
	fi
}

# Helper: escape string for JSON
json_escape() {
	printf '%s' "$1" | jq -Rs .
}

# Build JSON pieces
OBJETIVO_JSON=$(json_escape "$OBJETIVO")
ESTADO_JSON=$(json_escape "$ESTADO")
VEREDICTO_JSON=$(json_escape "$VEREDICTO")
EJECUTOR_JSON=$(json_escape "$EJECUTOR")
REVISOR_JSON=$(json_escape "$REVISOR")
EVIDENCIA_DIFF_JSON=$(json_escape "$EVIDENCIA_DIFF")
RESERVA_JSON=$(json_escape "$RESERVA")
EVIDENCIA_COMMITS_JSON=$(array_to_json "${EVIDENCIA_COMMITS[@]+"${EVIDENCIA_COMMITS[@]}"}")
PROBLEMAS_JSON=$(array_to_json "${PROBLEMAS[@]+"${PROBLEMAS[@]}"}")
RESERVA_JSON=$(json_escape "$RESERVA")

TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# Generar línea JSONL
cat >>"$MICRODATA_FILE" <<EOF
{"task_id":"$TASK_ID","timestamp":"$TIMESTAMP","objetivo":$OBJETIVO_JSON,"estado":$ESTADO_JSON,"evidencia_commits":$EVIDENCIA_COMMITS_JSON,"evidencia_diff":$EVIDENCIA_DIFF_JSON,"decisión":$VEREDICTO_JSON,"resumen_ejecutor":$EJECUTOR_JSON,"resumen_revisor":$REVISOR_JSON,"problemas_conocidos":$PROBLEMAS_JSON,"reserva":$RESERVA_JSON}
EOF

# Validar JSONL - Bug 1 fix: jq empty fails on multi-line JSONL, use jq -c . instead
if ! jq -c . "$MICRODATA_FILE" >/dev/null 2>&1; then
	log_error "JSONL generado inválido en $MICRODATA_FILE"
	exit 1
fi

log_info "Microdato escrito: $MICRODATA_FILE"
tail -1 "$MICRODATA_FILE" | jq .
