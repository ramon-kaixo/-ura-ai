#!/bin/bash
# Script para guardar documentación automáticamente

cd /Users/ramonesnaola/URA/ura_ia_1972

echo "Buscando documentación de IAs..."
python3 -c "from core.buscadores.buscador_documentacion import buscador_documentacion; buscador_documentacion.buscar_documentacion('DeepSeek API', 'ias')"
python3 -c "from core.buscadores.buscador_documentacion import buscador_documentacion; buscador_documentacion.buscar_documentacion('Gemini API', 'ias')"
python3 -c "from core.buscadores.buscador_documentacion import buscador_documentacion; buscador_documentacion.buscar_documentacion('Claude API', 'ias')"
python3 -c "from core.buscadores.buscador_documentacion import buscador_documentacion; buscador_documentacion.buscar_documentacion('Mistral API', 'ias')"

echo "Buscando documentación de herramientas..."
python3 -c "from core.buscadores.buscador_documentacion import buscador_documentacion; buscador_documentacion.buscar_documentacion('black', 'herramientas')"
python3 -c "from core.buscadores.buscador_documentacion import buscador_documentacion; buscador_documentacion.buscar_documentacion('isort', 'herramientas')"
python3 -c "from core.buscadores.buscador_documentacion import buscador_documentacion; buscador_documentacion.buscar_documentacion('ruff', 'herramientas')"
python3 -c "from core.buscadores.buscador_documentacion import buscador_documentacion; buscador_documentacion.buscar_documentacion('mypy', 'herramientas')"
python3 -c "from core.buscadores.buscador_documentacion import buscador_documentacion; buscador_documentacion.buscar_documentacion('bandit', 'herramientas')"
python3 -c "from core.buscadores.buscador_documentacion import buscador_documentacion; buscador_documentacion.buscar_documentacion('pylint', 'herramientas')"

echo "Buscando documentación de sistema..."
python3 -c "from core.buscadores.buscador_documentacion import buscador_documentacion; buscador_documentacion.buscar_documentacion('Docker', 'sistema')"
python3 -c "from core.buscadores.buscador_documentacion import buscador_documentacion; buscador_documentacion.buscar_documentacion('Redis', 'sistema')"
python3 -c "from core.buscadores.buscador_documentacion import buscador_documentacion; buscador_documentacion.buscar_documentacion('Ollama', 'sistema')"

echo "Buscando documentación de seguridad..."
python3 -c "from core.buscadores.buscador_documentacion import buscador_documentacion; buscador_documentacion.buscar_documentacion('auditoría', 'seguridad')"
python3 -c "from core.buscadores.buscador_documentacion import buscador_documentacion; buscador_documentacion.buscar_documentacion('compliance', 'seguridad')"

echo "Documentación guardada completada"
