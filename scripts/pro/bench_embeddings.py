#!/usr/bin/env python3
"""Benchmark de embeddings: nomic-embed-text vs bge-m3 con 10 consultas anotadas."""
import sys
import time
import json
from pathlib import Path

sys.path.insert(0, "/home/ramon/URA/ura_ia_1972")

import httpx
from qdrant_client import QdrantClient, models

QDRANT = QdrantClient("127.0.0.1", port=6333)
OLLAMA = "http://127.0.0.1:11434/api/embeddings"
COLLECTION = "ideas_bench"


def embed(text: str, model: str = "nomic-embed-text:latest") -> list[float]:
    r = httpx.post(OLLAMA, json={"model": model, "prompt": text}, timeout=30)
    return r.json()["embedding"]


# 10 annotated queries with expected answer keywords
CONSULTAS = [
    {"query": "herramientas gratis para disenar menus", "esperado": ["Canva", "Adobe Express", "gratis"]},
    {"query": "tendencias en carteles 2026", "esperado": ["QR", "digital", "foto"]},
    {"query": "como automatizar la creacion de carteles", "esperado": ["API", "automatizar", "plantillas"]},
    {"query": "programacion asincrona en Python", "esperado": ["asyncio", "coroutines", "async"]},
    {"query": "alternativas a Adobe para diseno", "esperado": ["gratis", "freemium", "Canva"]},
    {"query": "que es asyncio", "esperado": ["I/O", "concurrente", "async"]},
    {"query": "menus con codigo QR", "esperado": ["QR", "digital", "tendencia"]},
    {"query": "manejo de tareas I/O en Python", "esperado": ["asyncio", "I/O-bound", "coroutines"]},
    {"query": "herramientas de diseno con marca de agua", "esperado": ["Adobe Express", "freemium", "marca"]},
    {"query": "framework para APIs rapidas Python", "esperado": ["FastAPI", "API", "asincronas"]},
]


def evaluate(model: str) -> dict:
    print(f"\n{'='*50}")
    print(f"  Benchmark: {model}")
    print(f"{'='*50}")

    # Clear test collection
    try:
        QDRANT.delete_collection(COLLECTION)
    except Exception:
        pass
    QDRANT.create_collection(COLLECTION, vectors_config=models.VectorParams(size=768, distance=models.Distance.COSINE))

    # Seed: same 4 ideas we use everywhere
    ideas_text = [
        ("Canva permite crear menus gratis con plantillas y tiene API para automatizar", "carteles", ["menus", "diseno", "automatizacion"], "herramienta", "Canva", "gratis"),
        ("Tendencia 2026: menus digitales con codigo QR y fotos grandes", "carteles", ["menus", "QR", "tendencias"], "tendencia", "", ""),
        ("Adobe Express ofrece menus gratis con marca de agua", "carteles", ["menus", "diseno"], "herramienta", "Adobe Express", "freemium"),
        ("FastAPI es el framework para APIs asincronas en Python", "programacion", ["FastAPI", "Python", "API"], "tecnica", "", ""),
    ]

    points = []
    for i, (idea_text, tema, etiquetas, tipo, h, c) in enumerate(ideas_text):
        vec = embed(f"{idea_text} {tema} {' '.join(etiquetas)}", model)
        points.append(models.PointStruct(id=i + 1, vector=vec, payload={
            "idea": idea_text, "tema": tema, "etiquetas": etiquetas,
            "tipo": tipo, "herramienta": h, "coste": c,
        }))
    QDRANT.upsert(COLLECTION, points)

    # Run queries
    total = len(CONSULTAS)
    hits = 0
    scores = []
    elapsed = 0.0

    for c in CONSULTAS:
        t0 = time.time()
        vec = embed(c["query"], model)
        results = QDRANT.query_points(COLLECTION, query=vec, limit=5)
        elapsed += time.time() - t0

        top_ideas = [p.payload.get("idea", "") for p in results.points[:3]]
        score_hit = False
        for kw in c["esperado"]:
            for idea in top_ideas:
                if kw.lower() in idea.lower():
                    score_hit = True
                    break
        if score_hit:
            hits += 1
        top_score = results.points[0].score if results.points else 0
        scores.append(top_score)

    avg_score = sum(scores) / len(scores) if scores else 0

    return {
        "model": model,
        "hits": hits,
        "misses": total - hits,
        "recall": round(hits / total * 100, 1),
        "avg_score": round(avg_score, 3),
        "avg_latency_ms": round(elapsed / total * 1000, 1),
    }


if __name__ == "__main__":
    print("Benchmark de Embeddings — Memoria de Aura")
    print("=" * 50)

    results = {}
    for model in ["nomic-embed-text:latest"]:  # bge-m3 via Ollama: pull first
        r = evaluate(model)
        results[model] = r
        print(f"  Recall: {r['recall']}% ({r['hits']}/{r['hits']+r['misses']})")
        print(f"  Avg Score: {r['avg_score']}")
        print(f"  Avg Latency: {r['avg_latency_ms']}ms")

    # Note for bge-m3
    print("\nPara bge-m3: ollama pull bge-m3 && re-ejecutar")
    print(f"Baseline nomic: recall={results.get('nomic-embed-text:latest', {}).get('recall', 'N/A')}%")

    # Cleanup
    try:
        QDRANT.delete_collection(COLLECTION)
    except Exception:
        pass
