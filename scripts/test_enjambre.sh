#!/bin/bash
set -euo pipefail
# test_enjambre.sh — Test de integracion del Enjambre completo
BIBLIOTECARIO="${HOME}/URA/ura_ia_1972/sandbox/Aprendizaje/Enjambre/bibliotecario.sh"
INFORMES_DIR="${HOME}/URA/ura_ia_1972/sandbox/Aprendizaje/Enjambre/informes"
TIMEOUT=600; PASS=0; FAIL=0

echo "🧪 Test de Integracion del Enjambre — $(date)"
echo "═══════════════════════════════════════════════"

echo "   ▶️ Ejecutando bibliotecario.sh (${TIMEOUT}s)..."
if timeout "$TIMEOUT" bash "$BIBLIOTECARIO" 2>/dev/null; then
    echo "   ✅ Bibliotecario finalizado"
else
    echo "   🔴 Timeout o error"
    FAIL=$((FAIL + 1))
fi

echo "   📋 Verificando informes..."
for buzo in tendencias practicas modelos academico video economia recetas teoria_culinaria fotos_cocina competencia_pamplona tendencias_locales bares_espana bares_copas video_instagram carteles_menu vigilancia red sistema flota; do
    INFORME=$(find "$INFORMES_DIR" -name "hallazgos_${buzo}_*.json" -mmin -15 2>/dev/null | sort | tail -1)
    if [ -n "$INFORME" ]; then
        if jq -e 'type == "array"' "$INFORME" >/dev/null 2>&1; then
            echo "      ✅ $buzo: $(jq 'length' "$INFORME") items"
            PASS=$((PASS + 1))
        else
            echo "      🔴 $buzo: JSON invalido"
            FAIL=$((FAIL + 1))
        fi
    else
        echo "      🟡 $buzo: sin informe"
    fi
done

echo "═══════════════════════════════════════════════"
echo "   ✅ $PASS pasados  🔴 $FAIL fallados"
exit $FAIL
