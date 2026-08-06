#!/bin/bash
set -uo pipefail

# URA System Health Check
# Checks critical system components and outputs a pass/fail report.
# Designed to run standalone, from cron, or via systemd timer.
#
# Exit codes:
#   0 — all checks passed (no failures)
#   1 — warnings only (no failures)
#   2 — one or more failures
#
# Dependencies (M=mandatory, O=optional, G=graceful degradation):
#   M — systemctl    (all service checks fail without it)
#   M — nvidia-smi   (GPU check fails, continues)
#   M — ss           (X11 socket check fails)
#   O — curl         (model-router check degrades to port-only check)
#   M — df           (disk check fails)
#   M — free         (memory check fails)
#   M — journalctl   (journal check fails)
#   M — lsmod        (kernel module check fails)

MODEL_ROUTER_URL="http://localhost:11435/api/health"
CRITICAL_SERVICES=(
  "gdm.service"
  "opencode.service"
  "ollama.service"
  "ura-openclaw.service"
  "model-router.service"
  "model-router"
  "ura-mochila.service"
  "ura-voice.service"
  "ura-go2rtc.service"
  "ura-audit-api.service"
  "ura-agent-hierarchy.service"
)

# Known pre-existing failures (non-blocking, unrelated to current fix scope).
# These exist from before the 2026-07-01 intervention and are tracked separately.
# Maintenance: update this list after resolving any of these units or when
# new pre-existing failures are identified. A unit belongs here only if it
# was already failing BEFORE the current change and is not caused by it.
KNOWN_FAILED_UNITS=(
  "ura-aspirador.service"
  "ura-detector.service"
  "ura-hetzner-tunnel.service"
  "ura-historiador.service"
  "ura-procesamiento-lento.service"
  "ura-voice.service"
)

# Journal error budget: known noisy sources that don't indicate real problems.
# Patterns here are excluded from the "real errors" count and reported
# separately for visibility. If a pattern matches too broadly or stops
# matching after an update, adjust accordingly.
# Currently excluded:
#   - GDM remote display assertions (on_display_added/removed):
#     Known harmless bug with NVIDIA + remote display handling. Not related
#     to login functionality.
JOURNAL_NOISE_PATTERNS=(
  "on_display_added: assertion.*GDM_IS_REMOTE_DISPLAY"
  "on_display_removed: assertion.*GDM_IS_REMOTE_DISPLAY"
)

DISK_WARN=85
DISK_CRIT=95

PASS=0; FAIL=0; WARN=0

log_pass() { echo "  [PASS] $1"; ((PASS++)); }
log_fail() { echo "  [FAIL] $1"; ((FAIL++)); }
log_warn() { echo "  [WARN] $1"; ((WARN++)); }
log_info() { echo "    $1"; }

check_deps() {
  local missing_mandatory=0 missing_optional=0
  # mandatory (exit if missing)
  for cmd in systemctl nvidia-smi ss df free journalctl lsmod; do
    if ! command -v "$cmd" &>/dev/null; then
      echo "  [DEPS] [MANDATORY] $cmd not found" >&2
      ((missing_mandatory++))
    fi
  done
  # optional (warn but continue)
  for cmd in curl; do
    if ! command -v "$cmd" &>/dev/null; then
      echo "  [DEPS] [OPTIONAL] $cmd not found — some checks will degrade" >&2
      ((missing_optional++))
    fi
  done
  if [ "$missing_mandatory" -gt 0 ]; then
    echo "  [DEPS] $missing_mandatory mandatory dependencies missing" >&2
    exit 2
  fi
  [ "$missing_optional" -gt 0 ] && log_info "Optional missing deps: $missing_optional"
}

summary_header() {
  echo "========================================"
  echo " URA System Health Check"
  echo " Host: $(hostname)"
  echo " Date: $(date '+%Y-%m-%d %H:%M:%S %Z')"
  echo " Uptime: $(uptime -p | sed 's/up //')"
  echo "========================================"
}

print_summary() {
  TOTAL=$((PASS + FAIL + WARN))
  echo ""
  echo "========================================"
  echo " $PASS passed, $WARN warnings, $FAIL failed (of $TOTAL)"
  echo "========================================"
  if [ "$FAIL" -gt 0 ]; then
    exit 2
  elif [ "$WARN" -gt 0 ]; then
    exit 1
  fi
  exit 0
}

check_systemd_failed() {
  echo "-- Systemd Failed --"
  local failed_data new_fail
  failed_data=$(systemctl --failed --no-pager 2>/dev/null | tail -n +2 | head -n -2 || true)
  if [ -z "$failed_data" ]; then
    log_pass "No failed units"; return
  fi

  new_fail=0
  while IFS= read -r line; do
    local unit
    unit=$(echo "$line" | awk '{print $1}')
    local known=0
    for k in "${KNOWN_FAILED_UNITS[@]}"; do
      if [ "$unit" = "$k" ]; then known=1; break; fi
    done
    if [ "$known" -eq 1 ]; then
      log_info "$line  [known pre-existing, non-blocking]"
    else
      log_fail "$line  [NEW — not in known list]"
      ((new_fail++))
    fi
  done <<< "$failed_data"

  local count
  count=$(echo "$failed_data" | grep -c . || true)
  if [ "$new_fail" -eq 0 ]; then
    log_warn "$count failed unit(s) — all KNOWN pre-existing, non-blocking"
  fi
}

check_model_router() {
  echo "-- Model Router :11435 --"
  if curl -sf "$MODEL_ROUTER_URL" >/dev/null 2>&1; then
    log_pass "model-router responding"
  elif ss -tln 2>/dev/null | grep -q ":11435"; then
    log_warn "port open but curl failed"
  else
    log_fail "model-router NOT responding"
  fi
}

check_services() {
  echo "-- Critical Services --"
  for svc in "${CRITICAL_SERVICES[@]}"; do
    if systemctl is-active --quiet "$svc" 2>/dev/null; then
      log_pass "$svc"
    elif systemctl --user is-active --quiet "$svc" 2>/dev/null; then
      log_pass "$svc (user)"
    else
      local st
      st=$(systemctl is-active "$svc" 2>&1 || systemctl --user is-active "$svc" 2>&1 || echo "unknown")
      log_fail "$svc ($st)"
    fi
  done
}

check_nvidia() {
  echo "-- NVIDIA GPU --"
  if ! command -v nvidia-smi &>/dev/null; then
    log_fail "nvidia-smi not found"; return
  fi
  local drv temp pwr
  drv=$(nvidia-smi --query-gpu=driver_version --format=csv,noheader 2>&1) || { log_fail "nvidia-smi failed"; return; }
  temp=$(nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader 2>&1)
  pwr=$(nvidia-smi --query-gpu=power.draw --format=csv,noheader 2>&1)
  log_pass "Driver $drv, ${temp}C, $pwr"
}

check_x11() {
  echo "-- X11 Sockets --"
  local n
  n=$(ss -x -a 2>/dev/null | grep -c "X11-unix/X" || true)
  if [ "$n" -ge 1 ]; then
    log_pass "$n X11 socket(s) present"
    ss -x -a 2>/dev/null | grep "X11-unix/X" | awk '{print $NF}' | sort -u | while read -r s; do
      log_info "$s"
    done
  else
    log_fail "No X11 sockets"
  fi
}

check_disk() {
  echo "-- Disk --"
  local used pct
  used=$(df -h / 2>/dev/null | tail -1)
  pct=$(echo "$used" | awk '{print $5}' | tr -d '%')
  log_info "${pct}% used"
  if [ "$pct" -ge "$DISK_CRIT" ]; then
    log_fail "DISK CRITICAL: ${pct}%"
  elif [ "$pct" -ge "$DISK_WARN" ]; then
    log_warn "DISK WARNING: ${pct}%"
  else
    log_pass "Disk OK: ${pct}%"
  fi
}

check_journal() {
  echo "-- Journal Errors (this boot, -p err) --"
  local raw raw_nonnoise

  # Raw count
  raw=$(journalctl -b -p err --no-pager 2>/dev/null | grep -c . || true)

  # Count after removing known noise patterns
  local filter=""
  for p in "${JOURNAL_NOISE_PATTERNS[@]}"; do
    [ -n "$filter" ] && filter="$filter|$p" || filter="$p"
  done
  raw_nonnoise=$(journalctl -b -p err --no-pager 2>/dev/null | grep -vE "$filter" | grep -c . || true)

  # Group by service
  local top
  top=$(journalctl -b -p err --no-pager --output=short 2>/dev/null | \
    awk '{print $5}' | sed 's/\[.*//' | sort | uniq -c | sort -rn | head -5)

  log_info "Total: $raw lines (${raw_nonnoise} after noise filter)"
  log_info "Excluded patterns: GDM remote display assertions (known harmless bug)"
  if [ "$raw_nonnoise" -ge 100 ]; then
    log_fail "$raw_nonnoise real errors this boot"
    echo "$top" | while read -r line; do log_info "$line"; done
  elif [ "$raw_nonnoise" -ge 20 ]; then
    log_warn "$raw_nonnoise real errors this boot"
    echo "$top" | while read -r line; do log_info "$line"; done
  else
    log_pass "$raw_nonnoise real errors this boot"
  fi

  # Diagnose top sources
  local gdm_noise
  gdm_noise=$(journalctl -b -p err --no-pager 2>/dev/null | grep -c "on_display_added.*GDM_IS_REMOTE_DISPLAY\|on_display_removed.*GDM_IS_REMOTE_DISPLAY" 2>/dev/null || true)
  [ "$gdm_noise" -gt 0 ] && log_info "GDM remote display assertions (known harmless bug): $gdm_noise"
}

check_memory() {
  echo "-- Memory --"
  local info pct
  info=$(free -h 2>/dev/null | awk '/Mem:/{print $3 " / " $2}')
  pct=$(free 2>/dev/null | awk '/Mem:/{printf "%.0f", $3/$2 * 100}')
  log_info "$info ($pct%)"
  if [ "$pct" -ge 90 ]; then
    log_warn "Memory at ${pct}%"
  else
    log_pass "Memory at ${pct}%"
  fi
}

check_modules() {
  echo "-- NVIDIA Modules --"
  local m=0
  for mod in nvidia nvidia_modeset nvidia_drm nvidia_uvm; do
    if lsmod 2>/dev/null | grep -q "^$mod "; then :; else
      log_fail "Module $mod not loaded"; ((m++))
    fi
  done
  [ "$m" -eq 0 ] && log_pass "All NVIDIA modules loaded"
}

main() {
  summary_header
  check_deps
  check_systemd_failed
  check_model_router
  check_services
  check_nvidia
  check_x11
  check_disk
  check_journal
  check_memory
  check_modules
  print_summary
}

main "$@"
