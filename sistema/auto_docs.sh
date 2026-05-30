#!/bin/bash
set -euo pipefail
# auto_docs.sh — Genera documentacion actualizada del ecosistema URA
OUTPUT="${HOME}/URA/ura_ia_1972/docs/ESTADO_ACTUAL.md"

MODELOS=$(ollama list 2>/dev/null || echo "Ollama no disponible")
AGENTES=$(curl -s "http://127.0.0.1:5100/agents" 2>/dev/null | jq -r '.[] | "- \(.id) (\(.type))"' 2>/dev/null || echo "Registry no disponible")
SALUD=$(bash "${HOME}/URA/ura_ia_1972/scripts/health.sh" 2>/dev/null || echo "Health check no disponible")
DOCS=$(jq '.entradas | length' "${HOME}/URA/ura_ia_1972/knowledge/indice.json" 2>/dev/null || echo "0")

DISCO=$(curl -s "http://127.0.0.1:5103/health" 2>/dev/null | jq -r '.disco.uso_pct // 30')
FREE=$(vm_stat 2>/dev/null | awk '/free/ {print $3}' | sed 's/\.//' || echo 0)
RAM_MAC_MB=$((FREE * 4096 / 1024))
BUZOS=$(find "${HOME}/URA/ura_ia_1972/sandbox/Aprendizaje/Enjambre/informes" -name "hallazgos_*.json" -mtime -7 2>/dev/null | wc -l | tr -d ' ')

cat > "$OUTPUT" << EOF
# URA — Estado Actual del Ecosistema

*Generado automaticamente: $(date)*

## Modelos de IA activos
\`\`\`
$MODELOS
\`\`\`

## Agentes registrados
\`\`\`
$AGENTES
\`\`\`

## Salud del sistema
\`\`\`
$SALUD
\`\`\`

## Documentos indexados
$DOCS documentos en el Archivo de Conocimiento

## Seguridad
- Dashboard + Registry: Protegidos con token
- Ollama GX10: nginx + auth_basic (pendiente)
- Logs: Rotacion automatica
- Watchdog: Notificaciones activas

## Proyeccion de Capacidad

| Recurso | Uso actual |
|---------|:----------:|
| Disco | ${DISCO:-30}% |
| RAM Mac | ${RAM_MAC_MB:-0} MB libre |
| Buzos activos (7d) | ${BUZOS:-0} |
EOF

echo "OK docs/ESTADO_ACTUAL.md"
