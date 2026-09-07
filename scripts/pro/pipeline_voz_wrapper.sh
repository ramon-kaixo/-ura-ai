#!/bin/bash
# Wait for PipeWire to be ready
for i in {1..30}; do
    if systemctl --user is-active pipewire >/dev/null 2>&1; then
        break
    fi
    sleep 1
done

exec /usr/bin/python3 /home/ramon/URA/ura_ia_1972/scripts/pro/pipeline_voz.py
