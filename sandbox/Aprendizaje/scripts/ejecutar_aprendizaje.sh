#!/bin/bash
LOG="$(dirname "$0")/../logs/aprendizaje_$(date +%Y%m%d_%H%M).log"
echo "[$(date)] Iniciando ciclo de Aprendizaje..." | tee -a "$LOG"
cd ~/URA/ura_ia_1972
source .venv/bin/activate 2>/dev/null || true
python3 -c "
from pathlib import Path
docs = list(Path('docs').glob('*.md'))
print(f'  Documentos encontrados: {len(docs)}')
" 2>/dev/null | tee -a "$LOG"
echo "  [PENDIENTE] Embeddings — requiere modelo configurado" | tee -a "$LOG"
echo "  [PENDIENTE] Indexación — requiere FAISS/Chroma" | tee -a "$LOG"
echo "[$(date)] Ciclo de Aprendizaje completado" | tee -a "$LOG"
