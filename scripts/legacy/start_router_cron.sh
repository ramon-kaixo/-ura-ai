#!/bin/bash
# start_router_cron.sh — Wrapper para cron @reboot
# Se añade automáticamente al crontab del usuario
cd ~/URA/ura_ia_1972

# Verificar si ya está corriendo
if pgrep -f "llama_router.py" > /dev/null; then
    echo "$(date) - Router ya corriendo, no hacer nada" >> ~/URA/ura_ia_1972/logs/router_cron.log
    exit 0
fi

echo "$(date) - Iniciando router..." >> ~/URA/ura_ia_1972/logs/router_cron.log

export PYTHONPATH="$HOME/URA/ura_ia_1972:$PYTHONPATH"
export OLLAMA_MAX_LOADED_MODELS=4
nohup python3 ~/URA/ura_ia_1972/services/llama_router.py --models codestral-22b qwen2.5-coder-q8 qwen2.5-coder-32b >> ~/URA/ura_ia_1972/logs/llama_router.log 2>&1 &

echo "$(date) - Router PID: $!" >> ~/URA/ura_ia_1972/logs/router_cron.log
