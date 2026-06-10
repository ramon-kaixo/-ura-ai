#!/usr/bin/env python3
"""Benchmark de embeddings: nomic-embed-text vs bge-m3 — 20 consultas español."""
import sys, time, json
from pathlib import Path
sys.path.insert(0, "/home/ramon/URA/ura_ia_1972")
import httpx
from qdrant_client import QdrantClient, models

QDRANT = QdrantClient("127.0.0.1", port=6333)
OLLAMA = "http://127.0.0.1:11434/api/embeddings"
COLLECTION = "ideas_bench"

def embed(text: str, model: str) -> list[float]:
    r = httpx.post(OLLAMA, json={"model": model, "prompt": text}, timeout=60)
    r.raise_for_status()
    return r.json()["embedding"]

CONSULTAS = [
    {"query": "herramientas gratis para disenar menus de bar", "esperado": ["Canva", "Adobe", "gratis", "plantillas"]},
    {"query": "tendencias en carteles digitales 2026", "esperado": ["QR", "digital", "foto", "tendencia"]},
    {"query": "como automatizar la creacion de carteles con API", "esperado": ["API", "automatizar", "plantillas"]},
    {"query": "programacion asincrona en Python con ejemplos", "esperado": ["asyncio", "coroutine", "async", "await"]},
    {"query": "alternativas gratuitas a Adobe para diseno grafico", "esperado": ["gratis", "Canva", "freemium", "Express"]},
    {"query": "que es asyncio y para que sirve en Python", "esperado": ["I/O", "concurrente", "async", "event loop"]},
    {"query": "menus con codigo QR para restaurantes modernos", "esperado": ["QR", "digital", "menu"]},
    {"query": "manejo eficiente de tareas I/O en Python moderno", "esperado": ["asyncio", "I/O-bound", "coroutine"]},
    {"query": "herramientas de diseno con marca de agua gratuitas", "esperado": ["Adobe Express", "freemium", "marca"]},
    {"query": "framework para construir APIs rapidas en Python 2026", "esperado": ["FastAPI", "API", "Python"]},
    {"query": "como hacer una pagina web para un negocio pequeno", "esperado": ["hosting", "dominio", "plantilla"]},
    {"query": "estrategias de SEO local para bares y restaurantes", "esperado": ["SEO", "local", "Google", "resenas"]},
    {"query": "software libre para gestion de inventario de cocina", "esperado": ["inventario", "gratis", "open source"]},
    {"query": "precios de plataformas de reservas online 2026", "esperado": ["precio", "plataforma", "reserva", "euros"]},
    {"query": "como hacer fotos profesionales de comida con el movil", "esperado": ["foto", "iluminacion", "angulo"]},
    {"query": "herramientas de analisis de competencia para negocios", "esperado": ["competencia", "SEO", "analitica"]},
    {"query": "tendencias de colores en branding de bares 2026", "esperado": ["color", "paleta", "branding"]},
    {"query": "como crear un menu interactivo con fotos y precios", "esperado": ["interactivo", "foto", "precio", "QR"]},
    {"query": "requisitos legales para abrir un bar en Espana 2026", "esperado": ["licencia", "sanidad", "legal"]},
    {"query": "estrategias de marketing digital para hosteleria", "esperado": ["Instagram", "redes", "marketing", "digital"]},
]

IDEAS_SEED = [
    ("Canva permite crear menus gratis con plantillas y tiene API para automatizar", "carteles", ["menus","diseno","automatizacion"], "herramienta", "Canva", "gratis"),
    ("Tendencia 2026: menus digitales con codigo QR y fotos grandes", "carteles", ["menus","QR","tendencias"], "tendencia", "", ""),
    ("Adobe Express ofrece menus gratis con marca de agua para probar disenos", "carteles", ["menus","diseno"], "herramienta", "Adobe Express", "freemium"),
    ("FastAPI es el framework para APIs asincronas en Python con documentacion OpenAPI", "programacion", ["FastAPI","Python","API"], "tecnica", "", ""),
    ("El SEO local requiere fichas de Google My Business, resenas gestionadas y palabras clave de barrio", "marketing", ["SEO","local","Google"], "tecnica", "", ""),
    ("Para fotos de comida usa luz natural difusa, angulo cenital y edicion minima con Snapseed gratis", "fotografia", ["foto","comida","movil"], "tecnica", "Snapseed", "gratis"),
    ("Las paletas de color calidas (terracota, mostaza, verde oliva) dominan el branding hostelero en 2026", "diseno", ["color","paleta","branding"], "tendencia", "", ""),
    ("Un menu digital interactivo con QR permite cambiar precios y fotos sin reimprimir", "carteles", ["QR","digital","interactivo"], "tendencia", "", ""),
    ("Para abrir un bar en Espana necesitas licencia de actividad, permiso sanitario y registro en hacienda", "legal", ["licencia","sanidad","legal"], "dato", "", ""),
    ("Instagram y TikTok son los canales principales de marketing para hosteleria con contenido visual diario", "marketing", ["Instagram","redes","marketing"], "tendencia", "", ""),
]

def run_bench(model: str, dim: int) -> dict:
    label = model.split(":")[0] if ":" in model else model
    print(f"\n{'='*55}")
    print(f"  {label} ({dim}d)")
    print(f"{'='*55}")

    try:
        QDRANT.delete_collection(COLLECTION)
    except Exception:
        pass
    QDRANT.create_collection(COLLECTION, vectors_config={"size": dim, "distance": "Cosine"})

    points = []
    for i, (txt, tema, tags, tipo, h, c) in enumerate(IDEAS_SEED):
        vec = embed(f"{txt} {tema} {' '.join(tags)}", model)
        points.append(models.PointStruct(id=i+1, vector=vec, payload={"idea":txt,"tema":tema,"etiquetas":tags,"tipo":tipo,"herramienta":h,"coste":c}))
    QDRANT.upsert(COLLECTION, points)

    hits, prec3 = 0, 0
    scores, latencies = [], []

    for c in CONSULTAS:
        t0 = time.time()
        vec = embed(c["query"], model)
        results = QDRANT.query_points(COLLECTION, query=vec, limit=5)
        latencies.append((time.time()-t0)*1000)
        top3 = [p.payload.get("idea","") for p in results.points[:3]]
        top5 = [p.payload.get("idea","") for p in results.points]
        found = any(any(kw.lower() in idea.lower() for idea in top5) for kw in c["esperado"])
        if found:
            hits += 1
        prec = sum(1 for idea in top3 if any(kw.lower() in idea.lower() for kw in c["esperado"])) / 3
        prec3 += prec
        scores.append(results.points[0].score if results.points else 0)

    QDRANT.delete_collection(COLLECTION)
    return {
        "model": label,
        "dim": dim,
        "recall": round(hits/len(CONSULTAS)*100, 1),
        "precision@3": round(prec3/len(CONSULTAS)*100, 1),
        "avg_score": round(sum(scores)/len(scores), 3),
        "avg_latency_ms": round(sum(latencies)/len(latencies), 1),
    }

if __name__ == "__main__":
    print("Benchmark de Embeddings — Memoria de Aura v2")
    print("20 consultas en espanol, 10 ideas semilla, Qdrant Cosine\n")

    models = [("nomic-embed-text:latest", 768)]
    # Check bge-m3 availability
    try:
        tags = httpx.get("http://127.0.0.1:11434/api/tags", timeout=5).json()
        if any("bge-m3" in m["name"] for m in tags["models"]):
            models.append(("bge-m3:latest", 1024))
            print("bge-m3: disponible 1024d")
    except Exception:
        pass

    results = {}
    for model, dim in models:
        r = run_bench(model, dim)
        results[r["model"]] = r
        print(f"  Recall={r['recall']}%  Prec@3={r['precision@3']}%  AvgScore={r['avg_score']}  Lat={r['avg_latency_ms']}ms")

    if len(results) == 2:
        n, b = results["nomic-embed-text"], results["bge-m3"]
        diff = b["recall"] - n["recall"]
        winner = "bge-m3" if diff >= 10 else "nomic-embed-text"
        print(f"\nDiferencia recall: {diff:+.1f}%")
        print(f"Ganador: {winner}")
        if diff >= 10:
            print("bge-m3 gana por >=10% → elegido")
        else:
            print("Diferencia <10% → nomic (mas ligero: 274MB vs 1.5GB)")
