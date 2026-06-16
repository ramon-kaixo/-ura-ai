import sys
from core.memory_engine import MemoryEngine

if len(sys.argv) < 2:
    print("Uso: python3 ura-query.py 'query de contexto'")
    sys.exit(1)

query_text = sys.argv[1]
me = MemoryEngine()
resultados = me.query(query_text, n_results=3)
print(resultados)
