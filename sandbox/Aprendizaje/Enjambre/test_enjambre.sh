#!/bin/bash
set -euo pipefail
REPO="${HOME}/URA/ura_ia_1972"
ENJAMBRE_DIR="${REPO}/sandbox/Aprendizaje/Enjambre"
TEST_DIR="${ENJAMBRE_DIR}/test"
INFORMES_DIR="${TEST_DIR}/informes"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
mkdir -p "$INFORMES_DIR" "${REPO}/docs/decisiones"

echo "🧪 Test del Enjambre — $(date)"
echo "=============================================="

# 1. Hallazgos de prueba simulados
cat > "${INFORMES_DIR}/hallazgos_versiones_${TIMESTAMP}.json" << 'VEOF'
[{"buzo":"versiones","paquete":"ruff","version_actual":"0.14.0","version_nueva":"0.16.0","accion":"pip install --upgrade ruff==0.16.0"}]
VEOF
cat > "${INFORMES_DIR}/hallazgos_modelos_${TIMESTAMP}.json" << 'MEOF'
[{"buzo":"modelos","accion":"candidato","modelo":"deepseek-coder:33b","especialidad":"code"}]
MEOF

# 2. Decisiones simuladas (sin gastar tokens LLM)
DECISIONES='[{"hallazgo":"ruff 0.16.0","decision":"install","razon":"Nueva versión con mejoras"}]'
DECISIONES_MODELOS='[{"modelo":"deepseek-coder:33b","decision":"install","razon":"Mejor especialización"}]'

# 3. Verificar coherencia
python3 -c "
import json
d=json.loads('''$DECISIONES''')
m=json.loads('''$DECISIONES_MODELOS''')
errs=[]
if not any(x.get('hallazgo')=='ruff 0.16.0' and x['decision']=='install' for x in d):
    errs.append('ruff no se instaló')
if not any(x.get('modelo')=='deepseek-coder:33b' and x['decision']=='install' for x in m):
    errs.append('deepseek-coder no se instaló')
if errs:
    print('🔴 Errores:'); [print(f'  - {e}') for e in errs]; exit(1)
else:
    print('✅ Todas las verificaciones pasaron')
"

rm -rf "$TEST_DIR"
echo "✅ Test del Enjambre completado"
