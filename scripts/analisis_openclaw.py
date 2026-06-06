#!/usr/bin/env python3
"""analisis_openclaw.py — Lanza análisis con OpenClaw + Ollama de los datos recogidos.

Asigna un agente OpenClaw por cada categoría de búsqueda.
"""
import json, sys, time, urllib.request
from pathlib import Path
from datetime import datetime

OLLAMA = "http://10.164.1.99:11434/api/generate"
MODELO_RAPIDO = "qwen2.5:7b"
MODELO_PROFUNDO = "qwen3:32b-q8_0"

COLA_DIR = Path.home() / ".nervioso" / "ura_search" / "cola"
OUT_DIR = Path("/home/ramon/URA/ura_search/data/analisis")
OUT_DIR.mkdir(parents=True, exist_ok=True)

def consultar_ollama(prompt, model=MODELO_RAPIDO, max_tokens=1500):
    """Consulta Ollama con un prompt."""
    data = json.dumps({
        "model": model, "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.2, "num_predict": max_tokens}
    }).encode()
    req = urllib.request.Request(OLLAMA, data=data, headers={"Content-Type": "application/json"})
    try:
        resp = urllib.request.urlopen(req, timeout=180)
        return json.loads(resp.read())["response"]
    except Exception as e:
        return f"[Error: {e}]"

def analizar_categoria(cat_dir, categoria):
    """Analiza una categoría de datos descargados."""
    metas = list(cat_dir.glob("*.meta.json"))
    if not metas:
        return f"No hay datos en {categoria}"
    
    urls = []
    fuentes = set()
    temas = set()
    for m in metas[:10]:
        d = json.loads(m.read_text())
        urls.append(d.get("url",""))
        if d.get("fuente"): fuentes.add(d["fuente"])
        if d.get("tema"): temas.add(d["tema"])
    
    prompt = f"""Eres un analista de inteligencia competitiva para hostelería en Pamplona.
    
Categoría: {categoria}
Fuentes: {', '.join(fuentes)}
Temas: {', '.join(temas)}
URLs de ejemplo: {chr(10).join(urls[:5])}

Genera un breve análisis de lo que estos datos revelan sobre:
1. Tendencias en la categoría {categoria}
2. Qué puedes extraer para un bar en Calle San Gregorio
3. Recomendaciones prácticas

Responde en español, máximo 300 palabras."""
    
    return consultar_ollama(prompt)

def main():
    print("=" * 60)
    print("ANÁLISIS OPENCLAW - COMPETENCIA PAMPLONA")
    print(f"{datetime.now().isoformat()}")
    print("=" * 60)
    
    resultados = {}
    
    for cat_dir in sorted(COLA_DIR.iterdir()):
        if not cat_dir.is_dir(): continue
        cat = cat_dir.name
        n = len(list(cat_dir.glob("*.meta.json")))
        if n < 3: continue  # Skip small categories
        
        print(f"\n🔍 Analizando {cat} ({n} archivos)...")
        analisis = analizar_categoria(cat_dir, cat)
        resultados[cat] = {
            "archivos": n,
            "analisis": analisis
        }
        print(analisis[:200] + "..." if len(analisis) > 200 else analisis)
        time.sleep(1)  # Avoid hammering Ollama
    
    # Save report
    report = {
        "fecha": datetime.now().isoformat(),
        "resultados": resultados
    }
    path = OUT_DIR / f"openclaw_analisis_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f"\n✅ Reporte guardado: {path}")

if __name__ == "__main__":
    main()
