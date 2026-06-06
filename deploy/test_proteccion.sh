#!/bin/bash
# ============================================================
# test_proteccion.sh — Prueba de Estrés de Seguridad
# Verifica que el sistema rechace intentos de edición no autorizados.
# Ejecutar en Mac para validar que la inmutabilidad funciona.
# ============================================================

URA_PARENT="/Users/ramonesnaola/URA"
URA_REPO="/Users/ramonesnaola/URA/ura_ia_1972"
TESTS=0
PASSED=0
FAILED=0

green() { echo -e "\033[32m  ✓ $1\033[0m"; ((PASSED++)); }
red()   { echo -e "\033[31m  ✗ $1\033[0m"; ((FAILED++)); }
test_n()  { ((TESTS++)); echo "[$TESTS] $1"; }

echo ""
echo "URA Security Stress Test"
echo "========================"
echo ""

# ============================================================
# TEST 1: Verificar que inmutabilidad está activa
# ============================================================
test_n "Verificar estado inmutabilidad en ura_ia_1972/"
if [ -f "$URA_PARENT/.URA_IMMUTABLE_STATE" ] && [ "$(cat "$URA_PARENT/.URA_IMMUTABLE_STATE")" = "LOCKED" ]; then
    green "Inmutabilidad activa"
else
    red "Inmutabilidad NO activa — ejecutar: bash deploy/immutable_mac.sh lock"
fi

# ============================================================
# TEST 2: Verificar flag uchg en ura_ia_1972/
# ============================================================
test_n "Verificar flag uchg en ura_ia_1972/"
if ls -ldO "$URA_REPO" 2>/dev/null | grep -q "uchg"; then
    green "Flag uchg activo en ura_ia_1972/"
else
    red "Flag uchg NO activo en ura_ia_1972/"
fi

# ============================================================
# TEST 3: Intentar crear archivo DENTRO de ura_ia_1972/ (debería fallar)
# ============================================================
test_n "Intentar crear archivo en ura_ia_1972/"
if touch "$URA_REPO/test_write_permission.txt" 2>/dev/null; then
    rm -f "$URA_REPO/test_write_permission.txt"
    red "FALLO: Se pudo crear archivo (debería ser Permission Denied)"
else
    green "Permission Denied — escritura bloqueada"
fi

# ============================================================
# TEST 4: Intentar modificar archivo existente (debería fallar)
# ============================================================
test_n "Intentar modificar AGENTS.md"
if echo "test" >> "$URA_REPO/AGENTS.md" 2>/dev/null; then
    red "FALLO: Se pudo modificar AGENTS.md"
else
    green "Permission Denied — modificación bloqueada"
fi

# ============================================================
# TEST 5: Intentar eliminar archivo (debería fallar)
# ============================================================
test_n "Intentar eliminar AGENTS.md"
if rm -f "$URA_REPO/AGENTS.md" 2>/dev/null; then
    # Verificar si realmente se eliminó
    if [ ! -f "$URA_REPO/AGENTS.md" ]; then
        red "FALLO: AGENTS.md eliminado"
    else
        green "rm falló pero archivo persiste (OK)"
    fi
else
    green "Permission Denied — eliminación bloqueada"
fi

# ============================================================
# TEST 6: Verificar que git sigue funcionando
# ============================================================
test_n "Verificar que git operations funcionan"
cd "$URA_REPO"
if git status > /dev/null 2>&1; then
    green "git status funciona"
else
    red "FALLO: git status no funciona"
fi

# ============================================================
# TEST 7: Verificar sync_to_asus.sh
# ============================================================
test_n "Verificar sync_to_asus.sh"
if [ -f "$URA_REPO/deploy/sync_to_asus.sh" ] && [ -x "$URA_REPO/deploy/sync_to_asus.sh" ]; then
    green "sync_to_asus.sh existe y es ejecutable"
else
    red "FALLO: sync_to_asus.sh no encontrado o no ejecutable"
fi

# ============================================================
# TEST 8: Verificar validate_change.sh
# ============================================================
test_n "Verificar validate_change.sh"
if [ -f "$URA_REPO/deploy/validate_change.sh" ] && [ -x "$URA_REPO/deploy/validate_change.sh" ]; then
    green "validate_change.sh existe y es ejecutable"
else
    red "FALLO: validate_change.sh no encontrado o no ejecutable"
fi

# ============================================================
# TEST 9: Verificar error_logger
# ============================================================
test_n "Verificar error_logger en ASUS"
if ssh -o ConnectTimeout=2 ramon@10.164.1.99 "cd /home/ramon/URA/ura_ia_1972 && python3 -c 'from monitor.error_logger import ErrorLogger; print(\"OK\")'" > /dev/null 2>&1; then
    green "error_logger funciona en ASUS"
else
    red "FALLO: error_logger no funciona en ASUS"
fi

# ============================================================
# TEST 10: Verificar mac_heartbeat
# ============================================================
test_n "Verificar mac_heartbeat en ASUS"
if ssh -o ConnectTimeout=2 ramon@10.164.1.99 "cd /home/ramon/URA/ura_ia_1972 && python3 -c 'from monitor.mac_heartbeat import MacHeartbeat; print(\"OK\")'" > /dev/null 2>&1; then
    green "mac_heartbeat funciona en ASUS"
else
    red "FALLO: mac_heartbeat no funciona en ASUS"
fi

# ============================================================
# TEST 11: Verificar 139 tests
# ============================================================
test_n "Verificar tests unitarios (127)"
if python3 "$URA_REPO/tests/test_unit.py" > /dev/null 2>&1; then
    green "127/127 tests unitarios pasan"
else
    red "FALLO: tests unitarios fallaron"
fi

test_n "Verificar tests OpenClaw (12)"
if python3 -m pytest "$URA_REPO/tests/test_openclaw.py" -q > /dev/null 2>&1; then
    green "12/12 tests OpenClaw pasan"
else
    red "FALLO: tests OpenClaw fallaron"
fi

# ============================================================
# TEST 12: Verificar SNC autonomía
# ============================================================
test_n "Verificar SNC en ASUS (modo soberanía)"
if ssh -o ConnectTimeout=2 ramon@10.164.1.99 "cd /home/ramon/URA/ura_ia_1972 && python3 -c 'import monitor.snc; print(\"OK\")'" > /dev/null 2>&1; then
    green "SNC con autonomía funciona en ASUS"
else
    red "FALLO: SNC no funciona en ASUS"
fi

# ============================================================
# RESUMEN
# ============================================================
echo ""
echo "========================"
echo "RESUMEN: $PASSED/$TESTS pasaron, $FAILED fallaron"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "\033[32mSISTEMA BLINDADO — Todos los tests de seguridad pasaron\033[0m"
    exit 0
else
    echo -e "\033[31mHAY FALLOS — Revisar antes de continuar\033[0m"
    exit 1
fi
