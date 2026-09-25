#!/usr/bin/env bash
# prune-phase.sh - Olvido selectivo dirigido: archiva logs/temps de fase cerrada
# Uso: prune-phase.sh <TASK-ID> [--all-older-than N] [--dry-run]
# Archiva logs/temps de la fase en .opencode/archive/phase-<N>/ y limpia memory.md

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $*"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*" >&2; }

DRY_RUN=false
ALL_OLDER_THAN=""

# Parse arguments
while [[ $# -gt 0 ]]; do
	case $1 in
	--all-older-than)
		ALL_OLDER_THAN="$2"
		shift 2
		;;
	--dry-run)
		DRY_RUN=true
		shift
		;;
	-*)
		echo "Opción desconocida: $1"
		exit 1
		;;
	*)
		TASK_ID="$1"
		shift
		;;
	esac
done

if [[ -z "${TASK_ID:-}" && -z "${ALL_OLDER_THAN:-}" ]]; then
	echo "Uso: $0 <TASK-ID> [--all-older-than N] [--dry-run]"
	echo "Ejemplo: $0 TASK-20260925-001"
	echo "       $0 --all-older-than 7d  # limpia todas las fases >7 días"
	exit 1
fi

URA_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
MICRODATA_DIR="${URA_ROOT}/.opencode/microdata"
ARCHIVE_DIR="${URA_ROOT}/.opencode/archive"
MEMORY_FILE="${URA_ROOT}/.opencode/memory.md"
LOG_DIR="${URA_ROOT}/.opencode/logs"
TMP_DIR="${URA_ROOT}/tmp"

# Función para archivar una fase por número de fase
archive_phase() {
	local phase_num="$1"
	local phase_task_id="TASK-${phase_num}"

	log_info "Archivando fase: $phase_task_id"

	local MICRODATA_FILE="${URA_ROOT}/.opencode/microdata/phase-${phase_num}.jsonl"
	local ARCHIVE_PHASE_DIR="${URA_ROOT}/.opencode/archive/phase-${phase_num}"

	if [[ ! -f "$MICRODATA_FILE" ]]; then
		log_warn "Microdato no encontrado: $MICRODATA_FILE (¿ejecutaste phase-close.sh?)"
		# Continuar anyway para limpiar logs
	fi

	mkdir -p "${URA_ROOT}/.opencode/archive/phase-${phase_num}"

	# Función para mover archivo/directorio - no fallar si no existe
	archive_item() {
		local src="$1"
		local dst="$2"
		if [[ -e "$src" ]]; then
			if [[ "$DRY_RUN" == "true" ]]; then
				log_info "[DRY-RUN] Movería: $src -> $dst"
			else
				mkdir -p "$(dirname "$dst")"
				mv "$src" "$dst"
				log_info "Archivado: $src -> $dst"
			fi
			return 0
		fi
		return 0 # No fallar si no existe
	}

	# 1. Archivar logs de la fase (filtrar por TASK-ID en nombre o contenido)
	log_info "Archivando logs de TASK-${phase_num}..."
	while IFS= read -r logfile; do
		archive_item "$logfile" "${URA_ROOT}/.opencode/archive/phase-${phase_num}/logs/$(basename "$logfile")"
	done < <(find "$LOG_DIR" -type f \( -name "*TASK-${phase_num}*" -o -name "*phase-${phase_num}*" \) 2>/dev/null)

	# 2. Archivar directorios temporales de la fase
	for tmpdir in "${TMP_DIR}/phase-${phase_num}" "${URA_ROOT}/.opencode/tmp/phase-${phase_num}"; do
		archive_item "$tmpdir" "${URA_ROOT}/.opencode/archive/phase-${phase_num}/tmp/"
	done

	# 3. Limpiar memory.md: eliminar líneas que contengan el TASK-ID
	if [[ -f "$MEMORY_FILE" ]]; then
		# Backup
		cp "$MEMORY_FILE" "${MEMORY_FILE}.bak.$(date +%s)"
		# Eliminar líneas con TASK-ID
		grep -v "TASK-${phase_num}" "$MEMORY_FILE" >"${MEMORY_FILE}.tmp" && mv "${MEMORY_FILE}.tmp" "$MEMORY_FILE"
		# Añadir nota de archivado
		echo "" >>"$MEMORY_FILE"
		echo "---" >>"$MEMORY_FILE"
		echo "Fase TASK-${phase_num} archivada $(date -u +"%Y-%m-%dT%H:%M:%SZ")" >>"$MEMORY_FILE"
		log_info "memory.md limpiado y anotado para fase ${phase_num}"
	fi

	log_info "Fase ${phase_num} archivada"
}

# Modo --all-older-than
if [[ -n "$ALL_OLDER_THAN" ]]; then
	log_info "Modo limpieza global: fases > $ALL_OLDER_THAN"
	# Buscar todos los microdata files y filtrar por timestamp
	while IFS= read -r file; do
		# Extraer timestamp de la última línea
		last_ts=$(tail -1 "$file" | jq -r '.timestamp' 2>/dev/null || echo "")
		if [[ -n "$last_ts" ]]; then
			file_epoch=$(date -j -f "%Y-%m-%dT%H:%M:%SZ" "$last_ts" +%s 2>/dev/null || echo 0)
			cutoff_epoch=$(date -j -v-"${ALL_OLDER_THAN}" +%s 2>/dev/null || echo 0)
			if [[ $file_epoch -lt $cutoff_epoch ]]; then
				phase_num=$(basename "$file" .jsonl | sed 's/phase-//')
				log_info "Archivando fase antigua: $phase_num (timestamp: $last_ts)"
				if [[ "$DRY_RUN" == "false" ]]; then
					archive_phase "$phase_num"
				else
					log_info "[DRY-RUN] Archivaría fase: $phase_num"
				fi
			fi
		fi
	done < <(find "$MICRODATA_DIR" -name "phase-*.jsonl" -type f)
	exit 0
fi

# Validar TASK-ID
if [[ ! "$TASK_ID" =~ ^TASK-[0-9]{8}-[0-9]{3}$ ]]; then
	echo "Formato TASK-ID inválido: $TASK_ID"
	exit 1
fi

PHASE_NUM=$(echo "$TASK_ID" | sed 's/.*-0*\([0-9]*\)$/\1/')

# Llamar función de archivado
archive_phase "$PHASE_NUM"

log_info "Poda completada para fase: $PHASE_NUM"
log_info "Archivo de fase: ${URA_ROOT}/.opencode/archive/phase-${PHASE_NUM}"

# Mostrar resumen del directorio archivado
if [[ -d "${URA_ROOT}/.opencode/archive/phase-${PHASE_NUM}" ]]; then
	count=$(find "${URA_ROOT}/.opencode/archive/phase-${PHASE_NUM}" -type f | wc -l | tr -d ' ')
	log_info "Archivos archivados: $count"
fi
