#!/bin/bash
# Configurar Cron Jobs para Mantenimiento Automático de Agentes de Código

# Cron jobs para agentes de código
# Mantenimiento diario a las 3:00 AM
echo "0 3 * * * cd /Users/ramonesnaola/URA/ura_ia_1972 && python3 scripts/code_agents_maintenance.py" | crontab -

# Limpieza de historial semanal (domingo a las 4:00 AM)
echo "0 4 * * 0 cd /Users/ramonesnaola/URA/ura_ia_1972 && python3 -c 'from core.code_agents.orchestrator import code_agents_orchestrator; print(\"Limpieza de historial\")'" | crontab -

# Verificar estado cada hora
echo "0 * * * * cd /Users/ramonesnaola/URA/ura_ia_1972 && python3 -c 'from core.code_agents.orchestrator import code_agents_orchestrator; print(code_agents_orchestrator.obtener_estado())'" | crontab -

echo "Cron jobs configurados para agentes de código"
crontab -l
