#!/bin/bash
set -euo pipefail
REPO=/workspace
INBOX_DIR="$REPO/inbox"
TEST_FILE="$REPO/test_e2e_dummy.py"
REGISTRY_URL="http://host.docker.internal:5100/agents"
mkdir -p "$INBOX_DIR"
cd "$REPO"

cat > "$TEST_FILE" << 'PYEOF'
#!/usr/bin/env python3
import time
agent_id = "test_e2e_dummy"
agent_type = "test"
agent_ip = "127.0.0.1"
agent_port = 19999
def dummy_agent():
    return {"status": "ok", "timestamp": time.time()}
PYEOF

cp "$TEST_FILE" "$INBOX_DIR/"
echo 'Archivo depositado en inbox/'
for i in $(seq 1 4); do
    sleep 30
    [ ! -f "${INBOX_DIR}/test_e2e_dummy.py" ] && break
    echo "Intento $i/4..."
done
if [ -f "${INBOX_DIR}/test_e2e_dummy.py" ]; then echo 'TIMEOUT'; exit 1; fi
if [ -f "$REPO/agents/test_e2e_dummy.py" ]; then echo 'OK: movido a agents/'; else echo 'FAIL'; exit 1; fi
rm -f "$REPO/agents/test_e2e_dummy.py" "$TEST_FILE"
echo 'TEST E2E COMPLETADO'
