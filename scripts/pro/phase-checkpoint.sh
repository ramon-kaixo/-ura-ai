#!/usr/bin/env bash
# phase-checkpoint.sh - Marcador 80/100 para fases UDO
# Uso: phase-checkpoint.sh <TASK-ID> "situación" "problema_pendiente"
# Escribe .opencode/checkpoints/phase-<N>-80.json y actualiza nota UDO

set -euo pipefail

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() { echo -e "${GREEN}[INFO]${NC} $*"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*" >&2; }

# Helper: array to JSON array (handles empty arrays)
array_to_json() {
	local arr=("$@")
	if [[ ${#arr[@]} -eq 0 ]]; then
		echo "[]"
	else
		printf '%s\n' "${arr[@]}" | jq -R . | jq -s .
	fi
}

# Validar argumentos
if [[ $# -ne 3 ]]; then
	log_error "Uso: $0 <TASK-ID> \"situación\" \"problema_pendiente\""
	log_error "Ejemplo: $0 TASK-20260925-001 \"4 de 5 módulos listos\" \"Falta OAuth2\""
	exit 1
fi

TASK_ID="$1"
SITUACION="$2"
PROBLEMA_PENDIENTE="$3"

# Validar formato TASK-ID
if [[ ! "$TASK_ID" =~ ^TASK-[0-9]{8}-[0-9]{3}$ ]]; then
	log_error "Formato TASK-ID inválido: $TASK_ID (esperado: TASK-YYYYMMDD-NNN)"
	exit 1
fi

# Rutas base
URA_ROOT="/Users/ramonesnaola/URA"
TASK_FILE="${URA_ROOT}/docs/udo/tasks/${TASK_ID}.md"
COORD_FILE="${URA_ROOT}/docs/udo/coordination.json"
CHECKPOINT_DIR="${URA_ROOT}/.opencode/checkpoints"
MICRODATA_DIR="${URA_ROOT}/.opencode/microdata"

# Verificar que TASK existe
if [[ ! -f "$TASK_FILE" ]]; then
	log_error "Tarea no encontrada: $TASK_FILE"
	exit 1
fi

# Verificar directorios
mkdir -p "$CHECKPOINT_DIR" "$MICRODATA_DIR"

# Extraer número de fase del TASK-ID (últimos 3 dígitos)
PHASE_NUM=$(echo "$TASK_ID" | sed 's/.*-0*\([0-9]*\)$/\1/')
CHECKPOINT_FILE="${CHECKPOINT_DIR}/phase-${PHASE_NUM}-80.json"

# Obtener timestamp ISO 8601
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# Obtener commits recientes (últimos 10)
COMMITS=()
while IFS= read -r line; do
	[[ -n "$line" ]] && COMMITS+=("$line")
done < <(git -C "$URA_ROOT" log --oneline -10 --format="%h %s" 2>/dev/null || true)

# Generar JSON del checkpoint
cat >"$CHECKPOINT_FILE" <<EOF
{
  "task_id": "$TASK_ID",
  "progreso": 80,
  "timestamp": "$TIMESTAMP",
  "situacion": "$SITUACION",
  "problema_pendiente": "$PROBLEMA_PENDIENTE",
  "microdata_ref": ".opencode/microdata/phase-${PHASE_NUM}.jsonl",
  "evidencia_commits": $(array_to_json "${COMMITS[@]}")
}
EOF

# Validar JSON generado
if ! jq empty "$CHECKPOINT_FILE" 2>/dev/null; then
	log_error "JSON generado inválido en $CHECKPOINT_FILE"
	exit 1
fi

# Actualizar nota en UDO
NOTA_UDO="CHECKPOINT 80%: $SITUACION | problema: $PROBLEMA_PENDIENTE"
if ! /Users/ramonesnaola/URA/scripts/pro/ura-udo update "$TASK_ID" --nota "$NOTA_UDO" 2>&1 | grep -q "updated"; then
	log_warn "No se pudo actualizar nota UDO (puede que ura-udo no esté en PATH o la tarea no esté en estado válido)"
fi

log_info "Checkpoint 80% creado: $CHECKPOINT_FILE"
log_info "Nota UDO añadida: $NOTA_UDO"
cat "$CHECKPOINT_FILE"
