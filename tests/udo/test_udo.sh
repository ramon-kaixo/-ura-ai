#!/bin/bash
# Test UDO (F1+F2) — escenarios del plan de arreglo (Fase 7)
# Uso: bash tests/udo/test_udo.sh
# Usa UDO_ROOT temporal + repo real para git (solo lectura).
# Sin pytest: script bash autónomo, sin dependencias nuevas.

set -uo pipefail

REPO=/home/ramon/URA/ura_ia_1972
UDO="$REPO/scripts/pro/ura-udo"
WORK=/tmp/opencode/udo-tests
UDO_ROOT="$WORK/udo"

PASS=0; FAIL=0; FAILED_NAMES=()

ok()   { PASS=$((PASS+1)); echo "  OK: $1"; }
bad()  { FAIL=$((FAIL+1)); FAILED_NAMES+=("$1"); echo "  FAIL: $1"; }

# --- limpieza y setup
rm -rf "$WORK"; mkdir -p "$UDO_ROOT/tasks"

# helper: crea tarea y devuelve ID
new_task() {
    UDO_ROOT="$UDO_ROOT" UDO_REPO="$REPO" "$UDO" create "$1" | grep -o -m1 'TASK-[0-9-]*' | head -1
}

echo "=== UDO F1/F2 — suite de escenarios ==="

# 1. Creación con IDs únicos
echo "-- 1. IDs únicos"
A=$(new_task "Test A")
B=$(new_task "Test B")
[ -n "$A" ] && [ "$A" != "$B" ] && ok "IDs únicos ($A, $B)" || bad "IDs únicos"

# 2. Estado inicial PLANNED
echo "-- 2. Estado inicial"
UDO_ROOT="$UDO_ROOT" UDO_REPO="$REPO" "$UDO" show "$A" | grep -q '^estado: PLANNED' && ok "PLANNED inicial" || bad "PLANNED inicial"

# 3. IN_PROGRESS + commit_base automático
echo "-- 3. commit_base automático"
UDO_ROOT="$UDO_ROOT" UDO_REPO="$REPO" "$UDO" update "$A" --estado IN_PROGRESS --reserva "zona_a/foo.py" --nota "inicio" >/dev/null
base=$(UDO_ROOT="$UDO_ROOT" UDO_REPO="$REPO" "$UDO" show "$A" | grep '^commit_base:' | cut -d' ' -f2-)
[ -n "$base" ] && [ "$base" != "unknown" ] && ok "commit_base=$base" || bad "commit_base=$base"

# 4. Reserva permitida (zona distinta)
echo "-- 4. Reserva permitida (zona distinta)"
UDO_ROOT="$UDO_ROOT" UDO_REPO="$REPO" "$UDO" update "$B" --estado IN_PROGRESS --reserva "zona_b/other.py" --nota "inicio B" >/dev/null && ok "B reserva zona_b" || bad "B reserva zona_b"

# 5. Reserva BLOQUEADA: B intenta X ya reservado por A
echo "-- 5. Reserva bloqueada (enforcement)"
out=$(UDO_ROOT="$UDO_ROOT" UDO_REPO="$REPO" "$UDO" reserve "$B" --add "zona_a/foo.py" 2>&1); rc=$?
[ "$rc" -ne 0 ] && echo "$out" | grep -q "está reservada por $A" && ok "B bloqueada por A" || bad "B bloqueada por A (rc=$rc: $out)"

# 6. update --reserva también bloquea
echo "-- 6. update --reserva bloquea"
out=$(UDO_ROOT="$UDO_ROOT" UDO_REPO="$REPO" "$UDO" update "$B" --reserva "zona_a/foo.py" --nota "intento" 2>&1); rc=$?
[ "$rc" -ne 0 ] && ok "update bloquea" || bad "update bloquea (rc=$rc)"

# 7. --force autoriza (excepción expresa auditada)
echo "-- 7. --force autoriza"
UDO_ROOT="$UDO_ROOT" UDO_REPO="$REPO" "$UDO" reserve "$B" --add "zona_a/foo.py" --force >/dev/null 2>&1 && ok "--force autoriza" || bad "--force autoriza"
UDO_ROOT="$UDO_ROOT" UDO_REPO="$REPO" "$UDO" reserve "$B" --clear >/dev/null

# 8. check detector de conflicto
echo "-- 8. check CONFLICTO"
UDO_ROOT="$UDO_ROOT" UDO_REPO="$REPO" "$UDO" check zona_a/foo.py | grep -q "CONFLICTO.*$A" && ok "check detecta" || bad "check detecta"

# 9. check sin conflicto
echo "-- 9. check OK"
UDO_ROOT="$UDO_ROOT" UDO_REPO="$REPO" "$UDO" check zona_b/other.py | grep -q "^OK:" && ok "check OK" || bad "check OK"

# 10. CASO B: DONE sin REVIEW rechazado
echo "-- 10. DONE solo desde REVIEW (CASO B)"
out=$(UDO_ROOT="$UDO_ROOT" UDO_REPO="$REPO" "$UDO" update "$A" --estado DONE --nota "sin revisión" 2>&1); rc=$?
[ "$rc" -ne 0 ] && echo "$out" | grep -q "DONE solo desde REVIEW" && ok "DONE sin REVIEW bloqueado" || bad "DONE sin REVIEW bloqueado (rc=$rc)"

# 11. DONE legítimo: gate de integridad F2.2 (repo git temporal)
echo "-- 11. DONE con gate de integridad"
REPO_T="$WORK/repo_t"
mkdir -p "$REPO_T"
git init -q "$REPO_T" && git -C "$REPO_T" config user.email test@udo && git -C "$REPO_T" config user.name test
echo base > "$REPO_T/base.txt" && git -C "$REPO_T" add . && git -C "$REPO_T" commit -qm "base"
C=$(UDO_ROOT="$UDO_ROOT" UDO_REPO="$REPO_T" "$UDO" create "Test gate" | grep -o -m1 'TASK-[0-9-]*' | head -1)
UDO_ROOT="$UDO_ROOT" UDO_REPO="$REPO_T" "$UDO" update "$C" --estado IN_PROGRESS --reserva "zona_c/trabajo.py" >/dev/null
mkdir -p "$REPO_T/zona_c"
echo "trabajo" > "$REPO_T/zona_c/trabajo.py"
git -C "$REPO_T" add . && git -C "$REPO_T" commit -qm "[$C][TERM] trabajo de prueba"
UDO_ROOT="$UDO_ROOT" UDO_REPO="$REPO_T" "$UDO" verify "$C" >/dev/null 2>&1
UDO_ROOT="$UDO_ROOT" UDO_REPO="$REPO_T" "$UDO" update "$C" --estado REVIEW --nota "revisado" >/dev/null
UDO_ROOT="$UDO_ROOT" UDO_REPO="$REPO_T" "$UDO" update "$C" --estado DONE --analisis "Objetivo claro; contexto verificado; sin contradicciones" --validacion "suite 30/30" --nota "cierre con gate" >/dev/null && ok "DONE con gate superado" || bad "DONE con gate superado"
UDO_ROOT="$UDO_ROOT" UDO_REPO="$REPO_T" "$UDO" show "$C" | grep -q "AUTO-REVISIÓN" && ok "AUTO-REVISIÓN sin revisor" || bad "AUTO-REVISIÓN sin revisor"

# 11b. Gate: DONE sin commits registrados rechazado (verify previo exigido)
echo "-- 11b. Gate: DONE sin verify rechazado"
UDO_ROOT="$UDO_ROOT" UDO_REPO="$REPO" "$UDO" update "$A" --estado REVIEW --nota "a revisión sin trabajo" >/dev/null
out=$(UDO_ROOT="$UDO_ROOT" UDO_REPO="$REPO" "$UDO" update "$A" --estado DONE --nota "sin verify" 2>&1); rc=$?
[ "$rc" -ne 0 ] && echo "$out" | grep -q "DONE requiere commits registrados" && ok "gate bloquea sin commits" || bad "gate bloquea sin commits (rc=$rc)"

# 11c. Gate: SHA no ancestral (historia reescrita) rechazado
echo "-- 11c. Gate: SHA reescrito rechazado"
D2=$(UDO_ROOT="$UDO_ROOT" UDO_REPO="$REPO_T" "$UDO" create "Test rewrite" | grep -o -m1 'TASK-[0-9-]*' | head -1)
UDO_ROOT="$UDO_ROOT" UDO_REPO="$REPO_T" "$UDO" update "$D2" --estado IN_PROGRESS >/dev/null
echo "v1" > "$REPO_T/d2.txt" && git -C "$REPO_T" add . && git -C "$REPO_T" commit -qm "[$D2][TERM] v1"
UDO_ROOT="$UDO_ROOT" UDO_REPO="$REPO_T" "$UDO" verify "$D2" >/dev/null 2>&1
git -C "$REPO_T" reset -q --hard HEAD~1
echo "v2" > "$REPO_T/d2.txt" && git -C "$REPO_T" add . && git -C "$REPO_T" commit -qm "[$D2][TERM] v2 reescrita"
UDO_ROOT="$UDO_ROOT" UDO_REPO="$REPO_T" "$UDO" update "$D2" --estado REVIEW >/dev/null 2>&1
out=$(UDO_ROOT="$UDO_ROOT" UDO_REPO="$REPO_T" "$UDO" update "$D2" --estado DONE --nota "cierre" 2>&1); rc=$?
[ "$rc" -ne 0 ] && echo "$out" | grep -q "no es ancestro de HEAD" && ok "gate bloquea SHA reescrito" || bad "gate bloquea SHA reescrito (rc=$rc)"

# 11d. Revisión cruzada: --revisor distinto del ejecutor (sin AUTO-REVISIÓN)
echo "-- 11d. Revisión cruzada"
E=$(UDO_ROOT="$UDO_ROOT" UDO_REPO="$REPO_T" "$UDO" create "Test revisor" | grep -o -m1 'TASK-[0-9-]*' | head -1)
UDO_ROOT="$UDO_ROOT" UDO_REPO="$REPO_T" "$UDO" update "$E" --estado IN_PROGRESS --agente_terminal "TERM (ejecutor)" >/dev/null
echo "x" > "$REPO_T/e.txt" && git -C "$REPO_T" add . && git -C "$REPO_T" commit -qm "[$E][TERM] trabajo"
UDO_ROOT="$UDO_ROOT" UDO_REPO="$REPO_T" "$UDO" verify "$E" >/dev/null 2>&1
UDO_ROOT="$UDO_ROOT" UDO_REPO="$REPO_T" "$UDO" update "$E" --estado REVIEW >/dev/null
UDO_ROOT="$UDO_ROOT" UDO_REPO="$REPO_T" "$UDO" update "$E" --estado DONE --analisis "a" --validacion "v" --revisor "WEB" --nota "cierre" >/dev/null && ok "DONE con revisor WEB" || bad "DONE con revisor WEB"
UDO_ROOT="$UDO_ROOT" UDO_REPO="$REPO_T" "$UDO" show "$E" | grep -q "revisión por WEB" && ok "revisión por WEB registrada" || bad "revisión por WEB registrada"
! UDO_ROOT="$UDO_ROOT" UDO_REPO="$REPO_T" "$UDO" show "$E" | grep -q "AUTO-REVISIÓN" && ok "sin marca AUTO-REVISIÓN" || bad "sin marca AUTO-REVISIÓN"

# 11e. Gate PLAN 1 A1: DONE sin analisis: rechazado (tarea post-parche)
echo "-- 11e. Gate: DONE sin analisis rechazado"
F=$(UDO_ROOT="$UDO_ROOT" UDO_REPO="$REPO_T" "$UDO" create "Test analisis" | grep -o -m1 'TASK-[0-9-]*' | head -1)
UDO_ROOT="$UDO_ROOT" UDO_REPO="$REPO_T" "$UDO" update "$F" --estado IN_PROGRESS >/dev/null
echo "t" > "$REPO_T/f.txt" && git -C "$REPO_T" add . && git -C "$REPO_T" commit -qm "[$F][TERM] trabajo"
UDO_ROOT="$UDO_ROOT" UDO_REPO="$REPO_T" "$UDO" verify "$F" >/dev/null 2>&1
UDO_ROOT="$UDO_ROOT" UDO_REPO="$REPO_T" "$UDO" update "$F" --estado REVIEW >/dev/null 2>&1
out=$(UDO_ROOT="$UDO_ROOT" UDO_REPO="$REPO_T" "$UDO" update "$F" --estado DONE --validacion "x" --nota "sin analisis" 2>&1); rc=$?
[ "$rc" -ne 0 ] && echo "$out" | grep -q "requiere analisis" && ok "gate bloquea DONE sin analisis" || bad "gate bloquea DONE sin analisis (rc=$rc)"

# 11f. Gate PLAN 1 A2: DONE sin validacion: rechazado (tarea limpia)
echo "-- 11f. Gate: DONE sin validacion rechazado"
F2=$(UDO_ROOT="$UDO_ROOT" UDO_REPO="$REPO_T" "$UDO" create "Test validacion" | grep -o -m1 'TASK-[0-9-]*' | head -1)
UDO_ROOT="$UDO_ROOT" UDO_REPO="$REPO_T" "$UDO" update "$F2" --estado IN_PROGRESS >/dev/null
echo "t2" > "$REPO_T/f2.txt" && git -C "$REPO_T" add . && git -C "$REPO_T" commit -qm "[$F2][TERM] trabajo2"
UDO_ROOT="$UDO_ROOT" UDO_REPO="$REPO_T" "$UDO" verify "$F2" >/dev/null 2>&1
UDO_ROOT="$UDO_ROOT" UDO_REPO="$REPO_T" "$UDO" update "$F2" --estado REVIEW >/dev/null 2>&1
out=$(UDO_ROOT="$UDO_ROOT" UDO_REPO="$REPO_T" "$UDO" update "$F2" --estado DONE --analisis "analizado" --nota "sin validacion" 2>&1); rc=$?
[ "$rc" -ne 0 ] && echo "$out" | grep -q "requiere validacion" && ok "gate bloquea DONE sin validacion" || bad "gate bloquea DONE sin validacion (rc=$rc)"

# 11g. DONE con analisis+validacion supera el gate; campos registrados
echo "-- 11g. DONE con analisis+validacion"
UDO_ROOT="$UDO_ROOT" UDO_REPO="$REPO_T" "$UDO" update "$F2" --estado DONE --analisis "analizado" --validacion "suite OK" --nota "cierre" >/dev/null && ok "DONE con ambos campos" || bad "DONE con ambos campos"
UDO_ROOT="$UDO_ROOT" UDO_REPO="$REPO_T" "$UDO" show "$F2" | grep -q "^analisis: analizado" && ok "analisis registrado" || bad "analisis registrado"
UDO_ROOT="$UDO_ROOT" UDO_REPO="$REPO_T" "$UDO" show "$F2" | grep -q "^validacion: suite OK" && ok "validacion registrada" || bad "validacion registrada"

# 12. Liberación automática: C ya DONE no protege; B puede reservar zona_c
echo "-- 12. Liberación al cierre"
UDO_ROOT="$UDO_ROOT" UDO_REPO="$REPO" "$UDO" reserve "$B" --add "zona_c/trabajo.py" >/dev/null 2>&1 && ok "zona_c liberada tras DONE" || bad "zona_c liberada tras DONE"
UDO_ROOT="$UDO_ROOT" UDO_REPO="$REPO" "$UDO" reserve "$B" --clear >/dev/null

# 13. Campos canónicos antes de historial
echo "-- 13. Estructura canónica"
line=$(UDO_ROOT="$UDO_ROOT" UDO_REPO="$REPO" "$UDO" show "$B" | grep -n '^historial:' | cut -d: -f1)
aweb=$(UDO_ROOT="$UDO_ROOT" UDO_REPO="$REPO" "$UDO" show "$B" | grep -n '^agente_web:' | cut -d: -f1)
[ -n "$line" ] && [ -n "$aweb" ] && [ "$aweb" -lt "$line" ] && ok "campos antes de historial" || bad "campos antes de historial ($aweb vs $line)"

# 14. context + ura-ask
echo "-- 14. Contexto compartido"
ctx_out=$(UDO_ROOT="$UDO_ROOT" UDO_REPO="$REPO" "$UDO" context "$B" 2>/dev/null) && echo "$ctx_out" | grep -q "^=== CONTEXTO UDO — $B ===" && ok "ura-udo context" || bad "ura-udo context"
ask_out=$(UDO_ROOT="$UDO_ROOT" UDO_REPO="$REPO" bash "$REPO/scripts/pro/ura-ask" "$B" 2>/dev/null) && echo "$ask_out" | grep -q "^=== CONTEXTO UDO — $B ===" && ok "ura-ask wrapper" || bad "ura-ask wrapper"

# 15. Concurrencia: 10 creaciones paralelas → IDs únicos
echo "-- 15. Concurrencia (flock)"
for i in $(seq 1 10); do
    ( UDO_ROOT="$UDO_ROOT" UDO_REPO="$REPO" "$UDO" create "paralela $i" >/dev/null ) &
done
wait
total=$(ls "$UDO_ROOT/tasks"/*.md | wc -l)
unicos=$(ls "$UDO_ROOT/tasks"/*.md | xargs -n1 basename | cut -d. -f1 | sort -u | wc -l)
[ "$total" -eq "$unicos" ] && ok "10 IDs únicos ($total)" || bad "IDs únicos en concurrencia ($total vs $unicos)"

# 16. Estado inválido rechazado
echo "-- 16. Estado inválido"
UDO_ROOT="$UDO_ROOT" UDO_REPO="$REPO" "$UDO" update "$B" --estado INEXISTENTE >/dev/null 2>&1 && bad "estado inválido" || ok "estado inválido rechazado"

# 17. Compatibilidad F1: tarea sin commit_base en IN_PROGRESS se autorellena
echo "-- 17. Compatibilidad F1"
C=$(new_task "Test F1")
sed -i 's/^commit_base: .*/commit_base: /' "$UDO_ROOT/tasks/$C.md"
UDO_ROOT="$UDO_ROOT" UDO_REPO="$REPO" "$UDO" update "$C" --estado IN_PROGRESS >/dev/null
base2=$(UDO_ROOT="$UDO_ROOT" UDO_REPO="$REPO" "$UDO" show "$C" | grep '^commit_base:' | cut -d' ' -f2-)
[ -n "$base2" ] && ok "commit_base auto en tarea F1 ($base2)" || bad "commit_base auto en tarea F1"

# 18. verify tolera tarea sin commits (WARNING, no error)
echo "-- 18. verify degradado"
UDO_ROOT="$UDO_ROOT" UDO_REPO="$REPO" "$UDO" verify "$C" >/dev/null 2>&1 && ok "verify sin commits" || bad "verify sin commits"

# 19. --force queda auditado en historial (trazabilidad del override)
echo "-- 19. --force auditado"
D=$(new_task "Test force audit")
UDO_ROOT="$UDO_ROOT" UDO_REPO="$REPO" "$UDO" update "$D" --estado IN_PROGRESS --reserva "zona_force/x.py" >/dev/null
UDO_ROOT="$UDO_ROOT" UDO_REPO="$REPO" "$UDO" reserve "$D" --add "zona_a/foo.py" --force >/dev/null 2>&1
UDO_ROOT="$UDO_ROOT" UDO_REPO="$REPO" "$UDO" show "$D" | grep -q "AUTORIZACIÓN EXPRESA --force" && ok "--force marcado en historial" || bad "--force marcado en historial"
UDO_ROOT="$UDO_ROOT" UDO_REPO="$REPO" "$UDO" update "$D" --reserva "zona_force/y.py,zona_a/foo.py" --force >/dev/null 2>&1
UDO_ROOT="$UDO_ROOT" UDO_REPO="$REPO" "$UDO" show "$D" | grep -q "AUTORIZACIÓN EXPRESA (--force)" && ok "--force marcado en update" || bad "--force marcado en update"
UDO_ROOT="$UDO_ROOT" UDO_REPO="$REPO" "$UDO" update "$D" --estado DONE --force >/dev/null 2>&1
UDO_ROOT="$UDO_ROOT" UDO_REPO="$REPO" "$UDO" show "$D" | grep -q "AUTORIZACIÓN EXPRESA (--force)" && ok "--force marcado en DONE forzado" || bad "--force marcado en DONE forzado"

# 20. instrucciones/restricciones propagadas en update y context
echo "-- 20. instrucciones/restricciones"
UDO_ROOT="$UDO_ROOT" UDO_REPO="$REPO" "$UDO" update "$D" --instrucciones "Refactor X" --restricciones "no tocar motor/" >/dev/null
ctx_out=$(UDO_ROOT="$UDO_ROOT" UDO_REPO="$REPO" "$UDO" context "$D" 2>/dev/null) || true
echo "$ctx_out" | grep -q 'instrucciones: Refactor X' && ok "instrucciones en context" || bad "instrucciones en context"
echo "$ctx_out" | grep -q 'restricciones: no tocar motor/' && ok "restricciones en context" || bad "restricciones en context"

echo ""
echo "=============================================="
echo "RESULTADO: $PASS OK, $FAIL FAIL"
if [ "$FAIL" -gt 0 ]; then
    printf '  Fallos: %s\n' "${FAILED_NAMES[@]}"
    exit 1
fi
echo "SUITE UDO: TODOS LOS ESCENARIOS PASAN"
exit 0
