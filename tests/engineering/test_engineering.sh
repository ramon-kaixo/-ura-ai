#!/bin/bash
# test_engineering.sh — Casos de prueba del Plan 0 §44 (casos 1-6: análisis de plan)
# Casos 7-10 (degradación, conflicto, alcance, mejora) → tests/udo/test_udo.sh (reutilizados)
# Uso: bash tests/engineering/test_engineering.sh
# Valida: la metodología (PLAN_TEMPLATE + PLAN_REVIEW_TEMPLATE) detecta
#         correcto / incompleto / contradictorio / fase futura / complejo / requisito oculto.

set -euo pipefail

DOCS="$(cd "$(dirname "$0")/../../docs/engineering" && pwd)"
TEMPLATE="$DOCS/PLAN_TEMPLATE.md"
REVIEW="$DOCS/PLAN_REVIEW_TEMPLATE.md"
ENGPROC="$DOCS/ENGINEERING_PROCESS.md"

PASS=0; FAIL=0; FAILED_NAMES=()
ok()  { PASS=$((PASS+1)); echo "  OK: $1"; }
bad() { FAIL=$((FAIL+1)); FAILED_NAMES+=("$1"); echo "  FAIL: $1"; }

echo "=== Engineering Process — casos de prueba Plan 0 §44 ==="

# --- Prerrequisitos: los 4 archivos de la metodología existen ---
[ -f "$TEMPLATE" ] && ok "PLAN_TEMPLATE existe" || bad "PLAN_TEMPLATE falta"
[ -f "$REVIEW" ]   && ok "PLAN_REVIEW_TEMPLATE existe" || bad "PLAN_REVIEW_TEMPLATE falta"
[ -f "$ENGPROC" ]  && ok "ENGINEERING_PROCESS existe" || bad "ENGINEERING_PROCESS falta"

# --- Caso 1: plan correcto → identificable como ejecutable (GO) ---
# El template exige las 11 secciones; un plan correcto las tiene todas.
SECS_REQ='QUÉ QUIERO CONSEGUIR|POR QUÉ|QUÉ CONTEXTO EXISTE|QUÉ TIENE QUE HACER|QUÉ ES MÍNIMO|QUÉ ES CRÍTICO|CÓMO DEBE COMPORTARSE|QUÉ NO DEBE HACER|QUÉ ESTÁ FUERA DE ALCANCE|CÓMO SE VALIDARÁ|CÓMO SE SABRÁ QUE ESTÁ TERMINADO'
count=$(grep -cE "$SECS_REQ" "$TEMPLATE")
[ "$count" -ge 11 ] && ok "Caso 1: template exige las 11 preguntas (§50) — plan completo → GO" || bad "Caso 1: template incompleto ($count/11)"

# --- Caso 2: plan incompleto → el template detecta lo que falta ---
# Un plan sin la sección NO HACER o sin criterios de cierre es detectable:
# el template define que "un plan sin estas secciones está incompleto".
grep -q "sin estas secciones está incompleto" "$TEMPLATE" \
    && ok "Caso 2: template declara plan incompleto sin las 11 secciones" || bad "Caso 2: no declara incompletitud"

# --- Caso 3: plan contradictorio → obligación 6 del proceso ---
grep -qi "buscar contradicciones" "$ENGPROC" && grep -qi "contradicciones" "$REVIEW" \
    && ok "Caso 3: obligación 6 (contradicciones) en proceso y revisión" || bad "Caso 3: contradicciones no cubiertas"

# --- Caso 4: plan con fase posterior → obligación 9 (trabajo prematuro) ---
grep -q "trabajo prematuro" "$ENGPROC" && grep -q "PERTENECE A OTRA FASE\|pertenece a otra fase" "$REVIEW" \
    && ok "Caso 4: obligación 9 (fase futura) en proceso y revisión" || bad "Caso 4: trabajo prematuro no cubierto"

# --- Caso 5: plan excesivamente complejo → anti-sobreingeniería (§20) ---
grep -q "más sencilla que cumpla todos los mínimos" "$ENGPROC" \
    && ok "Caso 5: regla anti-sobreingeniería presente (simplificación)" || bad "Caso 5: anti-sobreingeniería ausente"

# --- Caso 6: requisito oculto → obligación 4-5 (inspeccionar código, buscar lo que falta) ---
grep -qi "inspeccionar el código real" "$ENGPROC" && grep -qi "buscar lo que falta" "$ENGPROC" \
    && ok "Caso 6: obligaciones 4-5 (requisito oculto) presentes" || bad "Caso 6: inspección de código ausente"

# --- Regla central: ningún plan se ejecuta sin análisis previo ---
grep -qi "nunca se ejecuta" "$ENGPROC" \
    && ok "Regla central: análisis previo obligatorio" || bad "Regla central ausente"

# --- Veredictos GO / GO CON CAMBIOS / NO-GO ---
for v in "GO" "GO CON CAMBIOS" "NO-GO"; do
    grep -qF "$v" "$REVIEW" && ok "Veredicto: $v presente" || bad "Veredicto $v ausente"
done

echo ""
if [ "$FAIL" -gt 0 ]; then
    printf '  Fallos: %s\n' "${FAILED_NAMES[@]}"
    echo "RESULTADO: $PASS OK, $FAIL FAIL — ENGINEERING NO VALIDADO"
    exit 1
fi
echo "RESULTADO: $PASS OK, 0 FAIL — ENGINEERING VALIDADO"
