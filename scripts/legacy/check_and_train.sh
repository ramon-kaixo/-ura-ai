#!/bin/bash
# Script llamado por cron cada noche a las 03:00
cd /Users/ramonesnaola/URA/ura_ia_1972
python -c "from core.training_gatekeeper import TrainingGatekeeper; result = TrainingGatekeeper().activate_if_ready(); print(result)"
