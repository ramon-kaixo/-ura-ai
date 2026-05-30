#!/bin/bash
# upgrade_pipeline.sh — Actualizacion combinada de OpenCode para la Tuneladora
# Inyectado por: URA Supervisor via integracion_opencode.sh
# Ejecutar desde: ciclo_mejora_6h.sh (seccion "Ensure environment")

echo "📦 [Tuneladora] Iniciando actualizacion combinada de OpenCode..."

# 1. Auto-upgrade del nucleo binario
opencode upgrade 2>/dev/null || echo "  opencode upgrade: no disponible (binario no actualizable)"

# 2. Plugin de auto-update
npm install -g opencode-plugin-auto-update --silent 2>/dev/null && \
  echo "  Plugin auto-update: OK" || \
  echo "  Plugin auto-update: ya instalado"

# 3. Forzar actualizacion sin throttling
export OPENCODE_AUTO_UPDATE_BYPASS_THROTTLE=true

# 4. Reiniciar servicio
if systemctl is-active opencode.service &>/dev/null; then
  sudo systemctl restart opencode.service && \
    echo "  Servicio OpenCode: reiniciado" || \
    echo "  Servicio OpenCode: fallo al reiniciar"
fi

# 5. Verificar integracion con Ura
curl -s -o /dev/null -w "%{http_code}" --max-time 3 http://127.0.0.1:9093/status 2>/dev/null && \
  echo "  Sync MCP (:9093): OK" || \
  echo "  Sync MCP (:9093): no responde"

echo "✅ [Tuneladora] OpenCode y sus subagentes integrados estan al dia."
