#!/usr/bin/env bash
# sync-opencode-config.sh — Sincroniza config de Ollama entre Mac y GX10
# Ejecutar después de cambiar modelos o IP de GX10.
set -euo pipefail

GX10_IP="${GX10_IP:-100.72.103.12}"
MAC_CONFIG="$HOME/Library/Application Support/opencode/opencode.json"
MAC_GLOBAL="$HOME/.config/opencode/opencode.json"
GX10_CONFIG="/home/ramon/.config/opencode/opencode.json"
PROJECT_CONFIG=".opencode/project.json"

# Modelos base (edit aquí para añadir/quitar modelos)
MODELS='{
  "qwen3-coder:30b": { "tools": true, "reasoning": false, "limit": { "context": 262144, "output": 8192 } },
  "qwen3.6:27b": { "tools": true, "reasoning": true, "limit": { "context": 131072, "output": 8192 } },
  "llama3:latest": { "tools": true, "reasoning": false, "limit": { "context": 8192, "output": 4096 } },
  "llama3.3:70b": { "tools": true, "reasoning": true, "limit": { "context": 131072, "output": 8192 } },
  "gemma4:26b": { "tools": true, "reasoning": true, "limit": { "context": 131072, "output": 8192 } },
  "nemotron-3-nano:30b-a3b-q4_K_M": { "tools": true, "reasoning": true, "limit": { "context": 131072, "output": 8192 } },
  "nomic-embed-text:latest": { "tools": false, "reasoning": false, "limit": { "context": 2048, "output": 0 } }
}'

PERMISSIONS='{
  "read": "allow", "edit": "allow", "glob": "allow",
  "grep": "allow", "list": "allow", "bash": "allow",
  "task": "allow", "external_directory": "allow",
  "todowrite": "allow", "question": "allow",
  "webfetch": "allow", "websearch": "allow", "skill": "allow"
}'

echo "=== Sync OpenCode Config ==="
echo "GX10 IP: $GX10_IP"

# 1. Generate Mac Application Support config
echo ""
echo "Writing $MAC_CONFIG ..."
python3 -c "
import json, sys
cfg = {
    '\$schema': 'https://opencode.ai/config.json',
    'permission': json.loads('''$PERMISSIONS'''),
    'provider': {
        'ollama': {
            'npm': '@ai-sdk/openai-compatible',
            'name': 'Ollama',
            'options': {'baseURL': f'http://$GX10_IP:11434/v1'},
            'models': json.loads('''$MODELS''')
        }
    }
}
with open('$MAC_CONFIG', 'w') as f:
    json.dump(cfg, f, indent=2)
print('OK')
"

# 2. Generate Mac global config (minimal, no conflict)
echo "Writing $MAC_GLOBAL ..."
echo '{ "\$schema": "https://opencode.ai/config.json" }' > "$MAC_GLOBAL"
echo "OK"

# 3. Update GX10 config via SSH
echo ""
echo "Updating GX10 config ..."
ssh ramon@$GX10_IP "python3 -c \"
import json
with open('$GX10_CONFIG') as f:
    cfg = json.load(f)
cfg['permission'] = json.loads('''$PERMISSIONS''')
cfg['provider']['ollama']['models'] = json.loads('''$MODELS''')
with open('$GX10_CONFIG', 'w') as f:
    json.dump(cfg, f, indent=2)
print('OK')
\"" 2>&1

echo ""
echo "=== Done ==="
echo "Reinicia OpenCode en ambas máquinas para aplicar cambios."
