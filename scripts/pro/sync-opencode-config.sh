#!/usr/bin/env bash
# sync-opencode-config.sh — Sincroniza config de OpenCode entre Mac y GX10
# Gestiona 3 configs independientes: Mac Desktop, GX10 Desktop, GX10 Web
set -euo pipefail

GX10_IP="${GX10_IP:-100.72.103.12}"
MAC_CONFIG="$HOME/Library/Application Support/opencode/opencode.json"
GX10_DESKTOP="/home/ramon/.config/opencode/opencode.json"
GX10_WEB="/home/ramon/.config/opencode/opencode-web.json"
PROJECT_CONFIG="$(dirname "$0")/../../opencode.json"

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

FEATURES='{
  "snapshot": true,
  "share": "disabled",
  "compaction": {"auto": true, "tail_turns": 15},
  "formatter": true,
  "lsp": true,
  "experimental": {"openTelemetry": true, "batch_tool": true}
}'

REFS_MAC='{
  "docs": {"path": "/Users/ramonesnaola/URA/ura_ia_1972/docs", "description": "URA project documentation"},
  "arch": {"path": "/Users/ramonesnaola/URA/ura_ia_1972/docs/architecture", "description": "Architecture docs"},
  "udo": {"path": "/Users/ramonesnaola/URA/ura_ia_1972/docs/udo", "description": "UDO task system docs"}
}'

REFS_GX10='{
  "docs": {"path": "/home/ramon/URA/ura_ia_1972/docs", "description": "URA project documentation"},
  "arch": {"path": "/home/ramon/URA/ura_ia_1972/docs/architecture", "description": "Architecture docs"},
  "udo": {"path": "/home/ramon/URA/ura_ia_1972/docs/udo", "description": "UDO task system docs"}
}'

echo "=== Sync OpenCode Config (3 instances) ==="
echo "GX10 IP: $GX10_IP"

# 1. Mac Desktop
echo ""
echo "[1/4] Mac Desktop: $MAC_CONFIG"
python3 -c "
import json
cfg = {
    '\$schema': 'https://opencode.ai/config.json',
    **json.loads('''$FEATURES'''),
    'permission': json.loads('''$PERMISSIONS'''),
    'references': json.loads('''$REFS_MAC'''),
    'provider': {
        'ollama': {
            'npm': '@ai-sdk/openai-compatible',
            'name': 'Ollama',
            'options': {'baseURL': 'http://$GX10_IP:11434/v1'},
            'models': json.loads('''$MODELS''')
        }
    },
    'model': 'ollama/qwen3.6:27b',
    'default_agent': 'general',
    'username': 'ramon'
}
with open('$MAC_CONFIG', 'w') as f:
    json.dump(cfg, f, indent=2)
print('OK')
"

# 2. GX10 Desktop
echo ""
echo "[2/4] GX10 Desktop: $GX10_DESKTOP"
ssh ramon@$GX10_IP "python3 -c \"
import json
with open('$GX10_DESKTOP') as f:
    cfg = json.load(f)
cfg['permission'] = json.loads('''$PERMISSIONS''')
cfg['references'] = json.loads('''$REFS_GX10''')
cfg.update(json.loads('''$FEATURES'''))
cfg['provider']['ollama']['models'] = json.loads('''$MODELS''')
cfg['model'] = 'ollama/qwen3.6:27b'
cfg['default_agent'] = 'general'
cfg['username'] = 'ramon'
with open('$GX10_DESKTOP', 'w') as f:
    json.dump(cfg, f, indent=2)
print('OK')
\"" 2>&1

# 3. GX10 Web
echo ""
echo "[3/4] GX10 Web: $GX10_WEB"
ssh ramon@$GX10_IP "python3 -c \"
import json
cfg = {
    '\$schema': 'https://opencode.ai/config.json',
    **json.loads('''$FEATURES'''),
    'permission': json.loads('''$PERMISSIONS'''),
    'references': json.loads('''$REFS_GX10'''),
    'server': {'port': 8081, 'hostname': '0.0.0.0', 'mdns': True, 'mdnsDomain': 'ura-gx10.local'},
    'provider': {
        'opencode': {'disabled': False},
        'ollama': {
            'npm': '@ai-sdk/openai-compatible',
            'options': {'baseURL': 'http://localhost:11434/v1'},
            'models': json.loads('''$MODELS''')
        },
        'gemini': {'npm': '@ai-sdk/google', 'options': {'apiKey': '\$GEMINI_API_KEY'}, 'models': {'gemini-2.0-flash': {}}}
    },
    'model': 'ollama/qwen3-coder:30b',
    'default_agent': 'general',
    'username': 'ramon',
    'mcp': {
        'codewiki': {'type': 'local', 'command': ['/home/ramon/.npm-global/bin/codewiki-mcp'], 'enabled': True}
    }
}
with open('$GX10_WEB', 'w') as f:
    json.dump(cfg, f, indent=2)
print('OK')
\"" 2>&1

# 4. Project config
echo ""
echo "[4/4] Project: $PROJECT_CONFIG"
if [ -f "$PROJECT_CONFIG" ]; then
    python3 -c "
import json
with open('$PROJECT_CONFIG') as f:
    cfg = json.load(f)
cfg.update(json.loads('''$FEATURES'''))
cfg['permission'] = json.loads('''$PERMISSIONS''')
cfg['references'] = json.loads('''$REFS_MAC''')
with open('$PROJECT_CONFIG', 'w') as f:
    json.dump(cfg, f, indent=2)
print('OK')
"
else
    echo "Skipped (not found)"
fi

echo ""
echo "=== Done ==="
echo "Reinicia OpenCode en ambas máquinas."
echo ""
echo "GX10: Para apply web config, ejecuta:"
echo "  sudo systemctl daemon-reload && sudo systemctl restart opencode"
