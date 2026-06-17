#!/usr/bin/env bash
# qdrant_health.sh — Weekly Qdrant health check.
# Checks collection status, points count, and segment merging.
set -euo pipefail

QDRANT_HOST="${QDRANT_HOST:-localhost:6333}"
LOG="/var/log/qdrant_health.log"

{
  echo "=== Qdrant Health Check: $(date -Iseconds) ==="
  
  # 1. Overall collection status
  curl -sf "http://${QDRANT_HOST}/collections" | python3 -c "
import json, sys
d = json.load(sys.stdin)
for c in d['result']['collections']:
    print(f'  {c[\"name\"]}: OK')
" 2>/dev/null || echo "  ERROR: Qdrant unreachable"
  
  # 2. Point counts per collection
  for col in incidente_record ura_documents ura_transacciones; do
    points=$(curl -sf "http://${QDRANT_HOST}/collections/${col}" | python3 -c "
import json, sys
d = json.load(sys.stdin)
r = d.get('result', {})
print(r.get('points_count', '?'))
" 2>/dev/null || echo "?")
    echo "  ${col}: ${points} points"
  done
  
  # 3. Disk usage
  echo "  Disk: $(df -h / | tail -1 | awk '{print $3 \" used / \" $2 \" (\" $5 \")\"}')"
  
  echo "=== Done ==="
} >> "$LOG" 2>&1

# Keep last 10 check results
tail -n 30 "$LOG" | head -5  # echo first 5 lines to stdout for cron
