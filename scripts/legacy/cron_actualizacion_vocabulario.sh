#!/bin/bash
# Cron job para actualización semanal de vocabulario
# Ejecutar cada domingo a las 3:00 AM

cd /Users/ramonesnaola/URA/ura_ia_1972

# Ejecutar ingestor de instrucciones
python3 core/vocabulario/ingestor_instrucciones.py

# Guardar log
echo "Actualización de vocabulario completada: $(date)" >> /Users/ramonesnaola/URA/ura_ia_1972/logs/actualizacion_vocabulario.log
