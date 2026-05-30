#!/bin/bash
echo "🧪 URA UAT — Test de Aceptación"
echo "========================================="
P=0;F=0

check(){
  local name="$1"; shift
  if "$@" >/dev/null 2>&1; then
    echo "  ✅ $name"; P=$((P+1))
  else
    echo "  ❌ $name"; F=$((F+1))
  fi
}

check "Tuneladora instalada" test -f ~/bin/auto_cleanup.sh
check "Sandbox running" docker ps --filter name=ura-mejora --format '{{.Names}}'
check "Registry API :5100" curl -s http://127.0.0.1:5100/agents
check "Dashboard :5101" curl -s http://127.0.0.1:5101
check "Timer auto-cleanup" launchctl list com.coderefine.auto-cleanup
check "Herramientas instaladas" command -v ruff
check "Bibliotecario endpoint" curl -s "http://127.0.0.1:5100/bibliotecario/consulta?q=test"

echo "========================================="
echo "  ✅ $P pasados  ❌ $F fallidos"
NOTA=$((10 - F * 2)); [ $NOTA -lt 0 ] && NOTA=0
echo "  NOTA: $NOTA/10"
exit $F
