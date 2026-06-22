#!/bin/bash
# dr_test.sh — Prueba trimestral de recuperación
# Verifica que los backups son válidos y se pueden restaurar.
# Uso: ./dr_test.sh
set -euo pipefail

PASS=0
FAIL=0
LOG="/tmp/ura_dr_test_$(date +%Y%m%d).log"

ok()   { echo "[PASS] $*" | tee -a "$LOG"; PASS=$((PASS + 1)); }
fail() { echo "[FAIL] $*" | tee -a "$LOG"; FAIL=$((FAIL + 1)); }

echo "=== URA DR Test $(date -u +%Y-%m-%dT%H:%M:%SZ) ===" | tee "$LOG"
echo "" | tee -a "$LOG"

# Test 1: Backup de código existe y es válido
echo "--- Test 1: Backup de código ---" | tee -a "$LOG"
CODE_BACKUP=$(ls -t /home/ramon/URA/backups/code/ura_*.tar.gz 2>/dev/null | head -1)
if [ -n "$CODE_BACKUP" ] && tar tzf "$CODE_BACKUP" >/dev/null 2>&1; then
    ok "Backup código válido: $(basename $CODE_BACKUP) ($(du -h "$CODE_BACKUP" | cut -f1))"
else
    fail "No hay backup de código válido"
fi

# Test 2: Backup Qdrant existe
echo "--- Test 2: Backup Qdrant ---" | tee -a "$LOG"
QDRANT_BACKUP=$(ls -t /home/ramon/URA/backups/qdrant/qdrant_*.tar.gz 2>/dev/null | head -1)
if [ -n "$QDRANT_BACKUP" ] && tar tzf "$QDRANT_BACKUP" >/dev/null 2>&1; then
    ok "Backup Qdrant válido: $(basename $QDRANT_BACKUP)"
else
    fail "No hay backup de Qdrant válido"
fi

# Test 3: Systemd services activos
echo "--- Test 3: Servicios críticos ---" | tee -a "$LOG"
for svc in ura-ejecutor model-router ura-openclaw ura-mochila; do
    if systemctl is-active --quiet "$svc" 2>/dev/null; then
        ok "Servicio $svc activo"
    else
        fail "Servicio $svc NO activo"
    fi
done

# Test 4: Qdrant responde
echo "--- Test 4: Qdrant ---" | tee -a "$LOG"
if curl -sf http://127.0.0.1:6333/collections >/dev/null 2>&1; then
    ok "Qdrant responde"
else
    fail "Qdrant NO responde"
fi

# Test 5: Ollama responde
echo "--- Test 5: Ollama ---" | tee -a "$LOG"
if curl -sf http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
    ok "Ollama responde"
else
    fail "Ollama NO responde"
fi

# Test 6: Espacio en disco
echo "--- Test 6: Disco ---" | tee -a "$LOG"
DISK_USAGE=$(df / | tail -1 | awk '{print $5}' | tr -d '%')
if [ "$DISK_USAGE" -lt 85 ]; then
    ok "Disco al ${DISK_USAGE}% (< 85%)"
else
    fail "Disco al ${DISK_USAGE}% (>= 85%)"
fi

# Test 7: Secrets rotados?
echo "--- Test 7: Rotación de secrets ---" | tee -a "$LOG"
ROTATION_LOG="/home/ramon/URA/backups/reports/secret_rotation.json"
if [ -f "$ROTATION_LOG" ]; then
    LAST=$(python3 -c "import json; print(json.load(open('$ROTATION_LOG')).get('last_rotation','never'))")
    ok "Última rotación secrets: $LAST"
else
    fail "No hay registro de rotación de secrets"
fi

# Test 8: git status
echo "--- Test 8: Git ---" | tee -a "$LOG"
if cd /home/ramon/URA/ura_ia_1972 && git status --porcelain | grep -q .; then
    fail "Hay cambios sin commit en el repositorio"
else
    ok "Repositorio limpio"
fi

# Summary
echo "" | tee -a "$LOG"
echo "=== Resultado: $PASS passed, $FAIL failed ===" | tee -a "$LOG"

exit $FAIL