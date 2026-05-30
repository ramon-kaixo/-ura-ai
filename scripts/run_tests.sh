#!/bin/bash
cd ~/URA/ura_ia_1972
source .venv/bin/activate
if [ "${GX10_AVAILABLE:-false}" = "true" ]; then
    pytest --quiet --ignore=quarantine
else
    pytest --quiet --ignore=scripts/GX10 --ignore=quarantine
fi
