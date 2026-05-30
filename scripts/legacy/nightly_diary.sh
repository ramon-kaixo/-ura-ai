#!/bin/bash
# Diario nocturno de URA - Se ejecuta cada día a las 23:59

cd /Users/ramonesnaola/URA/ura_ia_1972
source .venv/bin/activate

# Ejecutar diario nocturno
python -c "from core.ura_diary import get_ura_diary; get_ura_diary().escribir_entrada_diaria()"

echo "Diario nocturno de URA completado: $(date)"
