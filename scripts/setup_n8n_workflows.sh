#!/usr/bin/env bash
# setup_n8n_workflows.sh — Automatiza la importación de workflows en n8n
# Ejecutar en el servidor donde corre n8n.
# Crea el usuario owner si no existe e importa los workflows.
set -euo pipefail

N8N_URL="${N8N_URL:-http://localhost:5678}"
WORKFLOWS_DIR="$(dirname "$0")/../deploy/n8n"
COOKIE_FILE="/tmp/n8n_auth_cookie.txt"

echo "=== Setup n8n Workflows ==="
echo "URL: $N8N_URL"
echo "Workflows: $WORKFLOWS_DIR"
echo ""

# 1. Verificar que n8n está accesible
echo "[1/5] Verificando n8n..."
if ! curl -s "$N8N_URL/healthz" > /dev/null 2>&1; then
    echo "❌ n8n no accesible en $N8N_URL"
    exit 1
fi
echo "   ✅ n8n accesible"

# 2. Verificar si ya hay owner
echo "[2/5] Verificando owner..."
if curl -s "$N8N_URL/rest/owner/setup" -X GET > /dev/null 2>&1; then
    echo "   ℹ️  Owner ya configurado, intentando login..."
fi

# 3. Login o setup
echo "[3/5] Autenticando..."
if [ -f "$COOKIE_FILE" ]; then
    COOKIE=$(cat "$COOKIE_FILE")
else
    # Intentar login con credenciales por defecto
    LOGIN_RESP=$(curl -s "$N8N_URL/rest/login" \
        -H "Content-Type: application/json" \
        -d '{"emailOrLdapLoginId":"admin@ura.local","password":"Ura_1972"}')
    COOKIE=$(echo "$LOGIN_RESP" | python3 -c "import sys,json
try: print(json.load(sys.stdin)['data']['sessionCookie'])
except: print('')" 2>/dev/null)
    
    if [ -z "$COOKIE" ]; then
        echo "   ℹ️  Login falló. Intentando crear owner..."
        SETUP_RESP=$(curl -s "$N8N_URL/rest/owner/setup" \
            -H "Content-Type: application/json" \
            -d '{"email":"admin@ura.local","password":"Ura_1972","firstName":"URA","lastName":"Admin"}')
        COOKIE=$(echo "$SETUP_RESP" | python3 -c "import sys,json
try: print(json.load(sys.stdin)['data']['sessionCookie'])
except: print('')" 2>/dev/null)
        
        if [ -z "$COOKIE" ]; then
            echo "❌ No se pudo autenticar. Abre el navegador en $N8N_URL y configura el owner manualmente."
            echo "   Luego ejecuta: curl -X POST '$N8N_URL/rest/login' -H 'Content-Type: application/json' -d '{\"email\":\"admin@ura.local\",\"password\":\"TU_PASSWORD\"}'"
            exit 1
        fi
        echo "   ✅ Owner creado: admin@ura.local / Ura_1972"
    fi
    echo "$COOKIE" > "$COOKIE_FILE"
    echo "   ✅ Sesión iniciada"
fi

# 4. Importar workflows
echo "[4/5] Importando workflows..."
for wf in "$WORKFLOWS_DIR"/*.json; do
    name=$(basename "$wf")
    echo "   → $name..."
    
    # Leer workflow, añadir active: true y el userId correcto
    WF_JSON=$(cat "$wf" | python3 -c "
import sys,json
data = json.load(sys.stdin)
# Obtener userId de la sesión
data['active'] = True
print(json.dumps(data))
")
    
    RESP=$(curl -s "$N8N_URL/rest/workflows" \
        -H "Content-Type: application/json" \
        -H "Cookie: n8n-auth=$COOKIE" \
        -d "$WF_JSON")
    
    WF_ID=$(echo "$RESP" | python3 -c "import sys,json
try: print(json.load(sys.stdin).get('id','error'))
except: print('error')" 2>/dev/null)
    
    if [ "$WF_ID" != "error" ] && [ -n "$WF_ID" ]; then
        echo "     ✅ Importado (id=$WF_ID)"
    else
        echo "     ❌ Error: $(echo $RESP | head -c 200)"
    fi
done

# 5. Activar workflows
echo "[5/5] Activando workflows..."
for wf_id in $(curl -s "$N8N_URL/rest/workflows" \
    -H "Cookie: n8n-auth=$COOKIE" \
    | python3 -c "import sys,json
try:
    for w in json.load(sys.stdin).get('data',[]):
        if not w.get('active'): print(w['id'])
except: pass" 2>/dev/null); do
    echo "   Activando workflow $wf_id..."
    curl -s -X PATCH "$N8N_URL/rest/workflows/$wf_id" \
        -H "Content-Type: application/json" \
        -H "Cookie: n8n-auth=$COOKIE" \
        -d '{"active":true}' > /dev/null
done

echo ""
echo "✅ Setup completado!"
echo "   Accede a $N8N_URL con: admin@ura.local / Ura_1972"
