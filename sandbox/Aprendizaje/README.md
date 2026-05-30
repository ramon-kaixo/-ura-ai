# Sandbox 3 — Aprendizaje

**Función:** Memoria y embeddings del ecosistema
**Ubicación:** GX10 (Docker)
**Horario:** 12:00 y 18:00

## Herramientas
- `scripts/generar_embeddings.py` — Generación de embeddings para memoria semántica
- `scripts/indexar_memoria.py` — Indexación de documentos en FAISS/Chroma
- `scripts/procesar_documentos.py` — Procesamiento de nuevos documentos
- `scripts/entrenar_ligero.py` — Entrenamiento de modelos pequeños (LoRA)

## Flujo de ejecución
1. Escanear docs/ y logs/ en busca de contenido nuevo
2. Generar embeddings con el modelo de embeddings configurado
3. Indexar en la base de datos vectorial
4. Actualizar vectores obsoletos
5. Si hay suficientes datos nuevos → entrenar adaptador LoRA ligero

## Dependencias
- Modelo de embeddings (nomic-embed-text o similar)
- FAISS o ChromaDB
- Acceso a docs/ y logs/ del proyecto
