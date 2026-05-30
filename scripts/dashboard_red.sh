#!/bin/bash
set -euo pipefail
# dashboard_red.sh — Genera panel HTML con estado de la red
OUTPUT="${HOME}/URA/ura_ia_1972/docs/red/dashboard_red.html"
REGISTRY_URL="${REGISTRY_URL:-http://127.0.0.1:5100}"
INFORMES_DIR="${HOME}/URA/ura_ia_1972/sandbox/Aprendizaje/Enjambre/informes"
mkdir -p "$(dirname "$OUTPUT")"

DISPOSITIVOS=$(curl -s "$REGISTRY_URL" 2>/dev/null | jq '[.[] | select(.type == "dispositivo_red" or .type == "access_point")]' 2>/dev/null || echo "[]")
ULTIMO_INFORME=$(find "$INFORMES_DIR" -name "hallazgos_red_*.json" -mtime -7 2>/dev/null | sort | tail -1)
ULTIMO_JSON=$(cat "$ULTIMO_INFORME" 2>/dev/null | jq -c '{latencia: ([.[] | select(.tipo == "metrica" and .metrica == "latencia_gx10") | .valor] | first // "N/A"), dispositivos_ip: ([.[] | select(.tipo == "dispositivo_ip")] | length), aps: ([.[] | select(.tipo == "metrica_aps" and .metrica == "aps") | .valor] | add // 0), rogue: ([.[] | select(.tipo == "metrica_aps" and .metrica == "rogue_aps") | .valor] | add // 0)}' 2>/dev/null || echo "{}")

cat > "$OUTPUT" << HTML
<!DOCTYPE html><html lang="es"><head><meta charset="UTF-8"><title>URA — Dashboard de Red</title>
<style>
body{font-family:system-ui;margin:20px;background:#1e1e1e;color:#ddd}
h2{color:#4caf50}
table{border-collapse:collapse;width:100%;margin-bottom:20px}
th,td{padding:8px;text-align:left;border-bottom:1px solid #444}
th{background:#333}
.online{color:#4caf50}.offline{color:#f44336}.warning{color:#ff9800}
.metric{font-size:24px;font-weight:bold}
</style></head><body>
<h1>🌐 Dashboard de Red URA</h1>
<h2>📊 Metricas</h2>
<table><tr><th>Metrica</th><th>Valor</th></tr>
<tr><td>Latencia GX10</td><td class="metric" id="lat">$(echo "$ULTIMO_JSON" | jq -r '.latencia // "N/A"') ms</td></tr>
<tr><td>Dispositivos IP</td><td class="metric" id="dip">$(echo "$ULTIMO_JSON" | jq -r '.dispositivos_ip // 0')</td></tr>
<tr><td>APs detectados</td><td class="metric">$(echo "$ULTIMO_JSON" | jq -r '.aps // 0')</td></tr>
<tr><td>Rogue APs</td><td class="metric" id="rog">$(echo "$ULTIMO_JSON" | jq -r '.rogue // 0')</td></tr>
</table>
<h2>🖥️ Dispositivos IP</h2>
<table><tr><th>ID</th><th>IP</th><th>MAC</th><th>Ultimo visto</th></tr>
HTML

echo "$DISPOSITIVOS" | jq -r '.[] | select(.type == "dispositivo_red") | "<tr><td>\(.id // "?")</td><td>\(.ip // "?")</td><td>\(.mac // "?")</td><td>\(.last_seen // "?")</td></tr>"' >> "$OUTPUT" 2>/dev/null || true

cat >> "$OUTPUT" << HTML
</table>
<h2>📶 Puntos de Acceso</h2>
<table><tr><th>ID</th><th>SSID</th><th>Ultimo visto</th></tr>
HTML

echo "$DISPOSITIVOS" | jq -r '.[] | select(.type == "access_point") | "<tr><td>\(.id // "?")</td><td>\(.ssid // "?")</td><td>\(.last_seen // "?")</td></tr>"' >> "$OUTPUT" 2>/dev/null || true

echo "</table></body></html>" >> "$OUTPUT"

echo "OK docs/red/dashboard_red.html"
