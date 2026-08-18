#!/bin/bash
# Verificador de instalaciones F8-F10 (post-sudo) — 2026-08-18 WEB
# Uso: bash scripts/pro/verificar_instalaciones_f8.sh
# Comprueba: heartbeat (umbral VRAM), stack monitoreo, audit-api, backup-mac.
# Read-only: no modifica nada.

PASS=0; FAIL=0
check() {  # check <descripcion> <comando...>
    local desc="$1"; shift
    if "$@" >/dev/null 2>&1; then
        echo "  [OK] $desc"; PASS=$((PASS+1))
    else
        echo "  [FALLO] $desc"; FAIL=$((FAIL+1))
    fi
}

echo "=== Verificacion instalaciones F8-F10 ==="

echo "1. Heartbeat con umbral VRAM nuevo (sin vram_pressure_high en 5 min):"
check "heartbeat sin vram_pressure reciente" \
    bash -c "! journalctl -u ura-heartbeat --since '5 min ago' --no-pager 2>/dev/null | grep -q vram_pressure_high"

echo "2. Stack monitoreo (prometheus/grafana/alertmanager/node-exporter/webhook):"
check "prometheus 9094 healthy" curl -sf --max-time 3 http://127.0.0.1:9094/-/healthy
check "grafana 3001 health"      curl -sf --max-time 3 http://127.0.0.1:3001/api/health
check "alertmanager 9095 healthy" curl -sf --max-time 3 http://127.0.0.1:9095/-/healthy
check "node-exporter 9100 metrics" curl -sf --max-time 3 http://127.0.0.1:9100/metrics
check "webhook-alerts 9105 health" curl -sf --max-time 3 http://127.0.0.1:9105/health

echo "3. Audit-api con /metrics (P5+P9):"
check "audit-api 5053/metrics" curl -sf --max-time 3 http://127.0.0.1:5053/metrics

echo "4. Backup a la Mac limpio (sin estado failed):"
check "backup-mac sin estado failed" bash -c "! systemctl is-failed ura-backup-mac.service 2>/dev/null | grep -q failed"

echo "5. Watch-daemon procesando la cola (la cola se vacio):"
check "cola del watch-daemon vacia" bash -c "! test -f /home/ramon/URA/ura_ia_1972/.tuneladora/.watch_pending"

echo ""
echo "RESULTADO: $PASS OK, $FAIL fallos"
[ "$FAIL" -eq 0 ] && echo "TODO OK — instalaciones verificadas" || echo "Revisar los fallos (comandos de verificacion individuales arriba)"
exit 0
